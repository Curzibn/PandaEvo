from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.config import MCPServerConfig, load_mcp_servers
from app.db import McpServer, async_session
from app.mcp.builtin import BUILTIN_SERVERS
from app.mcp.client import HttpMCPClient, StdioMCPClient
from app.mcp.manager import (
    add_server,
    get_all_server_names,
    get_mcp_clients,
    get_server_error,
    get_server_source,
    reconnect_server,
    remove_server,
)

router = APIRouter(prefix="/mcp", tags=["mcp"])


class McpServerOut(BaseModel):
    name: str
    source: Literal["builtin", "yaml", "db"]
    transport: Literal["stdio", "http"]
    command: str | None = None
    args: list[str] = []
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    status: Literal["connected", "disconnected", "error"]
    tool_count: int = 0
    error: str | None = None
    editable: bool


class McpServerCreate(BaseModel):
    name: str
    command: str | None = None
    args: list[str] = []
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None

    def validate_transport(self) -> None:
        if not self.url and not self.command:
            raise HTTPException(status_code=422, detail="Either 'command' (stdio) or 'url' (http) is required")


class McpServerUpdate(BaseModel):
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None


def _build_server_out(name: str) -> McpServerOut:
    clients = get_mcp_clients()
    source = get_server_source(name) or "db"
    error = get_server_error(name)

    client = clients.get(name)
    if client:
        status: Literal["connected", "disconnected", "error"] = "connected"
        tool_count = len(client.get_tools())
        transport: Literal["stdio", "http"] = "http" if isinstance(client, HttpMCPClient) else "stdio"
        command = client._server_params.command if isinstance(client, StdioMCPClient) else None
        args = list(client._server_params.args or []) if isinstance(client, StdioMCPClient) else []
        url = client._url if isinstance(client, HttpMCPClient) else None
    else:
        status = "error" if error else "disconnected"
        tool_count = 0
        transport = "stdio"
        command = None
        args = []
        url = None

    return McpServerOut(
        name=name,
        source=source,
        transport=transport,
        command=command,
        args=args,
        url=url,
        status=status,
        tool_count=tool_count,
        error=error,
        editable=(source == "db"),
    )


def _all_known_names() -> list[str]:
    builtin_names = {s.name for s in BUILTIN_SERVERS}
    runtime_names = get_all_server_names()
    return list(builtin_names | runtime_names)


@router.get("/servers", response_model=list[McpServerOut])
async def list_mcp_servers() -> list[McpServerOut]:
    async with async_session() as session:
        rows = await session.scalars(select(McpServer))
        db_names = {row.name for row in rows}
    
    yaml_configs = load_mcp_servers()
    yaml_names = {cfg.name for cfg in yaml_configs}
    
    all_names = yaml_names | db_names
    
    builtin_names = {s.name for s in BUILTIN_SERVERS}
    all_names = all_names - builtin_names
    
    return [_build_server_out(n) for n in sorted(all_names)]


@router.post("/servers", response_model=McpServerOut, status_code=201)
async def create_mcp_server(body: McpServerCreate) -> McpServerOut:
    body.validate_transport()
    clients = get_mcp_clients()
    if body.name in clients or get_server_source(body.name):
        raise HTTPException(status_code=409, detail=f"MCP server '{body.name}' already exists")

    async with async_session() as session:
        existing = await session.scalar(select(McpServer).where(McpServer.name == body.name))
        if existing:
            raise HTTPException(status_code=409, detail=f"MCP server '{body.name}' already exists")
        row = McpServer(
            name=body.name,
            command=body.command,
            args=body.args,
            env=body.env,
            url=body.url,
            headers=body.headers,
            enabled=True,
        )
        session.add(row)
        await session.commit()

    cfg = MCPServerConfig(
        name=body.name,
        command=body.command,
        args=body.args,
        env=body.env,
        url=body.url,
        headers=body.headers,
    )
    await add_server(cfg)
    return _build_server_out(body.name)


@router.put("/servers/{name}", response_model=McpServerOut)
async def update_mcp_server(name: str, body: McpServerUpdate) -> McpServerOut:
    source = get_server_source(name)
    if source and source != "db":
        raise HTTPException(status_code=403, detail=f"MCP server '{name}' is read-only (source: {source})")

    async with async_session() as session:
        row = await session.scalar(select(McpServer).where(McpServer.name == name))
        if not row:
            raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")
        if body.command is not None:
            row.command = body.command
        if body.args is not None:
            row.args = body.args
        if body.env is not None:
            row.env = body.env
        if body.url is not None:
            row.url = body.url
        if body.headers is not None:
            row.headers = body.headers
        await session.commit()
        await session.refresh(row)

    cfg = MCPServerConfig(
        name=name,
        command=row.command,
        args=row.args or [],
        env=row.env,
        url=row.url,
        headers=row.headers,
    )
    await add_server(cfg)
    return _build_server_out(name)


@router.delete("/servers/{name}", status_code=204)
async def delete_mcp_server(name: str) -> None:
    source = get_server_source(name)
    if source and source != "db":
        raise HTTPException(status_code=403, detail=f"MCP server '{name}' is read-only (source: {source})")

    async with async_session() as session:
        result = await session.execute(delete(McpServer).where(McpServer.name == name))
        if result.rowcount == 0 and name not in get_mcp_clients():
            raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")
        await session.commit()

    await remove_server(name)


@router.post("/servers/{name}/reconnect", response_model=McpServerOut)
async def reconnect_mcp_server(name: str) -> McpServerOut:
    source = get_server_source(name)
    if source == "builtin":
        raise HTTPException(status_code=403, detail=f"MCP server '{name}' is builtin and cannot be reconnected via API")
    
    if name not in get_all_server_names() and name not in get_mcp_clients():
        raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")
    await reconnect_server(name)
    return _build_server_out(name)
