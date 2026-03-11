from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from app.config import (
    get_rules_auto_match,
    get_rules_enabled,
    get_skills_auto_match,
    get_skills_enabled,
    get_skills_max_skills,
    get_workspace_root,
)
from app.providers.store import ProviderLike
from app.providers.llm import llm_provider
from app.skills import integrate_skills, match_skills
from app.skills.integrator import integrate_skill_content, integrate_skills_discovery
from app.skills.snapshot import get_skill_snapshot
from app.tools import TOOLS_REGISTRY, dispatch, get_tool_schemas

_MAX_ROUNDS = 10
_SNAPSHOT_DEPTH = 2
_SNAPSHOT_MAX_LINES = 100


def _render_tree(node: dict[str, Any], indent: int = 0) -> list[str]:
    lines = ["  " * indent + node["name"] + ("/" if node["type"] == "dir" else "")]
    for child in node.get("children", []):
        lines.extend(_render_tree(child, indent + 1))
    return lines


def _workspace_snapshot() -> str:
    from app.tools.list_dir import build_dir_tree
    try:
        tree = build_dir_tree(".", _SNAPSHOT_DEPTH, include_hidden=False)
        lines = _render_tree(tree)[1:]
        if len(lines) > _SNAPSHOT_MAX_LINES:
            lines = lines[:_SNAPSHOT_MAX_LINES] + [f"... ({len(lines) - _SNAPSHOT_MAX_LINES} more items truncated)"]
        return "\n".join(lines)
    except Exception:
        return "(unavailable)"


_FILE_TOOLS = {"read_file", "write_file", "edit_file"}


def _extract_accessed_files(messages: list[dict[str, Any]]) -> list[str]:
    """从历史 assistant 消息的 tool_calls 中提取文件路径"""
    accessed: list[str] = []
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls", []):
            if tc.get("function", {}).get("name") not in _FILE_TOOLS:
                continue
            try:
                args = json.loads(tc["function"].get("arguments", "{}"))
                if path := args.get("path"):
                    accessed.append(path)
            except Exception:
                pass
    return accessed


def _build_system_prompt(
    user_input: str | None = None,
    accessed_files: list[str] | None = None,
) -> str:
    workspace = str(get_workspace_root())
    tool_lines = "\n".join(
        f"- {t.name}: {t.description}" for t in TOOLS_REGISTRY
    )
    snapshot = _workspace_snapshot()
    base_prompt = f"""你是一个通用 AI 助手，可以处理任意类型的任务，包括但不限于：调研分析、编程开发、文件操作、信息整理、写作等。

## 工作方式

按"规划 → 执行 → 汇总"三阶段推进任务：
1. **规划**：拆解任务，识别依赖关系，确定执行顺序
2. **执行**：逐步调用工具获取信息或完成操作
3. **汇总**：整合所有结果，给出清晰完整的最终答案

需要信息或操作时调用工具，无需工具时直接回答。

## 当前工作区

{workspace}

所有文件路径均相对于工作区根目录，禁止访问工作区以外的路径。

## 工作区结构快照（深度 {_SNAPSHOT_DEPTH}）

{snapshot}

注：`code/` 目录为本系统源代码（只读），包含 python-service、web-pc 等服务的完整代码，可通过 read_file / list_dir / search_files 自由查阅。

## 可用工具（可调用函数）

以下工具可以通过 function calling 机制直接调用：

{tool_lines}

**重要**：工具是可执行的函数，你可以通过 function calling 调用它们。工具名称必须完全匹配才能调用。

## ReAct 约束

每轮先思考（分析当前状态和下一步行动），再决定是否调用工具。工具结果返回后继续推理，直至得出最终结论。不要在同一轮既输出最终答案又调用工具。"""

    if get_rules_enabled():
        from app.rules import get_rule_snapshot, integrate_rules, match_rules
        
        snapshot = get_rule_snapshot()
        matched_rules = match_rules(
            all_rules=snapshot.rules,
            user_input=user_input,
            accessed_files=accessed_files,
            manual_rule_name=None,
        )
        base_prompt = integrate_rules(base_prompt, matched_rules)

    if get_skills_enabled():
        snapshot = get_skill_snapshot()
        
        if user_input:
            matched_discoveries = match_skills(
                user_input,
                all_skills=snapshot.discovered,
                auto_match=get_skills_auto_match(),
                max_skills=get_skills_max_skills(),
            )
            
            if matched_discoveries:
                activated_skills: list = []
                for discovery in matched_discoveries:
                    activated = snapshot.activate_skill(discovery.name)
                    if activated:
                        activated_skills.append(activated)
                
                if activated_skills:
                    prompt_with_discovery = integrate_skills_discovery(base_prompt, list(snapshot.discovered.values()))
                    for activated in activated_skills:
                        prompt_with_discovery = integrate_skill_content(prompt_with_discovery, activated)
                    return prompt_with_discovery
        else:
            if snapshot.discovered:
                return integrate_skills_discovery(base_prompt, list(snapshot.discovered.values()))

    return base_prompt


def _strip_thinking(msg: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in msg.items() if k != "thinking"}


class AgentRunner:
    async def run(
        self,
        model: str,
        messages: list[dict[str, Any]],
        provider: ProviderLike,
        allowed_tools: set[str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        tools = get_tool_schemas(allowed_tools)
        working = [_strip_thinking(m) for m in messages]

        user_input = None
        if working:
            for msg in reversed(working):
                if msg.get("role") == "user":
                    user_input = msg.get("content", "")
                    break

        accessed_files = _extract_accessed_files(working)
        if not working or working[0].get("role") != "system":
            working.insert(0, {"role": "system", "content": _build_system_prompt(user_input, accessed_files)})

        all_thinking: list[str] = []

        for _ in range(_MAX_ROUNDS):
            response: dict[str, Any] = {}
            async for event_type, payload in llm_provider.stream_complete(
                model=model,
                messages=working,
                api_key=provider.api_key,
                api_base=provider.api_base,
                tools=tools,
            ):
                if event_type == "thinking":
                    all_thinking.append(payload)
                    yield {"type": "thinking", "content": payload}
                elif event_type == "token":
                    yield {"type": "token", "content": payload}
                else:
                    response = payload

            tool_calls = response.get("tool_calls")

            if not tool_calls:
                final_msg: dict[str, Any] = {"role": "assistant", "content": response.get("content", "")}
                working.append(final_msg)
                thinking_content = "".join(all_thinking) or None
                new_message: dict[str, Any] = {**final_msg}
                if thinking_content:
                    new_message["thinking"] = thinking_content
                yield {"type": "done", "new_message": new_message}
                return

            assistant_with_calls: dict[str, Any] = {
                "role": "assistant",
                "content": response["content"],
                "tool_calls": tool_calls,
            }
            working.append(assistant_with_calls)

            tool_result_msgs: list[dict[str, Any]] = []
            for tc in tool_calls:
                call_id: str = tc["id"]
                name: str = tc["function"]["name"]
                args = llm_provider.parse_tool_call_args(tc["function"]["arguments"])

                yield {"type": "tool_call", "id": call_id, "name": name, "args": args}

                result = await dispatch(name, args, allowed_tools)

                yield {"type": "tool_result", "id": call_id, "content": result}

                tool_msg: dict[str, Any] = {"role": "tool", "tool_call_id": call_id, "content": result}
                working.append(tool_msg)
                tool_result_msgs.append(tool_msg)

            yield {"type": "checkpoint", "messages": [assistant_with_calls, *tool_result_msgs]}

        yield {"type": "error", "content": f"Reached max rounds ({_MAX_ROUNDS}) without a final response."}
        yield {"type": "done"}


