from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import get_workspace_root
from app.tools._utils import safe_path
from app.tools.base import ToolDef

_HIDDEN_PREFIXES = (".", "__pycache__")


def _build_tree(path: Path, root: Path, depth: int, include_hidden: bool) -> dict[str, Any]:
    node: dict[str, Any] = {"name": path.name, "type": "dir" if path.is_dir() else "file"}
    if path.is_dir() and depth > 0:
        children = []
        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            entries = []
        for entry in entries:
            if not include_hidden and any(entry.name.startswith(p) for p in _HIDDEN_PREFIXES):
                continue
            children.append(_build_tree(entry, root, depth - 1, include_hidden))
        node["children"] = children
    return node


def build_dir_tree(
    rel: str = ".",
    depth: int = 2,
    include_hidden: bool = False,
    excluded: set[str] | None = None,
) -> dict[str, Any]:
    root = get_workspace_root()
    target = safe_path(rel)
    node = _build_tree(target, root, depth, include_hidden)
    if excluded and target == root and "children" in node:
        node["children"] = [c for c in node["children"] if c["name"] not in excluded]
    return node


class ListDirTool(ToolDef):
    name = "list_dir"
    description = "List the directory structure of a path (relative to workspace root) as a JSON tree. Useful for understanding project layout."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to the directory (default: workspace root)"},
            "depth": {"type": "integer", "description": "Maximum recursion depth (default: 2)"},
            "include_hidden": {"type": "boolean", "description": "Include hidden files/dirs starting with '.' (default: false)"},
        },
        "required": [],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        rel = args.get("path") or "."
        depth = int(args.get("depth") or 2)
        include_hidden = bool(args.get("include_hidden", False))
        tree = build_dir_tree(rel, depth, include_hidden)
        return json.dumps(tree, ensure_ascii=False, indent=2)


list_dir_tool = ListDirTool()
