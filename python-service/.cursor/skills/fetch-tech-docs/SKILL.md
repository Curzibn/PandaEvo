---
name: fetch-tech-docs
description: Fetch and read official technical documentation from any platform (React, Go, Rust, Ant Design, etc.). Use WebFetch first; if blocked or empty, fall back to the bisheng MCP `read_url` tool for headless browser rendering. Use when the user asks to look up docs, read API references, check official usage, or mentions "官方文档", "查文档", "docs", "API reference", "how to use X".
---

# Fetch Tech Docs

## Strategy

Always attempt in this order:

1. **web_fetch** – fast, no overhead. Use for most doc sites.
2. **bisheng `read_url`** – headless browser fallback when web_fetch returns empty, blocked, or JS-rendered content.
3. **bisheng `scan_docs_toc`** – when the user needs the full TOC of a doc site or asks to batch-read multiple pages.

## Step 1 — Try web_fetch

Call the `web_fetch` tool with the target URL. Proceed to Step 2 if the result is:
- empty or clearly truncated
- a login/bot-check wall
- raw HTML with no readable content

## Step 2 — Fallback: bisheng `read_url`

MCP server: `user-bisheng`, tool: `read_url`

The tool name in PandaEvo will be `mcp_user-bisheng_read_url`.

```json
{ "url": "<target URL>" }
```

The tool uses a headless Chromium to render the page and returns Markdown. Use this for:
- SPA doc sites (Vite, Next.js, Docusaurus, VitePress, etc.)
- Sites that block simple HTTP fetchers

## Step 3 — Scan TOC: bisheng `scan_docs_toc`

MCP server: `user-bisheng`, tool: `scan_docs_toc`

The tool name in PandaEvo will be `mcp_user-bisheng_scan_docs_toc`.

```json
{ "url": "<doc root URL>", "max_depth": 3 }
```

Use when:
- User wants to explore what's available in a doc site
- User asks to read the entire guide for a library
- You need to discover page URLs before batch-reading them

After getting the TOC, read individual pages with `read_url` as needed.

## Tips

- Prefer specific deep-link URLs (e.g. `https://ant.design/components/table`) over root URLs to get focused content.
- For versioned docs, include the version in the URL if known.
- If `read_url` also fails (network error), report the issue and suggest the user provide the URL or paste the content manually.
