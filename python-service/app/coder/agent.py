from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from app.coder.tools import CODER_TOOLS, cleanup_clone, dispatch_coder
from app.providers.llm import llm_provider
from app.providers.store import ProviderLike

_MAX_ROUNDS = 50

_SYSTEM = """\
你是一名资深全栈程序员，负责根据任务描述对本系统的应用服务代码进行修改，并通过 Gitea 创建 PR 进入代码审查流程。

## 仓库结构

系统使用**单一 Gitea 仓库**，所有服务代码均在此仓库的子目录中：
- `apps/python-service/` — 后端 API 服务
- `apps/web-pc/`        — 前端 SPA

调用 list_repos 可获取仓库实际名称，通常为 `pandaevo`。

## 工作流程

1. 调用 list_repos 确认仓库名称（通常为 pandaevo）
2. 调用 clone_repo 克隆该仓库并创建功能分支
3. 使用 list_dir / read_file / search_files 深入理解现有代码结构和设计模式
4. 使用 write_file / edit_file 实现代码变更（严格遵循现有代码风格）
5. 调用 commit_and_push 提交变更并推送分支
6. 调用 create_pr 创建 PR，标题和描述须清晰说明变更内容和原因

## 约束

- 只修改 apps/python-service/ 和 apps/web-pc/ 目录下的代码
- 严禁修改 core/desktop/、core/evolution-core/ 等基座目录
- 每次任务只能调用一次 create_pr
- 代码须高内聚、低耦合，遵循现有模块的设计模式
- 引入新依赖时必须同步更新 pyproject.toml，使用 >= 约束而非固定版本
- 禁止添加无意义注释，代码应自说明"""


def _extract_text(msg: dict[str, Any]) -> str | None:
    raw = msg.get("content", "")
    if not raw or not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed.get("content") or None
    except (json.JSONDecodeError, TypeError):
        pass
    return raw or None


def _build_messages(
    original_messages: list[dict[str, Any]],
    prior_results: dict[str, str],
    prompt: str,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": _SYSTEM}]

    for msg in original_messages:
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _extract_text(msg)
        if text:
            messages.append({"role": role, "content": text})

    if prior_results:
        parts = ["以下是前置分析任务的执行结果，供你参考："]
        for tid, result in prior_results.items():
            parts.append(f"\n## {tid}\n{result}")
        messages.append({"role": "user", "content": "\n".join(parts)})

    messages.append({"role": "user", "content": f"当前编码任务：\n\n{prompt}"})
    return messages


class CoderAgent:
    async def run(
        self,
        task_id: str,
        prompt: str,
        original_messages: list[dict[str, Any]],
        prior_results: dict[str, str],
        model: str,
        provider: ProviderLike,
    ) -> AsyncGenerator[dict[str, Any], None]:
        yield {"type": "worker_start", "task_id": task_id}

        tools_schema = [t.to_schema() for t in CODER_TOOLS]
        messages = _build_messages(original_messages, prior_results, prompt)
        result_parts: list[str] = []

        try:
            for _ in range(_MAX_ROUNDS):
                response: dict[str, Any] = {}

                async for event_type, payload in llm_provider.stream_complete(
                    model=model,
                    messages=messages,
                    api_key=provider.api_key,
                    api_base=provider.api_base,
                    tools=tools_schema,
                ):
                    if event_type == "token":
                        result_parts.append(payload)
                        yield {
                            "type": "worker_event",
                            "task_id": task_id,
                            "event": {"type": "token", "content": payload},
                        }
                    else:
                        response = payload

                tool_calls = response.get("tool_calls")

                if not tool_calls:
                    content = response.get("content", "")
                    messages.append({"role": "assistant", "content": content})
                    yield {
                        "type": "worker_done",
                        "task_id": task_id,
                        "result": "".join(result_parts) or content,
                    }
                    return

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": response.get("content"),
                    "tool_calls": tool_calls,
                }
                messages.append(assistant_msg)

                for tc in tool_calls:
                    call_id: str = tc["id"]
                    name: str = tc["function"]["name"]
                    args = llm_provider.parse_tool_call_args(tc["function"]["arguments"])

                    yield {
                        "type": "worker_event",
                        "task_id": task_id,
                        "event": {"type": "tool_call", "id": call_id, "name": name, "args": args},
                    }

                    result = await dispatch_coder(name, args)

                    yield {
                        "type": "worker_event",
                        "task_id": task_id,
                        "event": {"type": "tool_result", "id": call_id, "content": result},
                    }

                    messages.append({"role": "tool", "tool_call_id": call_id, "content": result})

            yield {
                "type": "worker_done",
                "task_id": task_id,
                "result": "".join(result_parts),
            }

        finally:
            cleanup_clone()
