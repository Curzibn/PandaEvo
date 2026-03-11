from __future__ import annotations

import httpx

from app.config import get_gitea_org, get_gitea_token, get_gitea_url
from app.gitops import build_http_auth_url


def _headers(include_auth: bool = True) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = get_gitea_token().strip()
    if include_auth and token:
        headers["Authorization"] = f"token {token}"
    return headers


def _parse_error(resp: httpx.Response) -> str:
    try:
        data = resp.json()
    except Exception:
        text = resp.text.strip()
        return text or f"HTTP {resp.status_code}"
    if isinstance(data, dict):
        msg = data.get("message")
        if isinstance(msg, str) and msg:
            return msg
    return str(data)


def _extract_repo_names(payload: object) -> list[str]:
    if isinstance(payload, list):
        return [r["name"] for r in payload if isinstance(r, dict) and isinstance(r.get("name"), str) and r.get("name")]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [r["name"] for r in data if isinstance(r, dict) and isinstance(r.get("name"), str) and r.get("name")]
    return []


async def _fetch_repo_names(client: httpx.AsyncClient, url: str, include_auth: bool) -> tuple[int, list[str], str]:
    resp = await client.get(url, headers=_headers(include_auth), params={"limit": 200})
    names = _extract_repo_names(resp.json()) if resp.headers.get("content-type", "").startswith("application/json") else []
    return resp.status_code, names, _parse_error(resp)


async def list_repos() -> dict:
    owner = get_gitea_org()
    base = get_gitea_url().rstrip("/")
    urls = [
        ("org", f"{base}/api/v1/orgs/{owner}/repos"),
        ("user", f"{base}/api/v1/users/{owner}/repos"),
    ]

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            attempted: list[str] = []
            for owner_type, url in urls:
                status, repos, err = await _fetch_repo_names(client, url, include_auth=True)
                attempted.append(f"{owner_type}:{status}")
                if status == 200:
                    return {"success": True, "owner": owner, "owner_type": owner_type, "repos": sorted(set(repos))}
                if status == 404:
                    continue
                if status == 403 and "required scope" in err:
                    fallback_status, fallback_repos, fallback_err = await _fetch_repo_names(client, url, include_auth=False)
                    attempted.append(f"{owner_type}_no_auth:{fallback_status}")
                    if fallback_status == 200:
                        return {
                            "success": True,
                            "owner": owner,
                            "owner_type": owner_type,
                            "repos": sorted(set(fallback_repos)),
                            "warning": "token missing read scopes; returning repositories visible without auth",
                        }
                    return {
                        "success": False,
                        "error": f"{owner_type} endpoint forbidden with auth and failed without auth: {fallback_err}",
                        "attempted": attempted,
                    }
                return {"success": False, "error": f"{owner_type} endpoint failed: {err}", "attempted": attempted}
            return {
                "success": False,
                "error": f"owner '{owner}' not found as org or user",
                "attempted": attempted,
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


def build_repo_clone_url(repo: str) -> str:
    base_url = get_gitea_url().rstrip("/")
    token = get_gitea_token().strip()
    if token:
        base_url = build_http_auth_url(base_url, "token", token)
    org = get_gitea_org()
    return f"{base_url}/{org}/{repo}.git"
