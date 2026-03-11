from __future__ import annotations

import json
from abc import ABC, abstractmethod
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.logger import get_logger

logger = get_logger(__name__)


class MCPClient(ABC):
    def __init__(self, name: str):
        self.name = name
        self.session: ClientSession | None = None
        self._exit_stack = AsyncExitStack()
        self._connected = False
        self._tools: dict[str, dict[str, Any]] = {}

    @abstractmethod
    async def _open_transport(self) -> tuple[Any, Any]: ...

    async def connect(self) -> None:
        if self._connected:
            return
        try:
            read, write = await self._open_transport()
            self.session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await self.session.initialize()
            self._connected = True
            logger.info("MCP server '%s' connected", self.name)
            await self._discover_tools()
        except Exception as exc:
            logger.exception("Failed to connect to MCP server '%s': %s", self.name, exc)
            await self.disconnect()
            raise

    async def _discover_tools(self) -> None:
        if not self.session:
            return
        try:
            response = await self.session.list_tools()
            self._tools = {tool.name: tool.model_dump() for tool in response.tools}
            logger.info("Discovered %d tools from MCP server '%s'", len(self._tools), self.name)
        except Exception as exc:
            logger.exception("Failed to discover tools from MCP server '%s': %s", self.name, exc)

    async def disconnect(self) -> None:
        if not self._connected:
            return
        try:
            await self._exit_stack.aclose()
        except Exception as exc:
            logger.exception("Error disconnecting from MCP server '%s': %s", self.name, exc)
        finally:
            self.session = None
            self._connected = False
            self._tools = {}

    def is_connected(self) -> bool:
        return self._connected

    def get_tools(self) -> dict[str, dict[str, Any]]:
        return self._tools.copy()

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        if not self.session:
            return f"Error: MCP server '{self.name}' is not connected"
        if name not in self._tools:
            return f"Error: tool '{name}' not found in MCP server '{self.name}'"
        try:
            result = await self.session.call_tool(name, arguments or {})
            if result.isError:
                error_msg = "Unknown error"
                if hasattr(result, "error") and result.error:
                    error_msg = str(result.error)
                elif hasattr(result, "content") and result.content:
                    error_msg = str(result.content)
                return f"Error calling tool '{name}': {error_msg}"
            if not result.content:
                return "(no result)"
            if isinstance(result.content, list):
                parts = []
                for item in result.content:
                    if hasattr(item, "text"):
                        parts.append(item.text)
                    elif hasattr(item, "model_dump"):
                        parts.append(item.model_dump())
                    else:
                        parts.append(str(item))
                return json.dumps(parts, ensure_ascii=False)
            if hasattr(result.content, "text"):
                return result.content.text
            if hasattr(result.content, "model_dump"):
                return json.dumps(result.content.model_dump(), ensure_ascii=False)
            return str(result.content)
        except Exception as exc:
            logger.exception("Error calling tool '%s' on MCP server '%s': %s", name, self.name, exc)
            return f"Error calling tool '{name}': {exc}"

    @classmethod
    def create(cls, name: str, *, command: str | None = None, args: list[str] | None = None,
               env: dict[str, str] | None = None, url: str | None = None,
               headers: dict[str, str] | None = None) -> "MCPClient":
        if url:
            return HttpMCPClient(name, url=url, headers=headers)
        if command:
            return StdioMCPClient(name, command=command, args=args or [], env=env)
        raise ValueError(f"MCP server '{name}' must specify either 'command' (stdio) or 'url' (http)")


class StdioMCPClient(MCPClient):
    def __init__(self, name: str, *, command: str, args: list[str], env: dict[str, str] | None):
        super().__init__(name)
        self._server_params = StdioServerParameters(command=command, args=args, env=env)

    async def _open_transport(self) -> tuple[Any, Any]:
        return await self._exit_stack.enter_async_context(stdio_client(self._server_params))


class HttpMCPClient(MCPClient):
    def __init__(self, name: str, *, url: str, headers: dict[str, str] | None):
        super().__init__(name)
        self._url = url
        self._headers = headers or {}

    async def _open_transport(self) -> tuple[Any, Any]:
        try:
            from mcp.client.streamable_http import streamablehttp_client
            return await self._exit_stack.enter_async_context(
                streamablehttp_client(self._url, headers=self._headers)
            )
        except ImportError:
            from mcp.client.sse import sse_client
            return await self._exit_stack.enter_async_context(
                sse_client(self._url, headers=self._headers)
            )
