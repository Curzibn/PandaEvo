from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.config import get_evolution_core_url
from app.providers.store import ProviderLike


class EvolutionAgent:
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
                json={"task_id": task_id, "prompt": prompt},
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        yield json.loads(line[6:])
