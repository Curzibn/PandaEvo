const BASE = '/api'

export interface ModelIn {
  id: string
}

export interface ProviderPayload {
  name: string
  api_key: string
  api_base: string | null
  models: ModelIn[]
}

export interface ProviderUpdatePayload {
  api_key: string | null
  api_base: string | null
  models: ModelIn[]
}

export async function createProvider(payload: ProviderPayload): Promise<void> {
  const res = await fetch(`${BASE}/providers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `创建失败 (${res.status})`)
  }
}

export async function updateProvider(name: string, payload: ProviderUpdatePayload): Promise<void> {
  const res = await fetch(`${BASE}/providers/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `更新失败 (${res.status})`)
  }
}

export async function deleteProvider(name: string): Promise<void> {
  const res = await fetch(`${BASE}/providers/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `删除失败 (${res.status})`)
  }
}
