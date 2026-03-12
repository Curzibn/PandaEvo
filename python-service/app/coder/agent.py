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

应用仓库默认是 python-service 和 web-pc，运行时会在服务启动阶段从 Gitea 拉取到容器目录。
调用 list_repos 可获取仓库实际名称。

## 工作流程

1. 调用 list_repos 确认目标仓库名称（通常为 python-service 或 web-pc）
2. 调用 clone_repo 克隆该仓库并创建功能分支
3. 使用 list_dir / read_file / search_files 深入理解现有代码结构和设计模式
4. 使用 write_file / edit_file 实现代码变更（严格遵循现有代码风格）
5. 调用 commit_and_push 提交变更并推送分支
6. 调用 create_pr 创建 PR，标题和描述须清晰说明变更内容和原因

## 约束

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


def _extract_json(content: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


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
        pr_artifact: dict[str, Any] | None = None

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
                    if pr_artifact is None:
                        fail_payload = {
                            "success": False,
                            "code": "PR_NOT_CREATED",
                            "error": "Coder task ended without a successful create_pr result.",
                        }
                        yield {
                            "type": "worker_done",
                            "task_id": task_id,
                            "result": json.dumps(fail_payload, ensure_ascii=False),
                        }
                        return
                    result_payload = {
                        "success": True,
                        "code": "CODER_COMPLETED_WITH_PR",
                        "data": pr_artifact,
                        "message": "".join(result_parts) or content,
                    }
                    yield {
                        "type": "worker_done",
                        "task_id": task_id,
                        "result": json.dumps(result_payload, ensure_ascii=False),
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

                    parsed_result = _extract_json(result)
                    if (
                        name == "create_pr"
                        and parsed_result
                        and parsed_result.get("success") is True
                        and parsed_result.get("code") == "PR_CREATED"
                    ):
                        data = parsed_result.get("data")
                        if isinstance(data, dict):
                            pr_artifact = data

                    messages.append({"role": "tool", "tool_call_id": call_id, "content": result})

                if pr_artifact is not None:
                    result_payload = {
                        "success": True,
                        "code": "CODER_COMPLETED_WITH_PR",
                        "data": pr_artifact,
                    }
                    yield {
                        "type": "worker_done",
                        "task_id": task_id,
                        "result": json.dumps(result_payload, ensure_ascii=False),
                    }
                    return

            fail_payload = {
                "success": False,
                "code": "PR_NOT_CREATED",
                "error": "Coder task ended without a successful create_pr result.",
            }
            yield {
                "type": "worker_done",
                "task_id": task_id,
                "result": json.dumps(fail_payload, ensure_ascii=False),
            }

        finally:
            cleanup_clone()
