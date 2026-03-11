from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.config import get_workspace_root
from app.tools._utils import safe_path
from app.tools.base import ToolDef

_MAX_RESULTS = 200
_TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".md", ".txt", ".html", ".css", ".env", ".sh", ".sql",
    ".cfg", ".ini", ".csv", ".xml",
}


def _is_text(path: Path) -> bool:
    return path.suffix.lower() in _TEXT_SUFFIXES


def _search_by_name(root: Path, pattern: str) -> list[str]:
    results = []
    for match in root.rglob(pattern):
        results.append(str(match.relative_to(root)))
        if len(results) >= _MAX_RESULTS:
            break
    return results


def _search_by_content(root: Path, keyword: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file() or not _is_text(path):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if keyword in line:
                results.append({
                    "path": str(path.relative_to(root)),
                    "line": i,
                    "content": line.strip()[:200],
                })
                if len(results) >= _MAX_RESULTS:
                    return results
    return results


class SearchFilesTool(ToolDef):
    name = "search_files"
    description = (
        "Search for files by name (glob pattern) or by content (keyword). "
        "Returns up to 50 matches. Use type='name' for filename patterns (e.g. '*.py'), "
        "type='content' to search inside file contents."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern (for name search) or keyword string (for content search)"},
            "path": {"type": "string", "description": "Root directory to search in, relative to workspace (default: workspace root)"},
            "type": {"type": "string", "enum": ["name", "content"], "description": "Search mode: 'name' matches filenames, 'content' searches inside files (default: name)"},
        },
        "required": ["pattern"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        rel = args.get("path") or "."
        root = safe_path(rel)
        pattern = args["pattern"]
        mode = args.get("type", "name")

        if mode == "content":
            loop = asyncio.get_event_loop()
            matches = await loop.run_in_executor(None, _search_by_content, root, pattern)
            if not matches:
                return "No matches found."
            lines = [f"{m['path']}:{m['line']}: {m['content']}" for m in matches]
            suffix = f"\n(showing first {_MAX_RESULTS})" if len(matches) == _MAX_RESULTS else ""
            return "\n".join(lines) + suffix
        else:
            workspace = get_workspace_root()
            matches = _search_by_name(root, pattern)
            if not matches:
                return "No matches found."
            suffix = f"\n(showing first {_MAX_RESULTS})" if len(matches) == _MAX_RESULTS else ""
            return "\n".join(matches) + suffix


search_files_tool = SearchFilesTool()
