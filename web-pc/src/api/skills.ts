const BASE = '/api'

export interface SkillRequires {
  bins?: string[]
  env?: string[]
  config?: string[]
}

export interface SkillInfo {
  name: string
  description: string
  license?: string
  compatibility?: string
  source: 'workspace' | 'user' | 'data_dir'
  priority: number
  path: string
  eligible: boolean
  enabled: boolean
  disable_model_invocation: boolean
  requires?: SkillRequires
  metadata?: Record<string, string>
}

export interface SkillDetail extends SkillInfo {
  content: string
  resources?: {
    scripts?: Record<string, string>
    references?: Record<string, string>
    assets?: Record<string, string>
  }
  env?: Record<string, string>
  api_key?: string
  config?: Record<string, unknown>
}

export interface SkillConfigUpdate {
  enabled?: boolean
  env?: Record<string, string>
  api_key?: string
  config?: Record<string, unknown>
}

export interface SkillsConfig {
  enabled: boolean
  auto_match: boolean
  max_skills: number
}

export async function listSkills(): Promise<SkillInfo[]> {
  const res = await fetch(`${BASE}/skills`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getSkill(name: string): Promise<SkillDetail> {
  const res = await fetch(`${BASE}/skills/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function updateSkillConfig(name: string, config: SkillConfigUpdate): Promise<void> {
  const res = await fetch(`${BASE}/skills/${encodeURIComponent(name)}/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(await res.text())
}

export async function getSkillsConfig(): Promise<SkillsConfig> {
  const res = await fetch(`${BASE}/skills/config`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
