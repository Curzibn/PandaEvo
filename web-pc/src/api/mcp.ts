const BASE = '/api'

export type McpSource = 'builtin' | 'yaml' | 'db'
export type McpTransport = 'stdio' | 'http'
export type McpStatus = 'connected' | 'disconnected' | 'error'

export interface McpServerInfo {
  name: string
  source: McpSource
  transport: McpTransport
  command?: string
  args?: string[]
  env?: Record<string, string>
  url?: string
  headers?: Record<string, string>
  status: McpStatus
  tool_count: number
  error?: string
  editable: boolean
}

export interface McpServerCreate {
  name: string
  command?: string
  args?: string[]
  env?: Record<string, string>
  url?: string
  headers?: Record<string, string>
}

export interface McpServerUpdate {
  command?: string
  args?: string[]
  env?: Record<string, string>
  url?: string
  headers?: Record<string, string>
}

export async function listMcpServers(): Promise<McpServerInfo[]> {
  const res = await fetch(`${BASE}/mcp/servers`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function createMcpServer(body: McpServerCreate): Promise<McpServerInfo> {
  const res = await fetch(`${BASE}/mcp/servers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function updateMcpServer(name: string, body: McpServerUpdate): Promise<McpServerInfo> {
  const res = await fetch(`${BASE}/mcp/servers/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function deleteMcpServer(name: string): Promise<void> {
  const res = await fetch(`${BASE}/mcp/servers/${encodeURIComponent(name)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await res.text())
}

export async function reconnectMcpServer(name: string): Promise<McpServerInfo> {
  const res = await fetch(`${BASE}/mcp/servers/${encodeURIComponent(name)}/reconnect`, { method: 'POST' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
