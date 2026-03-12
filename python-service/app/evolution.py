from __future__ import annotations

import json
from hashlib import sha1
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.config import get_evolution_core_url
from app.providers.store import ProviderLike


class EvolutionAgent:
    def _build_payload(self, task_id: str, prompt: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"task_id": task_id, "prompt": prompt}
        try:
            parsed = json.loads(prompt)
        except Exception:
            return payload
        if not isinstance(parsed, dict):
            return payload

        pr_context = parsed.get("pr_context")
        instruction = parsed.get("instruction")
        if isinstance(pr_context, dict):
            payload["pr_context"] = pr_context
            repo = pr_context.get("repo", "")
            branch = pr_context.get("branch", "")
            pr_number = pr_context.get("pr_number", "")
            key_raw = f"{repo}:{branch}:{pr_number}"
            payload["idempotency_key"] = sha1(key_raw.encode("utf-8")).hexdigest()
        if isinstance(instruction, str) and instruction.strip():
            payload["prompt"] = instruction.strip()
        return payload

    async def run(
        self,
        task_id: str,
        prompt: str,
        model: str,
        provider: ProviderLike,
    ) -> AsyncGenerator[dict[str, Any], None]:
        url = get_evolution_core_url()
        if not url:
            yield {"type": "worker_start", "task_id": task_id}
            yield {
                "type": "worker_done",
                "task_id": task_id,
                "result": "Error: evolution_core.url is not configured",
            }
            return

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{url}/run",
                json=self._build_payload(task_id, prompt),
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        yield json.loads(line[6:])
