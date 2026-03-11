from __future__ import annotations

import httpx

from app.config import get_gitea_org, get_gitea_token, get_gitea_url


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"token {get_gitea_token()}",
        "Content-Type": "application/json",
    }


async def list_repos() -> dict:
    owner = get_gitea_org()
    url = f"{get_gitea_url()}/api/v1/users/{owner}/repos"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(url, headers=_headers(), params={"limit": 50})
            resp.raise_for_status()
            repos = resp.json()
            return {
                "success": True,
                "owner": owner,
                "repos": [r["name"] for r in repos if isinstance(r, dict)],
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}


async def create_pr(repo: str, branch: str, title: str, body: str) -> dict:
    url = f"{get_gitea_url()}/api/v1/repos/{get_gitea_org()}/{repo}/pulls"
    payload = {"head": branch, "base": "main", "title": title, "body": body}
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(url, json=payload, headers=_headers())
            resp.raise_for_status()
            data = resp.json()
            return {
                "success": True,
                "pr_number": data.get("number"),
                "url": data.get("html_url"),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}
