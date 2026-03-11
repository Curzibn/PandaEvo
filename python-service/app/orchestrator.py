from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from app.providers.store import ProviderLike
from app.coder.agent import CoderAgent
from app.evolution import EvolutionAgent
from app.logger import get_logger
from app.providers.llm import llm_provider
from app.worker import run_worker

logger = get_logger(__name__)

_PLAN_SYSTEM = """你是一个任务规划专家。分析用户的请求，将其拆解为若干子任务分配给 Worker 执行。

输出严格的 JSON 格式（不含任何其他文字）：
{
  "tasks": [
    {
      "id": "t1",
      "title": "简短标题（10字以内）",
      "type": "analysis",
      "prompt": "给 Worker 的完整自包含指令，需包含完成该子任务所需的全部上下文",
      "depends_on": []
    }
  ]
}

type 字段取值：
- "analysis"：信息查询、代码阅读、分析推理、写作、工作区文件操作等。
- "coder"：需要修改应用服务代码（python-service、web-pc 等）并通过 Gitea 创建 PR 的任务。根据用户意图自主判断是否使用，无需用户明确说"部署"或"上线"。
- "evolution"：需要对已有 Gitea PR 进行代码审查并决策是否合并部署的任务。

约束：
- 子任务数量 1～5 个
- 每个 Worker 只完成一件事，prompt 必须自包含
- 可并行的任务 depends_on 为空，需要前置结果的任务在 depends_on 中列出前置任务 id
- 若任务本身可直接由一个 Worker 完成，输出单个任务即可
- coder/evolution 任务通常应 depends_on 前置的 analysis 任务（先读懂代码再修改或审查）"""

_SYNTHESIZE_SYSTEM = """你是一个结果汇总专家。根据各子任务的执行结果，综合生成完整、清晰的最终回答。"""


@dataclass
class Task:
    id: str
    title: str
    prompt: str
    depends_on: list[str] = field(default_factory=list)
    type: str = "analysis"


def _parse_plan(raw: str) -> list[Task]:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])
        return [
            Task(
                id=t["id"],
                title=t["title"],
                prompt=t["prompt"],
                depends_on=t.get("depends_on", []),
                type=t.get("type", "analysis"),
            )
            for t in data.get("tasks", [])
        ]
    except Exception:
        logger.exception("Failed to parse orchestrator plan")
        return []


def _topological_batches(tasks: list[Task]) -> list[list[Task]]:
    remaining = {t.id: t for t in tasks}
    done: set[str] = set()
    batches: list[list[Task]] = []

    while remaining:
        batch = [t for t in remaining.values() if all(dep in done for dep in t.depends_on)]
        if not batch:
            batch = list(remaining.values())
        for t in batch:
            del remaining[t.id]
            done.add(t.id)
        batches.append(batch)

    return batches


async def _run_batch_concurrent(
    batch: list[Task],
    orchestrator_model: str,
    orchestrator_provider: ProviderLike,
    worker_model: str,
    worker_provider: ProviderLike,
    task_results: dict[str, str],
    messages: list[dict[str, Any]],
) -> AsyncGenerator[dict[str, Any], None]:
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    pending = len(batch)

    async def _run_one(task: Task) -> None:
        try:
            if task.type == "evolution":
                stream = EvolutionAgent().run(task.id, task.prompt, orchestrator_model, orchestrator_provider)
            elif task.type == "coder":
                prior = {tid: task_results[tid] for tid in task.depends_on if tid in task_results}
                stream = CoderAgent().run(
                    task.id, task.prompt,
                    original_messages=messages,
                    prior_results=prior,
                    model=worker_model,
                    provider=worker_provider,
                )
            else:
                stream = run_worker(task.id, task.prompt, worker_model, worker_provider)
            async for event in stream:
                await queue.put(event)
                if event["type"] == "worker_done":
                    task_results[task.id] = event.get("result", "")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker %s failed", task.id)
            task_results[task.id] = ""
            await queue.put({"type": "worker_done", "task_id": task.id, "result": ""})
        finally:
            await queue.put(None)

    worker_tasks = [asyncio.create_task(_run_one(task)) for task in batch]

    try:
        finished = 0
        while finished < pending:
            item = await queue.get()
            if item is None:
                finished += 1
            else:
                yield item
    finally:
        for t in worker_tasks:
            t.cancel()
        await asyncio.gather(*worker_tasks, return_exceptions=True)


class OrchestratorAgent:
    async def run(
        self,
        task: str,
        model: str,
        messages: list[dict[str, Any]],
        orchestrator_provider: ProviderLike,
        worker_model: str,
        worker_provider: ProviderLike,
    ) -> AsyncGenerator[dict[str, Any], None]:
        plan_messages = [
            {"role": "system", "content": _PLAN_SYSTEM},
            *messages,
        ]
        plan_response = await llm_provider.complete(
            model=model,
            messages=plan_messages,
            api_key=orchestrator_provider.api_key,
            api_base=orchestrator_provider.api_base,
        )
        raw_plan = plan_response.get("content", "")
        tasks = _parse_plan(raw_plan)

        if not tasks:
            tasks = [Task(id="t1", title=task[:20], prompt=task, depends_on=[])]

        yield {
            "type": "plan",
            "tasks": [
                {"id": t.id, "title": t.title, "type": t.type, "depends_on": t.depends_on}
                for t in tasks
            ],
        }

        task_results: dict[str, str] = {}
        batches = _topological_batches(tasks)

        for batch in batches:
            async for event in _run_batch_concurrent(
                batch,
                model,
                orchestrator_provider,
                worker_model,
                worker_provider,
                task_results,
                messages,
            ):
                yield event

        results_text = "\n\n".join(
            f"## {t.title}\n{task_results.get(t.id, '（无结果）')}"
            for t in tasks
        )
        synthesize_messages = [
            {"role": "system", "content": _SYNTHESIZE_SYSTEM},
            *messages,
            {
                "role": "user",
                "content": f"以下是各子任务的执行结果：\n\n{results_text}\n\n请根据上述结果生成完整的最终回答。",
            },
        ]

        all_thinking: list[str] = []
        response: dict[str, Any] = {}

        async for event_type, payload in llm_provider.stream_complete(
            model=model,
            messages=synthesize_messages,
            api_key=orchestrator_provider.api_key,
            api_base=orchestrator_provider.api_base,
        ):
            if event_type == "thinking":
                all_thinking.append(payload)
                yield {"type": "thinking", "content": payload}
            elif event_type == "token":
                yield {"type": "token", "content": payload}
            else:
                response = payload

        new_message: dict[str, Any] = {
            "role": "assistant",
            "content": response.get("content", ""),
        }
        thinking_content = "".join(all_thinking) or None
        if thinking_content:
            new_message["thinking"] = thinking_content

        yield {"type": "done", "new_message": new_message}
