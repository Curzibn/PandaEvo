from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path

from app.config import get_workspace_root

session_ctx: ContextVar[str | None] = ContextVar("session_id", default=None)


def _get_session_workspace_root() -> Path:
    root = get_workspace_root()
    session_id = session_ctx.get()
    if session_id:
        return root / session_id
    return root


def safe_path(rel: str) -> Path:
    """Resolve a path for read access. Boundary is workspace root, allowing access to code/ and other shared directories."""
    ws_root = get_workspace_root().resolve()
    target = (ws_root / rel).resolve()
    if not str(target).startswith(str(ws_root)):
        raise PermissionError(f"Access denied: '{rel}' is outside workspace root.")
    return target


def safe_write_path(rel: str) -> Path:
    """Resolve a path for write access. Resolves relative to session root to maintain per-session isolation."""
    session_root = _get_session_workspace_root().resolve()
    ws_root = get_workspace_root().resolve()
    target = (session_root / rel).resolve()
    if not str(target).startswith(str(ws_root)):
        raise PermissionError(f"Access denied: '{rel}' is outside workspace root.")
    return target
