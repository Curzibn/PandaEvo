from __future__ import annotations

from typing import Any

from app.sandbox import sandbox_manager
from app.tools._utils import session_ctx
from app.tools.base import ToolDef

_TIMEOUT = 300

_BLOCKED_PREFIXES = (
    "docker ",
    "docker\t",
    "docker-compose",
    "sudo docker",
)


def _is_blocked(command: str) -> bool:
    normalized = command.strip().lower()
    return any(normalized.startswith(prefix) for prefix in _BLOCKED_PREFIXES)


class ExecShellTool(ToolDef):
    name = "exec_shell"
    description = "Execute a shell command in the workspace root directory. Returns combined stdout and stderr. Timeout is 300 seconds."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
        },
        "required": ["command"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        command = args["command"]

        if _is_blocked(command):
            return "Error: docker lifecycle commands are forbidden. Phase 2 infrastructure is exclusively managed by the Phase 1 bootstrap process."

        session_id = session_ctx.get() or "default"

        try:
            return await sandbox_manager.exec(session_id, command, timeout=_TIMEOUT)
        except RuntimeError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error: {e!r}"


exec_shell_tool = ExecShellTool()
