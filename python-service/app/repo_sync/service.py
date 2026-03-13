from __future__ import annotations

import shutil
from pathlib import Path

from app.coder.gitea import build_repo_clone_url
from app.config import (
    get_repo_sync_branch,
    get_repo_sync_enabled,
    get_repo_sync_repos,
    get_repo_sync_root,
)
from app.gitops import run_git
from app.logger import get_logger

_WORKSPACE_APPS = Path("/workspace/apps")

logger = get_logger(__name__)


async def ensure_repo_synced(repo: str, target_root: Path, branch: str) -> None:
    repo_path = target_root / repo
    if not repo_path.exists():
        clone_url = build_repo_clone_url(repo)
        rc, out = await run_git(
            ["clone", "--branch", branch, "--single-branch", clone_url, str(repo_path)],
            target_root,
        )
        if rc != 0:
            raise RuntimeError(f"clone failed for {repo}: {out}")
        logger.info("repo sync clone success repo=%s branch=%s", repo, branch)
        return

    rc, out = await run_git(["rev-parse", "--is-inside-work-tree"], repo_path)
    if rc != 0:
        raise RuntimeError(f"target is not a git repository for {repo}: {out}")

    rc, out = await run_git(["pull", "--ff-only", "origin", branch], repo_path)
    if rc != 0:
        raise RuntimeError(f"pull failed for {repo}: {out}")
    logger.info("repo sync pull success repo=%s branch=%s", repo, branch)


async def post_merge_sync(repo: str) -> None:
    target_root = get_repo_sync_root()
    branch = get_repo_sync_branch()
    await ensure_repo_synced(repo, target_root, branch)

    src = target_root / repo
    dst = _WORKSPACE_APPS / repo
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    logger.info("post merge sync done repo=%s", repo)


async def startup_sync_repositories() -> None:
    if not get_repo_sync_enabled():
        logger.info("repo sync disabled")
        return

    repos = get_repo_sync_repos()
    if not repos:
        logger.info("repo sync skipped because repos is empty")
        return

    target_root = get_repo_sync_root()
    target_root.mkdir(parents=True, exist_ok=True)
    branch = get_repo_sync_branch()

    logger.info(
        "repo sync start repos=%s target_root=%s branch=%s",
        ",".join(repos),
        target_root,
        branch,
    )
    for repo in repos:
        try:
            await ensure_repo_synced(repo, target_root, branch)
        except Exception as exc:
            logger.warning("repo sync failed repo=%s reason=%s", repo, exc)
    logger.info("repo sync done")
