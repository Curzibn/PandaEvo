from __future__ import annotations

from typing import Any

import httpx

from app.tools.base import ToolDef


class WebFetchTool(ToolDef):
    name = "web_fetch"
    description = (
        "Fetch content from a URL and return it as readable text. "
        "Fast HTTP fetch without JavaScript rendering. Use for simple doc sites. "
        "For JavaScript-heavy sites, use MCP bisheng read_url tool instead."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
        },
        "required": ["url"],
    }

    async def execute(self, args: dict[str, Any]) -> str:
        url = args["url"]
        if not url.startswith(("http://", "https://")):
            return f"Error: invalid URL '{url}' (must start with http:// or https://)"

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                response.raise_for_status()
                content = response.text

                if not content or len(content.strip()) < 100:
                    return f"[Empty or very short content from {url}. Consider using MCP bisheng read_url for JavaScript-rendered pages.]"

                if any(indicator in content.lower() for indicator in [
                    "cloudflare", "checking your browser", "please enable javascript",
                    "access denied", "bot detection", "captcha"
                ]):
                    return f"[Content appears to be blocked or requires JavaScript rendering. Use MCP bisheng read_url tool instead.]"

                return content[:50000]

        except httpx.HTTPStatusError as exc:
            return f"Error: HTTP {exc.response.status_code} - {exc.response.reason_phrase}"
        except httpx.TimeoutException:
            return "Error: Request timed out after 30 seconds"
        except Exception as exc:
            return f"Error fetching {url}: {exc!r}"


web_fetch_tool = WebFetchTool()
