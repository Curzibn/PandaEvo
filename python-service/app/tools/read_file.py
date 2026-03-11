from __future__ import annotations

from pathlib import Path
from typing import Any

from app.tools._utils import safe_path
from app.tools.base import ToolDef


class ReadFileTool(ToolDef):
    name = "read_file"
    description = "Read the contents of a file at the given path (relative to workspace root). Returns the file content as a string."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to the file"},
            "offset": {"type": "integer", "description": "Start line number (1-indexed, optional)"},
            "limit": {"type": "integer", "description": "Number of lines to read (optional)"},
        },
        "required": ["path"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        target = safe_path(args["path"])
        if not target.exists():
            return f"Error: file not found: {args['path']}"
        lines = target.read_text(encoding="utf-8").splitlines()
        offset = int(args.get("offset") or 1) - 1
        limit = args.get("limit")
        selected = lines[offset:] if limit is None else lines[offset: offset + int(limit)]
        return "\n".join(f"{offset + i + 1}|{line}" for i, line in enumerate(selected))


read_file_tool = ReadFileTool()
