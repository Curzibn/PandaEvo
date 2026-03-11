from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from app.agent import AgentRunner
from app.providers.store import ProviderLike


async def run_worker(
    task_id: str,
    prompt: str,
    model: str,
    provider: ProviderLike,
) -> AsyncGenerator[dict[str, Any], None]:
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    result_parts: list[str] = []

    yield {"type": "worker_start", "task_id": task_id}

    async for event in AgentRunner().run(
        model=model,
        messages=messages,
        provider=provider,
    ):
        etype = event["type"]

        if etype == "done":
            new_msg = event.get("new_message", {})
            if new_msg.get("content"):
                result_parts.append(new_msg["content"])
            yield {"type": "worker_done", "task_id": task_id, "result": "".join(result_parts)}
            return

        if etype == "token":
            result_parts.append(event["content"])

        yield {"type": "worker_event", "task_id": task_id, "event": event}

    yield {"type": "worker_done", "task_id": task_id, "result": "".join(result_parts)}
