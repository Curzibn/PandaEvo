from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path

from app.config import get_workspace_root

session_ctx: ContextVar[str | None] = ContextVar("session_id", default=None)


def safe_path(rel: str) -> Path:
    ws_root = get_workspace_root().resolve()
    target = (ws_root / rel).resolve()
    if not str(target).startswith(str(ws_root)):
        raise PermissionError(f"Access denied: '{rel}' is outside workspace root.")
    return target


def safe_write_path(rel: str) -> Path:
    return safe_path(rel)
