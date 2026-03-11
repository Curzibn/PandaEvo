from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import litellm

litellm.drop_params = True


class LLMProvider:
    @staticmethod
    def _normalize_model_name(model: str, api_base: str | None) -> str:
        if api_base and "/" not in model:
            return f"openai/{model}"
        return model

    async def stream_complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        api_key: str,
        api_base: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[tuple[str, Any], None]:
        normalized_model = self._normalize_model_name(model, api_base)
        kwargs: dict[str, Any] = {
            "model": normalized_model,
            "messages": messages,
            "api_key": api_key,
            "stream": True,
        }
        if api_base:
            kwargs["api_base"] = api_base
        if tools:
            kwargs["tools"] = tools

        content_parts: list[str] = []
        tool_calls_map: dict[int, dict[str, Any]] = {}

        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            delta = chunk.choices[0].delta

            raw_thinking = getattr(delta, "reasoning_content", None) or getattr(delta, "thinking", None)
            if raw_thinking:
                yield ("thinking", raw_thinking)

            if delta.content:
                content_parts.append(delta.content)
                yield ("token", delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = {
                            "id": tc_delta.id or "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    tc = tool_calls_map[idx]
                    if tc_delta.id:
                        tc["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc["function"]["arguments"] += tc_delta.function.arguments

        tool_calls = (
            [tool_calls_map[i] for i in sorted(tool_calls_map)]
            if tool_calls_map
            else None
        )
        yield (
            "complete",
            {
                "role": "assistant",
                "content": "".join(content_parts),
                "tool_calls": tool_calls,
            },
        )

    async def complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        api_key: str,
        api_base: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_model = self._normalize_model_name(model, api_base)
        kwargs: dict[str, Any] = {
            "model": normalized_model,
            "messages": messages,
            "api_key": api_key,
            "stream": False,
        }
        if api_base:
            kwargs["api_base"] = api_base
        if tools:
            kwargs["tools"] = tools
        if extra_body:
            kwargs["extra_body"] = extra_body

        response = await litellm.acompletion(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]

        return {
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": tool_calls,
            "finish_reason": choice.finish_reason,
        }

    @staticmethod
    def parse_tool_call_args(arguments: str) -> dict[str, Any]:
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return {}


llm_provider = LLMProvider()
