from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Literal

from app.config import (
    get_auto_trigger_evolution_after_pr,
    get_enforce_code_tasks_via_orchestrator,
    get_rules_enabled,
)
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
- "coder"：需要修改应用服务代码（优先 python-service、web-pc 仓库）并通过 Gitea 创建 PR 的任务。根据用户意图自主判断是否使用，无需用户明确说"部署"或"上线"。
- "evolution"：需要对已有 Gitea PR 进行代码审查并决策是否合并部署的任务。

约束：
- 子任务数量 1～5 个
- 每个 Worker 只完成一件事，prompt 必须自包含
- 可并行的任务 depends_on 为空，需要前置结果的任务在 depends_on 中列出前置任务 id
- 若任务本身可直接由一个 Worker 完成，输出单个任务即可
- coder/evolution 任务通常应 depends_on 前置的 analysis 任务（先读懂代码再修改或审查）"""

_SYNTHESIZE_SYSTEM = """你是一个结果汇总专家。根据各子任务的执行结果，综合生成完整、清晰的最终回答。

约束：若某子任务结果包含 success: false、error 或 PR_NOT_CREATED 等失败信息，必须在回答中如实说明该任务失败及原因，不得声称任务已成功完成。"""
_ROUTE_SYSTEM = """你是一个路由决策器。你只负责判断当前请求应该走 direct 还是 orchestrator。

请输出严格 JSON（不含任何其他文字）：
{
  "route": "direct",
  "reason": "简短原因（20字以内）"
}

取值约束：
- route 只能是 "direct" 或 "orchestrator"
- reason 必须简短、可读

