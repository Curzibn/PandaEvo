from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import docker
from docker.errors import DockerException

from app.config import get_workspace_root, get_sandbox_config
from app.logger import get_logger
from app.sandbox.sandbox import SessionSandbox

logger = get_logger(__name__)


class SandboxManager:
    _instance: SandboxManager | None = None
    _lock = asyncio.Lock()

    def __new__(cls) -> SandboxManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._client: docker.DockerClient | None = None
        self._sandboxes: dict[str, SessionSandbox] = {}
        self._cleanup_task: asyncio.Task[None] | None = None
        self._initialized = True

    async def _ensure_client(self) -> docker.DockerClient:
        if self._client is None:
            try:
                self._client = docker.from_env()
                await asyncio.to_thread(self._client.ping)
                logger.info("Docker client initialized successfully")
            except DockerException as e:
                logger.error("Failed to connect to Docker daemon: %s", e)
                raise RuntimeError("Docker daemon not available") from e
        return self._client

    async def get_or_create(self, session_id: str) -> SessionSandbox:
        if session_id in self._sandboxes:
            sandbox = self._sandboxes[session_id]
            try:
                await asyncio.to_thread(sandbox.container.reload)
                return sandbox
            except docker.errors.NotFound:
                del self._sandboxes[session_id]

        config = get_sandbox_config()
        client = await self._ensure_client()

        session_workspace = get_workspace_root()
        session_workspace.mkdir(parents=True, exist_ok=True)

        container_name = f"pandaevo-sandbox-{session_id}"

        host_config = client.api.create_host_config(
            binds=[f"{session_workspace}:/workspace:rw"],
            mem_limit=config.mem_limit,
            nano_cpus=config.nano_cpus,
            pids_limit=config.pids_limit,
            network_mode=config.network_mode,
            auto_remove=False,
        )

        create_kwargs: dict[str, Any] = {
            "image": config.image,
            "name": container_name,
            "host_config": host_config,
            "detach": True,
            "stdin_open": True,
            "tty": True,
            "command": ["/bin/bash"],
        }

        try:
            container = await asyncio.to_thread(client.containers.create, **create_kwargs)
            await asyncio.to_thread(container.start)
            sandbox = SessionSandbox(
                container=container,
                session_id=session_id,
                workspace_path=str(session_workspace),
            )
            self._sandboxes[session_id] = sandbox
            logger.info("Created sandbox container for session %s", session_id)

            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_idle_loop())

            return sandbox
        except docker.errors.ImageNotFound:
            logger.error("Sandbox image %s not found. Please build it first.", config.image)
            raise RuntimeError(f"Sandbox image {config.image} not found") from None
        except Exception as e:
            logger.exception("Failed to create sandbox for session %s", session_id)
            raise RuntimeError(f"Failed to create sandbox: {e}") from e

    async def exec(self, session_id: str, command: str, timeout: int = 30) -> str:
        sandbox = await self.get_or_create(session_id)
        return await sandbox.exec(command, timeout=timeout)

    async def cleanup(self, session_id: str) -> None:
        if session_id not in self._sandboxes:
            return
        sandbox = self._sandboxes[session_id]
        await sandbox.cleanup()
        del self._sandboxes[session_id]

    async def cleanup_idle(self) -> None:
        config = get_sandbox_config()
        timeout = config.idle_timeout_s
        idle_sessions = [
            session_id
            for session_id, sandbox in self._sandboxes.items()
            if sandbox.is_idle(timeout)
        ]
        for session_id in idle_sessions:
            logger.info("Cleaning up idle sandbox for session %s", session_id)
            await self.cleanup(session_id)

    async def _cleanup_idle_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(300)
                await self.cleanup_idle()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in cleanup_idle_loop")

    async def shutdown(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        for session_id in list(self._sandboxes.keys()):
            await self.cleanup(session_id)

        if self._client:
            self._client.close()
            self._client = None


sandbox_manager = SandboxManager()
