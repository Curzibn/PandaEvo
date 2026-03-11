from __future__ import annotations

from app.config import MCPServerConfig

BUILTIN_SERVERS: list[MCPServerConfig] = [
    MCPServerConfig(
        name="fetch",
        command="uvx",
        args=["mcp-server-fetch"],
    ),
]
