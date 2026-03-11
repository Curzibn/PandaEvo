from __future__ import annotations

import json
import shutil
import tempfile
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from app.config import get_gitea_token
from app.coder.gitea import build_repo_clone_url
from app.gitops import run_git
from app.tools.base import ToolDef

_TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".md", ".txt", ".html", ".css", ".env", ".sh", ".sql",
    ".cfg", ".ini", ".csv", ".xml",
}

_MAX_RESULTS = 200

_repo_ctx: ContextVar[Path | None] = ContextVar("coder_repo", default=None)
_branch_ctx: ContextVar[str] = ContextVar("coder_branch", default="")
_repo_name_ctx: ContextVar[str] = ContextVar("coder_repo_name", default="")


def get_clone_root() -> Path | None:
    return _repo_ctx.get()


def cleanup_clone() -> None:
    root = _repo_ctx.get()
    if root is not None:
        parent = root.parent
        if parent.exists():
            shutil.rmtree(parent, ignore_errors=True)


def _safe_path(rel: str) -> Path:
    root = _repo_ctx.get()
    if root is None:
        raise ValueError("No repository cloned. Call clone_repo first.")
    target = (root / rel).resolve()
    if not str(target).startswith(str(root.resolve())):
        raise ValueError(f"Path escapes repository root: {rel}")
    return target


async def _run_git(*args: str, cwd: Path) -> tuple[int, str]:
    return await run_git(list(args), cwd)


def _build_tree(p: Path, depth: int) -> dict[str, Any]:
    node: dict[str, Any] = {"name": p.name, "type": "dir" if p.is_dir() else "file"}
    if p.is_dir() and depth > 0:
        try:
            entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except PermissionError:
            entries = []
        node["children"] = [
            _build_tree(e, depth - 1)
            for e in entries
            if not e.name.startswith((".", "__pycache__"))
        ]
    return node


class CloneRepoTool(ToolDef):
    name = "clone_repo"
    description = (
        "Clone a Gitea repository and create a new feature branch. "
        "Must be called before any file operations. "
        "Use list_repos first to discover the correct repository name."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository name as returned by list_repos (e.g. pandaevo)"},
            "branch": {"type": "string", "description": "New feature branch name (e.g. feat/add-caching)"},
        },
        "required": ["repo", "branch"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        repo = args["repo"].strip()
        branch = args["branch"].strip()

        token = get_gitea_token()
        if not token:
            return (
                "Error: GITEA_TOKEN is not configured. "
                "Set the GITEA_TOKEN environment variable and restart the service. "
                "Use list_repos to verify Gitea connectivity once the token is set."
            )

        clone_url = build_repo_clone_url(repo)

        tmp = Path(tempfile.mkdtemp(prefix="coder-"))
        repo_path = tmp / repo

        rc, out = await _run_git("clone", clone_url, str(repo_path), cwd=tmp)
        if rc != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            return f"Error: git clone failed:\n{out}"

        await _run_git("config", "user.email", "coder@pandaevo.local", cwd=repo_path)
        await _run_git("config", "user.name", "PandaEvo Coder", cwd=repo_path)

        rc, out = await _run_git("checkout", "-b", branch, cwd=repo_path)
        if rc != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            return f"Error: git checkout -b failed:\n{out}"

        _repo_ctx.set(repo_path)
        _branch_ctx.set(branch)
        _repo_name_ctx.set(repo)

        return f"Cloned '{repo}' and created branch '{branch}'"


class ReadFileTool(ToolDef):
    name = "read_file"
    description = "Read a file from the cloned repository. Returns line-numbered content."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to file"},
            "offset": {"type": "integer", "description": "Start line (1-indexed, optional)"},
            "limit": {"type": "integer", "description": "Number of lines to read (optional)"},
        },
        "required": ["path"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        try:
            target = _safe_path(args["path"])
        except ValueError as e:
            return f"Error: {e}"
        if not target.exists():
            return f"Error: file not found: {args['path']}"
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(0, int(args.get("offset") or 1) - 1)
        limit = args.get("limit")
        selected = lines[start:] if limit is None else lines[start: start + int(limit)]
        return "\n".join(f"{start + i + 1}|{line}" for i, line in enumerate(selected))


class ListDirTool(ToolDef):
    name = "list_dir"
    description = "List the directory structure of the cloned repository as a JSON tree."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to directory (default: repo root)"},
            "depth": {"type": "integer", "description": "Max recursion depth (default: 2)"},
        },
        "required": [],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        try:
            target = _safe_path(args.get("path") or ".")
        except ValueError as e:
            return f"Error: {e}"
        depth = int(args.get("depth") or 2)
        return json.dumps(_build_tree(target, depth), ensure_ascii=False, indent=2)