决策原则：
- 简单问候、闲聊、单步直接回答，优先 direct
- 需要拆分步骤、并行处理、多阶段汇总，选择 orchestrator
"""


@dataclass
class Task:
    id: str
    title: str
    prompt: str
    depends_on: list[str] = field(default_factory=list)
    type: str = "analysis"


@dataclass
class RouteDecision:
    route: Literal["direct", "orchestrator"]
    reason: str


_GITEA_RE = re.compile(r"(commit|pull request|gitea)", re.IGNORECASE)


def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                return content
    return ""


def is_code_intent_request(text: str) -> bool:
    if not text:
        return False
    return _GITEA_RE.search(text) is not None


def _build_route_system() -> str:
    base = _ROUTE_SYSTEM
    if not get_rules_enabled():
        return base
    from app.rules import get_rule_snapshot, integrate_rules, match_rules
    snapshot = get_rule_snapshot()
    always_rules = [r for r in snapshot.rules.values() if r.metadata.always_apply]
    return integrate_rules(base, always_rules)


def _parse_json_dict(raw: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_task_result(task_type: str, raw: str) -> dict[str, Any]:
    parsed = _parse_json_dict(raw) if isinstance(raw, str) else None
    if parsed and isinstance(parsed.get("success"), bool):
        success = bool(parsed.get("success"))
        code = str(parsed.get("code", ""))
        data = parsed.get("data")
        return {
            "raw": raw,
            "success": success,
            "code": code,
            "data": data if isinstance(data, dict) else {},
            "error": str(parsed.get("error", "")) if not success else "",
        }

    if task_type == "coder":
        return {
            "raw": raw,
            "success": False,
            "code": "CODER_RESULT_INVALID",
            "data": {},
            "error": "Coder result is not a structured JSON payload.",
        }

    text = raw or ""
    failed = "Error:" in text or "Traceback" in text
    return {
        "raw": raw,
        "success": not failed,
        "code": "WORKER_ERROR" if failed else "OK",
        "data": {},
        "error": text if failed else "",
    }


def _extract_pr_artifact(normalized: dict[str, Any]) -> dict[str, Any] | None:
    if not normalized.get("success"):
        return None
    data = normalized.get("data")
    if not isinstance(data, dict):
        return None
    required = ("repo", "branch", "pr_number", "pr_url")
    if all(data.get(k) for k in required):
        return {
            "repo": data["repo"],
            "branch": data["branch"],
            "pr_number": data["pr_number"],
            "pr_url": data["pr_url"],
        }
    return None


def _parse_route_decision(raw: str) -> RouteDecision:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])
        route = str(data.get("route", "")).strip().lower()
        reason = str(data.get("reason", "")).strip()
        if route not in ("direct", "orchestrator"):
            raise ValueError("invalid route")
        return RouteDecision(route=route, reason=reason or "model route")
    except Exception:
        logger.exception("Failed to parse route decision")
        return RouteDecision(route="direct", reason="fallback: parse failed")


async def decide_route(
    *,
    model: str,
    messages: list[dict[str, Any]],
    provider: ProviderLike,
) -> RouteDecision:
    if get_enforce_code_tasks_via_orchestrator() and is_code_intent_request(_latest_user_text(messages)):
        return RouteDecision(route="orchestrator", reason="policy: gitea intent enforced")

    route_messages = [
        {"role": "system", "content": _build_route_system()},
        *messages,
    ]
    try:
        route_response = await llm_provider.complete(
            model=model,
            messages=route_messages,
            api_key=provider.api_key,
            api_base=provider.api_base,
        )
        raw = route_response.get("content", "")
        return _parse_route_decision(raw)
    except Exception:
        logger.exception("Route decision failed")
        return RouteDecision(route="direct", reason="fallback: route failed")


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
    task_results: dict[str, dict[str, Any]],
    messages: list[dict[str, Any]],
) -> AsyncGenerator[dict[str, Any], None]:
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    pending = len(batch)

    async def _run_one(task: Task) -> None:
        try:
            if task.type == "evolution":
                stream = EvolutionAgent().run(task.id, task.prompt, orchestrator_model, orchestrator_provider)
            elif task.type == "coder":
                prior = {tid: task_results[tid]["raw"] for tid in task.depends_on if tid in task_results}
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
                    raw_result = event.get("result", "")
                    task_results[task.id] = _normalize_task_result(task.type, raw_result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker %s failed", task.id)
            task_results[task.id] = _normalize_task_result(
                task.type,
                json.dumps(
                    {"success": False, "code": "WORKER_EXCEPTION", "error": f"Worker {task.id} failed unexpectedly"},
                    ensure_ascii=False,
                ),
            )
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
        plan_system = _PLAN_SYSTEM
        if get_rules_enabled():
            from app.rules import get_rule_snapshot, integrate_rules
            snapshot = get_rule_snapshot()
            always_rules = [r for r in snapshot.rules.values() if r.metadata.always_apply]
            plan_system = integrate_rules(plan_system, always_rules)

        plan_messages = [
            {"role": "system", "content": plan_system},
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

        task_results: dict[str, dict[str, Any]] = {}
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

        if get_auto_trigger_evolution_after_pr() and not any(t.type == "evolution" for t in tasks):
            extra_evolution_tasks: list[Task] = []
            for task in tasks:
                if task.type != "coder":
                    continue
                normalized = task_results.get(task.id, {})
                artifact = _extract_pr_artifact(normalized)
                if not artifact:
                    continue
                evo_id = f"{task.id}_evo"
                extra_evolution_tasks.append(
                    Task(
                        id=evo_id,
                        title=f"{task.title}-审查",
                        type="evolution",
                        depends_on=[],
                        prompt=json.dumps(
                            {
                                "instruction": "请执行代码审查并给出是否可灰度发布结论。",
                                "pr_context": {
                                    "repo": artifact["repo"],
                                    "branch": artifact["branch"],
                                    "pr_number": artifact["pr_number"],
                                    "pr_url": artifact["pr_url"],
                                },
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
            if extra_evolution_tasks:
                tasks.extend(extra_evolution_tasks)
                async for event in _run_batch_concurrent(
                    extra_evolution_tasks,
                    model,
                    orchestrator_provider,
                    worker_model,
                    worker_provider,
                    task_results,
                    messages,
                ):
                    yield event

        if (
            len(tasks) == 1
            and tasks[0].type == "analysis"
            and not tasks[0].depends_on
        ):
            new_message = {
                "role": "assistant",
                "content": task_results.get(tasks[0].id, {}).get("raw", ""),
            }
            yield {"type": "done", "status": "success", "new_message": new_message, "artifacts": {}}
            return

        results_text = "\n\n".join(
            f"## {t.title}\n{task_results.get(t.id, {}).get('raw', '（无结果）')}"
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

        failed_tasks = [
            {
                "id": t.id,
                "title": t.title,
                "type": t.type,
                "code": task_results.get(t.id, {}).get("code", "UNKNOWN"),
                "error": task_results.get(t.id, {}).get("error", ""),
            }
            for t in tasks
            if not task_results.get(t.id, {}).get("success", False)
        ]
        pr_artifacts = [
            artifact
            for t in tasks
            if t.type == "coder"
            for artifact in [_extract_pr_artifact(task_results.get(t.id, {}))]
            if artifact is not None
        ]
        status = "success"
        if failed_tasks and pr_artifacts:
            status = "partial"
        elif failed_tasks:
            status = "failed"

        logger.info(
            "orchestrator_done status=%s failed_tasks=%d prs=%d",
            status,
            len(failed_tasks),
            len(pr_artifacts),
        )

        yield {
            "type": "done",
            "status": status,
            "new_message": new_message,
            "artifacts": {"prs": pr_artifacts, "failed_tasks": failed_tasks},
        }
