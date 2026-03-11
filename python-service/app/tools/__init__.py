from __future__ import annotations

from typing import Any

from app.tools.base import ToolDef
from app.tools.edit_file import edit_file_tool
from app.tools.exec_shell import exec_shell_tool
from app.tools.list_dir import list_dir_tool
from app.tools.read_file import read_file_tool
from app.tools.search_files import search_files_tool
from app.tools.web_fetch import web_fetch_tool
from app.tools.write_file import write_file_tool

TOOLS_REGISTRY: list[ToolDef] = [
    read_file_tool,
    write_file_tool,
    edit_file_tool,
    exec_shell_tool,
    list_dir_tool,
    search_files_tool,
    web_fetch_tool,
]

_TOOL_MAP: dict[str, ToolDef] = {t.name: t for t in TOOLS_REGISTRY}
_MCP_SERVER_TOOLS: dict[str, list[str]] = {}


def register_mcp_server_tools(server_name: str, client: Any) -> None:
    tools = client.get_tools()
    if not tools:
        return

    from app.mcp.adapter import MCPToolAdapter

    registered: list[str] = []
    for tool_name, tool_def in tools.items():
        adapter_name = f"mcp_{server_name}_{tool_name}"
        if adapter_name not in _TOOL_MAP:
            adapter = MCPToolAdapter(server_name, tool_name, tool_def, client)
            TOOLS_REGISTRY.append(adapter)
            _TOOL_MAP[adapter_name] = adapter
        registered.append(adapter_name)

    _MCP_SERVER_TOOLS[server_name] = registered


def unregister_mcp_server_tools(server_name: str) -> None:
    for adapter_name in _MCP_SERVER_TOOLS.pop(server_name, []):
        tool = _TOOL_MAP.pop(adapter_name, None)
        if tool is not None and tool in TOOLS_REGISTRY:
            TOOLS_REGISTRY.remove(tool)


def get_tool_schemas(allowed: set[str] | None = None) -> list[dict[str, Any]]:
    tools = TOOLS_REGISTRY if allowed is None else [t for t in TOOLS_REGISTRY if t.name in allowed]
    return [t.to_schema() for t in tools]


async def dispatch(name: str, args: dict[str, Any], allowed: set[str] | None = None) -> str:
    if allowed is not None and name not in allowed:
        return f"Error: tool '{name}' is not available in current context"
    tool = _TOOL_MAP.get(name)
    if tool is None:
        return f"Error: unknown tool '{name}'"
    try:
        return await tool.execute(args)
    except PermissionError as exc:
        return f"Error: {exc}"
    except Exception as exc:
        return f"Error executing {name}: {exc}"


def get_exposed_tool_schemas() -> list[dict[str, Any]]:
    return [t.to_schema() for t in TOOLS_REGISTRY if t.name.startswith("mcp_")]
