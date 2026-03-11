from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit


async def run_git(args: list[str], cwd: Path) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return proc.returncode, stdout.decode("utf-8", errors="replace").strip()


def build_http_auth_url(base_url: str, username: str, password: str) -> str:
    parsed = urlsplit(base_url)
    auth = f"{quote(username, safe='')}:{quote(password, safe='')}"
    netloc = f"{auth}@{parsed.hostname or ''}"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
