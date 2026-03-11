from __future__ import annotations

from pathlib import Path
from typing import Any

from app.tools._utils import safe_write_path
from app.tools.base import ToolDef


class WriteFileTool(ToolDef):
    name = "write_file"
    description = "Write (overwrite) content to a file at the given path (relative to workspace root). Creates parent directories if needed."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to the file"},
            "content": {"type": "string", "description": "Full content to write"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        target = safe_write_path(args["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(args["content"], encoding="utf-8")
        return f"Written {len(args['content'])} characters to {args['path']}"


write_file_tool = WriteFileTool()
