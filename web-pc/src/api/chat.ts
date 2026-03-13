import { invoke } from '@tauri-apps/api/core'

const BASE = '/api'

export interface ModelItem {
  id: string
  label: string
  provider_id: string
}

export interface Provider {
  name: string
  api_base: string | null
  models: ModelItem[]
}

export interface Session {
  id: string
  model: string
  messages: {
    role: string
    content: string
    thinking?: string
    tool_calls?: { id: string; function: { name: string; arguments: string } }[]
    tool_call_id?: string
  }[]
  created_at: string
}

export interface SessionSummary {
  id: string
  model: string
  title: string | null
  created_at: string
  message_count: number
}

export interface ToolCallEvent {
  type: 'tool_call'
  id: string
  name: string
  args: Record<string, unknown>
}

export interface ToolResultEvent {
  type: 'tool_result'
  id: string
  content: string
}

export interface PlanTask {
  id: string
  title: string
  depends_on: string[]
}

export interface PlanEvent {
  type: 'plan'
  tasks: PlanTask[]
}

export interface WorkerStartEvent {
  type: 'worker_start'
  task_id: string
}

export interface WorkerInnerEvent {
  type: string
  [key: string]: unknown
}

export interface WorkerEventWrapper {
  type: 'worker_event'
  task_id: string
  event: WorkerInnerEvent
}

export interface WorkerDoneEvent {
  type: 'worker_done'
  task_id: string
  result: string
}

export interface RouteEvent {
  type: 'route'
  route: 'direct' | 'orchestrator'
  reason: string
}

export interface EvolutionDisabledWarningEvent {
  type: 'evolution_disabled_warning'
  message: string
}

export interface DoneEvent {
  type: 'done'
  status: 'success' | 'failed' | 'partial'
  new_message?: { content?: string; thinking?: string }
  artifacts?: {
    prs?: Array<{
      repo: string
      branch: string
      pr_number: number | string
      pr_url: string
    }>
    failed_tasks?: Array<{
      id: string
      title: string
      type: string
      code: string
      error: string
    }>
  }
}

export async function listSessions(): Promise<SessionSummary[]> {
  const res = await fetch(`${BASE}/sessions`)
  if (!res.ok) throw new Error('Failed to list sessions')
  return res.json()
}

export async function fetchProviders(): Promise<Provider[]> {
  const res = await fetch(`${BASE}/providers`)
  if (!res.ok) throw new Error('Failed to fetch providers')
  return res.json()
}

export async function createSession(model: string): Promise<Session> {
  const res = await fetch(`${BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model }),
  })
  if (!res.ok) throw new Error('Failed to create session')
  return res.json()
}

export async function getSession(sessionId: string): Promise<Session> {
  const res = await fetch(`${BASE}/sessions/${sessionId}`)
  if (!res.ok) throw new Error('Failed to get session')
  return res.json()
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' })
}

function parseDownloadFileName(contentDisposition: string | null): string {
  if (!contentDisposition) return 'pandaevo-session-export.json'
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(contentDisposition)
  if (utf8?.[1]) return decodeURIComponent(utf8[1])
  const plain = /filename="([^"]+)"/i.exec(contentDisposition)
  if (plain?.[1]) return plain[1]
  return 'pandaevo-session-export.json'
}

export interface ExportSessionResult {
  fileName: string
  savedPath?: string
  mode: 'tauri_dialog' | 'browser_download'
}

function isTauriRuntime(): boolean {
  const w = window as unknown as { __TAURI__?: unknown; __TAURI_INTERNALS__?: unknown }
  return Boolean(w.__TAURI__ || w.__TAURI_INTERNALS__)
}

function triggerBrowserDownload(blob: Blob, fileName: string): void {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  a.click()
  window.URL.revokeObjectURL(url)
}

async function fetchSessionExport(sessionId: string): Promise<{ blob: Blob; fileName: string }> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/export`)
  if (!res.ok) {
    let detail = 'Failed to export session'
    try {
      const payload = await res.json() as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {}
    throw new Error(detail)
  }
  const blob = await res.blob()
  const fileName = parseDownloadFileName(res.headers.get('content-disposition'))
  return { blob, fileName }
}

async function saveByTauriDialog(blob: Blob, fileName: string): Promise<string | undefined> {
  const bytes = Array.from(new Uint8Array(await blob.arrayBuffer()))
  const savedPath = await invoke<string | null>('save_export_file', { fileName, bytes })
  if (savedPath === null) {
    throw new Error('已取消导出')
  }
  return savedPath ?? undefined
}

export async function exportSession(sessionId: string): Promise<ExportSessionResult> {
  const { blob, fileName } = await fetchSessionExport(sessionId)
  if (isTauriRuntime()) {
    const savedPath = await saveByTauriDialog(blob, fileName)
    return { fileName, savedPath, mode: 'tauri_dialog' }
  }
  triggerBrowserDownload(blob, fileName)
  return { fileName, mode: 'browser_download' }
}

export async function switchModel(sessionId: string, model: string): Promise<Session> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/model`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model }),
  })
  if (!res.ok) throw new Error('Failed to switch model')
  return res.json()
}

export async function generateTitle(sessionId: string, content: string): Promise<{ title: string | null }> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/title`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  if (!res.ok) {
    if (res.status === 409) {
      return { title: null }
    }
    throw new Error('Failed to generate title')
  }
  return res.json()
}

