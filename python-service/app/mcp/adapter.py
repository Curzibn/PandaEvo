from __future__ import annotations

from typing import Any

from app.mcp.client import MCPClient
from app.tools.base import ToolDef


class MCPToolAdapter(ToolDef):
    def __init__(self, server_name: str, tool_name: str, tool_def: dict[str, Any], client: MCPClient):
        self.server_name = server_name
        self._tool_name = tool_name
        self._tool_def = tool_def
        self._client = client

        self.name = f"mcp_{server_name}_{tool_name}"
        self.description = tool_def.get("description", tool_def.get("title", tool_name))

        input_schema = tool_def.get("inputSchema", {})
        self.parameters = self._convert_schema(input_schema)

    @staticmethod
    def _convert_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
        if not input_schema:
            return {"type": "object", "properties": {}, "required": []}

        result: dict[str, Any] = {
            "type": input_schema.get("type", "object"),
        }

        if "properties" in input_schema:
            result["properties"] = input_schema["properties"].copy()

        if "required" in input_schema:
            result["required"] = input_schema["required"]

        return result

    async def execute(self, args: dict[str, Any]) -> str:
        return await self._client.call_tool(self._tool_name, args)
