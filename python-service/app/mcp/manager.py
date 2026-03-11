from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.config import MCPServerConfig, load_mcp_builtin_config, load_mcp_servers
from app.db import McpServer, async_session
from app.logger import get_logger
from app.mcp.builtin import BUILTIN_SERVERS
from app.mcp.client import MCPClient

logger = get_logger(__name__)

_clients: dict[str, MCPClient] = {}
_sources: dict[str, str] = {}
_errors: dict[str, str] = {}


def _make_client(cfg: MCPServerConfig) -> MCPClient:
    return MCPClient.create(
        cfg.name,
        command=cfg.command,
        args=cfg.args,
        env=cfg.env,
        url=cfg.url,
        headers=cfg.headers,
    )


async def _connect_server(cfg: MCPServerConfig, source: str) -> None:
    from app.tools import register_mcp_server_tools

    name = cfg.name
    _errors.pop(name, None)
    client = _make_client(cfg)
    try:
        await client.connect()
        _clients[name] = client
        _sources[name] = source
        register_mcp_server_tools(name, client)
        logger.info("MCP server '%s' (%s) connected", name, source)
    except Exception as exc:
        _errors[name] = str(exc)
        logger.exception("Failed to connect MCP server '%s' (%s): %s", name, source, exc)


async def _disconnect_server(name: str) -> None:
    from app.tools import unregister_mcp_server_tools

    unregister_mcp_server_tools(name)
    client = _clients.pop(name, None)
    _sources.pop(name, None)
    _errors.pop(name, None)
    if client:
        try:
            await client.disconnect()
            logger.info("MCP server '%s' disconnected", name)
        except Exception as exc:
            logger.exception("Error disconnecting MCP server '%s': %s", name, exc)


async def _load_db_servers() -> list[MCPServerConfig]:
    try:
        async with async_session() as session:
            rows = await session.scalars(select(McpServer).where(McpServer.enabled == True))
            return [
                MCPServerConfig(
                    name=row.name,
                    command=row.command,
                    args=row.args or [],
                    env=row.env,
                    url=row.url,
                    headers=row.headers,
                )
                for row in rows
            ]
    except Exception as exc:
        logger.exception("Failed to load MCP servers from DB: %s", exc)
        return []


async def initialize_mcp_servers() -> None:
    builtin_cfg = load_mcp_builtin_config()
    disabled = set(builtin_cfg.disabled)

    if builtin_cfg.enabled:
        for cfg in BUILTIN_SERVERS:
            if cfg.name not in disabled:
                await _connect_server(cfg, "builtin")

    for cfg in load_mcp_servers():
        if cfg.name not in _clients:
            await _connect_server(cfg, "yaml")

    for cfg in await _load_db_servers():
        if cfg.name not in _clients:
            await _connect_server(cfg, "db")

    total = len(_clients)
    if total == 0:
        logger.info("No MCP servers connected")
    else:
        logger.info("Initialized %d MCP server(s)", total)


async def shutdown_mcp_servers() -> None:
    for name in list(_clients.keys()):
        await _disconnect_server(name)


async def add_server(cfg: MCPServerConfig) -> None:
    if cfg.name in _clients:
        await _disconnect_server(cfg.name)
    await _connect_server(cfg, "db")


async def remove_server(name: str) -> None:
    await _disconnect_server(name)


async def reconnect_server(name: str) -> bool:
    client = _clients.get(name)
    source = _sources.get(name, "db")
    if not client:
        return False
    cfg_attrs: dict[str, Any] = {}
    if isinstance(client, MCPClient):
        from app.mcp.client import StdioMCPClient, HttpMCPClient
        if isinstance(client, StdioMCPClient):
            cfg_attrs = dict(command=client._server_params.command,
                             args=list(client._server_params.args or []),
                             env=dict(client._server_params.env or {}))
        elif isinstance(client, HttpMCPClient):
            cfg_attrs = dict(url=client._url, headers=dict(client._headers))
    await _disconnect_server(name)
    cfg = MCPServerConfig(name=name, **cfg_attrs)
    await _connect_server(cfg, source)
    return name in _clients


def get_mcp_clients() -> dict[str, MCPClient]:
    return _clients.copy()


def get_server_source(name: str) -> str | None:
    return _sources.get(name)


def get_server_error(name: str) -> str | None:
    return _errors.get(name)


def get_all_server_names() -> set[str]:
    return set(_clients.keys()) | set(_errors.keys())
