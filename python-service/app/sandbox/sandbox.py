from __future__ import annotations

import time
from typing import Any

import docker
from docker.models.containers import Container

from app.logger import get_logger

logger = get_logger(__name__)


class SessionSandbox:
    def __init__(
        self,
        container: Container,
        session_id: str,
        workspace_path: str,
    ):
        self.container = container
        self.session_id = session_id
        self.workspace_path = workspace_path
        self.last_used_at = time.time()

    async def exec(self, command: str, timeout: int = 30) -> str:
        self.last_used_at = time.time()
        try:
            import asyncio
            result = await asyncio.to_thread(
                self.container.exec_run,
                command,
                workdir="/workspace",
                timeout=timeout,
                demux=True,
            )
            exit_code, (stdout, stderr) = result
            output = (stdout or b"").decode("utf-8", errors="replace") + (
                stderr or b""
            ).decode("utf-8", errors="replace")
            output = output.strip()
            if not output:
                return f"(exit code {exit_code})"
            return output
        except docker.errors.APIError as e:
            logger.error("Docker exec error for session %s: %s", self.session_id, e)
            return f"Error: Docker exec failed: {e}"
        except Exception as e:
            logger.exception("Unexpected error executing command in sandbox %s", self.session_id)
            return f"Error: {e!r}"

    async def cleanup(self) -> None:
        try:
            import asyncio
            await asyncio.to_thread(self.container.stop, timeout=5)
            await asyncio.to_thread(self.container.remove)
            logger.info("Cleaned up sandbox container for session %s", self.session_id)
        except docker.errors.NotFound:
            logger.debug("Container already removed for session %s", self.session_id)
        except Exception as e:
            logger.exception("Error cleaning up sandbox for session %s", self.session_id)
            raise

    def is_idle(self, timeout_seconds: int) -> bool:
        return time.time() - self.last_used_at > timeout_seconds