export interface FileNode {
  name: string
  type: 'file' | 'dir'
  children?: FileNode[]
}

export async function fetchFileTree(path = '.', depth = 2): Promise<FileNode> {
  const res = await fetch(`${BASE}/fs/tree?path=${encodeURIComponent(path)}&depth=${depth}`)
  if (!res.ok) throw new Error('Failed to fetch file tree')
  return res.json()
}

export async function uploadFile(file: File, dir = '.'): Promise<{ path: string; size: number }> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/fs/upload?dir=${encodeURIComponent(dir)}`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error('Failed to upload file')
  return res.json()
}

export function downloadFile(path: string): void {
  const url = `${BASE}/fs/download?path=${encodeURIComponent(path)}`
  const a = document.createElement('a')
  a.href = url
  a.download = path.split('/').pop() ?? 'download'
  a.click()
}

export function streamChat(
  sessionId: string,
  content: string,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (err: Error) => void,
  onToolCall?: (event: ToolCallEvent) => void,
  onToolResult?: (event: ToolResultEvent) => void,
  onThinking?: (chunk: string) => void,
  onPlan?: (event: PlanEvent) => void,
  onWorkerStart?: (event: WorkerStartEvent) => void,
  onWorkerEvent?: (event: WorkerEventWrapper) => void,
  onWorkerDone?: (event: WorkerDoneEvent) => void,
  onRoute?: (event: RouteEvent) => void,
  onDoneEvent?: (event: DoneEvent) => void,
  onEvolutionDisabledWarning?: (event: EvolutionDisabledWarningEvent) => void,
): AbortController {
  const ctrl = new AbortController()
  fetch(`${BASE}/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, route_mode: 'auto' }),
    signal: ctrl.signal,
  })
    .then(async (res) => {
      if (!res.ok || !res.body) throw new Error('Stream failed')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6)
          if (raw === '[DONE]') {
            onDone()
            return
          }
          try {
            const event = JSON.parse(raw) as { type: string; [k: string]: unknown }
            if (event.type === 'token') {
              onToken(event.content as string)
            } else if (event.type === 'thinking') {
              onThinking?.(event.content as string)
            } else if (event.type === 'tool_call') {
              onToolCall?.(event as unknown as ToolCallEvent)
            } else if (event.type === 'tool_result') {
              onToolResult?.(event as unknown as ToolResultEvent)
            } else if (event.type === 'error') {
              onError(new Error(event.content as string))
            } else if (event.type === 'plan') {
              onPlan?.(event as unknown as PlanEvent)
            } else if (event.type === 'worker_start') {
              onWorkerStart?.(event as unknown as WorkerStartEvent)
            } else if (event.type === 'worker_event') {
              onWorkerEvent?.(event as unknown as WorkerEventWrapper)
            } else if (event.type === 'worker_done') {
              onWorkerDone?.(event as unknown as WorkerDoneEvent)
            } else if (event.type === 'route') {
              onRoute?.(event as unknown as RouteEvent)
            } else if (event.type === 'evolution_disabled_warning') {
              onEvolutionDisabledWarning?.(event as unknown as EvolutionDisabledWarningEvent)
            } else if (event.type === 'done') {
              onDoneEvent?.(event as unknown as DoneEvent)
            }
          } catch {
            onToken(raw)
          }
        }
      }
      onDone()
    })
    .catch((err: Error) => {
      if (err.name !== 'AbortError') onError(err)
    })
  return ctrl
}
