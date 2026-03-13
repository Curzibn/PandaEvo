from __future__ import annotations

from pathlib import Path

from app.config import get_repo_sync_branch
from app.gitops import run_git
from app.logger import get_logger

_WORKSPACE_APPS = Path("/workspace/apps")

logger = get_logger(__name__)


async def post_merge_sync(repo: str) -> None:
    if repo != "apps":
        raise ValueError(f"post_merge_sync only supports repo='apps', got {repo!r}")
    if not (_WORKSPACE_APPS / ".git").exists():
        raise RuntimeError("/workspace/apps is not a git repository")
    branch = get_repo_sync_branch()
    rc, out = await run_git(["pull", "--ff-only", "origin", branch], _WORKSPACE_APPS)
    if rc != 0:
        raise RuntimeError(f"git pull failed: {out}")
    logger.info("post merge sync done repo=apps")


async def startup_sync_repositories() -> None:
    pass
