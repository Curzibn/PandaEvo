from __future__ import annotations

from pathlib import Path
from typing import Any

from app.tools._utils import safe_write_path
from app.tools.base import ToolDef


class EditFileTool(ToolDef):
    name = "edit_file"
    description = "Replace the first occurrence of old_string with new_string in a file. The file must already exist."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to the file"},
            "old_string": {"type": "string", "description": "Exact string to find and replace"},
            "new_string": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        target = safe_write_path(args["path"])
        if not target.exists():
            return f"Error: file not found: {args['path']}"
        original = target.read_text(encoding="utf-8")
        old = args["old_string"]
        if old not in original:
            return f"Error: old_string not found in {args['path']}"
        updated = original.replace(old, args["new_string"], 1)
        target.write_text(updated, encoding="utf-8")
        return f"Replaced 1 occurrence in {args['path']}"


edit_file_tool = EditFileTool()