class SearchFilesTool(ToolDef):
    name = "search_files"
    description = (
        "Search files in the cloned repository by name (glob) or content (keyword). "
        "Use type='name' for filename patterns, type='content' for keyword search inside files."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern or keyword string"},
            "path": {"type": "string", "description": "Root directory to search (default: repo root)"},
            "type": {"type": "string", "enum": ["name", "content"], "description": "Search mode (default: name)"},
        },
        "required": ["pattern"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        try:
            root = _safe_path(args.get("path") or ".")
        except ValueError as e:
            return f"Error: {e}"

        pattern = args["pattern"]
        mode = args.get("type", "name")
        repo_root = _repo_ctx.get()

        if mode == "content":
            results: list[str] = []
            for p in root.rglob("*"):
                if not p.is_file() or p.suffix.lower() not in _TEXT_SUFFIXES:
                    continue
                try:
                    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
                except OSError:
                    continue
                for i, line in enumerate(lines, 1):
                    if pattern in line:
                        rel = str(p.relative_to(repo_root)) if repo_root else str(p)
                        results.append(f"{rel}:{i}: {line.strip()[:200]}")
                        if len(results) >= _MAX_RESULTS:
                            return "\n".join(results) + f"\n(showing first {_MAX_RESULTS})"
            return "\n".join(results) if results else "No matches found."

        matches: list[str] = []
        for m in root.rglob(pattern):
            rel = str(m.relative_to(repo_root)) if repo_root else str(m)
            matches.append(rel)
            if len(matches) >= _MAX_RESULTS:
                return "\n".join(matches) + f"\n(showing first {_MAX_RESULTS})"
        return "\n".join(matches) if matches else "No matches found."


class WriteFileTool(ToolDef):
    name = "write_file"
    description = "Create or overwrite a file in the cloned repository."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to file"},
            "content": {"type": "string", "description": "Full file content to write"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        try:
            target = _safe_path(args["path"])
        except ValueError as e:
            return f"Error: {e}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(args["content"], encoding="utf-8")
        return f"Written {len(args['content'])} characters to {args['path']}"


class EditFileTool(ToolDef):
    name = "edit_file"
    description = (
        "Replace a unique string in a file. old_str must appear exactly once."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to file"},
            "old_str": {"type": "string", "description": "Exact string to replace (must be unique in file)"},
            "new_str": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_str", "new_str"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        try:
            target = _safe_path(args["path"])
        except ValueError as e:
            return f"Error: {e}"
        if not target.exists():
            return f"Error: file not found: {args['path']}"
        content = target.read_text(encoding="utf-8")
        old_str = args["old_str"]
        count = content.count(old_str)
        if count == 0:
            return f"Error: old_str not found in {args['path']}"
        if count > 1:
            return f"Error: old_str appears {count} times in {args['path']}. Must be unique."
        target.write_text(content.replace(old_str, args["new_str"], 1), encoding="utf-8")
        return f"Replaced 1 occurrence in {args['path']}"


class CommitAndPushTool(ToolDef):
    name = "commit_and_push"
    description = "Stage all changes, commit, and push the branch to Gitea."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Commit message (Conventional Commits format recommended)"},
        },
        "required": ["message"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        root = _repo_ctx.get()
        branch = _branch_ctx.get()
        if root is None:
            return "Error: No repository cloned."
        if not branch:
            return "Error: No branch set."

        rc, out = await _run_git("add", "-A", cwd=root)
        if rc != 0:
            return f"Error: git add failed:\n{out}"

        rc, out = await _run_git("commit", "-m", args["message"], cwd=root)
        if rc != 0:
            if "nothing to commit" in out:
                return "Nothing to commit. No changes detected."
            return f"Error: git commit failed:\n{out}"

        rc, out = await _run_git("push", "origin", branch, cwd=root)
        if rc != 0:
            return f"Error: git push failed:\n{out}"

        return f"Committed and pushed branch '{branch}' successfully."


class ListReposTool(ToolDef):
    name = "list_repos"
    description = (
        "List all repositories available in the Gitea organization. "
        "Use this first to discover the correct repository names before calling clone_repo."
    )
    parameters: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

    async def execute(self, args: dict[str, Any]) -> str:
        from app.coder.gitea import list_repos as _list_repos

        result = await _list_repos()
        if result.get("success"):
            owner = result.get("owner", "")
            owner_type = result.get("owner_type", "unknown")
            repos = result["repos"]
            if not repos:
                return f"No repositories found under '{owner}' ({owner_type})."
            lines = [f"Owner: {owner} ({owner_type})"]
            warning = result.get("warning")
            if isinstance(warning, str) and warning:
                lines.append(f"Warning: {warning}")
            lines += ["Repositories:"] + [f"- {r}" for r in repos]
            return "\n".join(lines)
        attempted = result.get("attempted")
        attempted_text = f" attempted={attempted}" if attempted else ""
        return f"Error listing repos: {result.get('error')}{attempted_text}"


class CreatePRTool(ToolDef):
    name = "create_pr"
    description = (
        "Create a Pull Request on Gitea for the current branch. "
        "Call after commit_and_push. Only one PR per task."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "PR title"},
            "body": {"type": "string", "description": "PR description in markdown"},
        },
        "required": ["title", "body"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        from app.coder.gitea import create_pr as _create_pr

        repo = _repo_name_ctx.get()
        branch = _branch_ctx.get()
        if not repo:
            return "Error: No repository cloned."
        if not branch:
            return "Error: No branch set."

        result = await _create_pr(repo, branch, args["title"], args["body"])
        if result.get("success"):
            return f"PR #{result['pr_number']} created: {result['url']}"
        return f"Error creating PR: {result.get('error')}"


CODER_TOOLS: list[ToolDef] = [
    ListReposTool(),
    CloneRepoTool(),
    ReadFileTool(),
    ListDirTool(),
    SearchFilesTool(),
    WriteFileTool(),
    EditFileTool(),
    CommitAndPushTool(),
    CreatePRTool(),
]

_CODER_TOOL_MAP: dict[str, ToolDef] = {t.name: t for t in CODER_TOOLS}


async def dispatch_coder(name: str, args: dict[str, Any]) -> str:
    tool = _CODER_TOOL_MAP.get(name)
    if tool is None:
        return f"Error: unknown tool '{name}'"
    try:
        return await tool.execute(args)
    except Exception as exc:
        return f"Error executing {name}: {exc!r}"
