from __future__ import annotations

import json
from hashlib import sha1
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.config import get_evolution_core_url, get_gitea_org, get_gitea_token, get_gitea_url
from app.providers.store import ProviderLike

_DIFF_MAX_BYTES = 50 * 1024


async def _fetch_pr_diff(repo: str, pr_number: int | str) -> tuple[str | None, str | None]:
    base = get_gitea_url().rstrip("/")
    org = get_gitea_org()
    token = get_gitea_token().strip()
    url = f"{base}/api/v1/repos/{org}/{repo}/pulls/{pr_number}.diff"
    headers = {"Authorization": f"token {token}"} if token else {}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            text = resp.text
            if len(text.encode("utf-8")) > _DIFF_MAX_BYTES:
                truncated = text.encode("utf-8")[:_DIFF_MAX_BYTES].decode("utf-8", errors="replace")
                text = truncated + "\n\n（已截断，diff 过长）"
            return (text, None)
    except Exception as exc:
        return (None, str(exc))


class EvolutionAgent:
    def _build_payload(
        self,
        task_id: str,
        prompt: str,
        diff_content: str | None = None,
        diff_error: str | None = None,
    ) -> dict[str, Any]:
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
            pr_line = ""
            if isinstance(pr_context, dict):
                pr_line = (
                    f"\n\n仓库：{pr_context.get('repo', '')}，"
                    f"分支：{pr_context.get('branch', '')}，"
                    f"PR #{pr_context.get('pr_number', '')}，"
                    f"链接：{pr_context.get('pr_url', '')}"
                )
            full_prompt = instruction.strip() + pr_line
            if diff_content:
                full_prompt += f"\n\n## PR 代码变更\n\n```diff\n{diff_content}\n```"
            elif diff_error:
                full_prompt += f"\n\nPR diff 获取失败：{diff_error}"
            payload["prompt"] = full_prompt
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

        diff_content: str | None = None
        diff_error: str | None = None
        try:
            parsed = json.loads(prompt) if isinstance(prompt, str) else {}
            if isinstance(parsed, dict):
                pr_context = parsed.get("pr_context")
                if isinstance(pr_context, dict):
                    repo = pr_context.get("repo", "")
                    pr_number = pr_context.get("pr_number", "")
                    if repo and pr_number is not None:
                        diff_content, diff_error = await _fetch_pr_diff(repo, pr_number)
        except Exception:
            pass

        payload = self._build_payload(
            task_id, prompt, diff_content=diff_content, diff_error=diff_error
        )

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{url}/run",
                json=payload,
            ) as resp:
                if resp.status_code == 403:
                    yield {"type": "worker_start", "task_id": task_id}
                    yield {
                        "type": "worker_done",
                        "task_id": task_id,
                        "result": "演化功能已关闭，请在设置中开启演化。",
                    }
                    return
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        yield json.loads(line[6:])
