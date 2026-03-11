const BASE = '/api'

export const ALL_PURPOSES = ['chat', 'title', 'worker'] as const
export type Purpose = typeof ALL_PURPOSES[number]

export const PURPOSE_LABELS: Record<Purpose, string> = {
  chat: '对话',
  title: '标题生成',
  worker: '子智能体',
}

export interface PurposeModelItem {
  provider_id: string
  provider_name: string
  model_id: string
  label: string
  sort_order: number
}

export interface PurposeModelIn {
  provider_id: string
  model_id: string
}

export async function getPurposeModels(purpose: Purpose): Promise<PurposeModelItem[]> {
  const res = await fetch(`${BASE}/purposes/${purpose}`)
  if (!res.ok) throw new Error(`获取用途模型失败 (${res.status})`)
  return res.json()
}

export async function setPurposeModels(purpose: Purpose, models: PurposeModelIn[]): Promise<PurposeModelItem[]> {
  const res = await fetch(`${BASE}/purposes/${purpose}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ models }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `设置用途模型失败 (${res.status})`)
  }
  return res.json()
}
