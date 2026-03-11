import { CheckCircleOutlined, CodeOutlined, DeleteOutlined, DownloadOutlined, FileOutlined, FolderOutlined, LoadingOutlined, ReloadOutlined, SettingOutlined, UploadOutlined, UserOutlined } from '@ant-design/icons'
import appIcon from '../assets/app-icon.png'
import { Bubble, Conversations, Sender, Think } from '@ant-design/x'
import type { BubbleListProps } from '@ant-design/x'
import XMarkdown from '@ant-design/x-markdown'
import { Avatar, Button, Collapse, Flex, Select, Tag, Tooltip, Tree, Typography, Upload, message, theme as antdTheme } from 'antd'
import type { DataNode } from 'antd/es/tree'
import { createStyles } from 'antd-style'
import dayjs from 'dayjs'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import SettingsDrawer from './settings/SettingsDrawer'
import {
  createSession,
  deleteSession,
  exportSession,
  downloadFile,
  fetchFileTree,
  fetchProviders,
  generateTitle,
  getSession,
  listSessions,
  streamChat,
  switchModel,
  uploadFile,
  type FileNode,
  type ModelItem,
  type PlanEvent,
  type Provider,
  type Session,
  type ToolCallEvent,
  type ToolResultEvent,
  type WorkerDoneEvent,
  type WorkerEventWrapper,
  type WorkerStartEvent,
} from '../api/chat'
import { getPurposeModels } from '../api/purposes'

const { Text } = Typography

const useStyle = createStyles(({ token, css }) => ({
  layout: css`
    width: 100%;
    height: 100vh;
    display: flex;
    background: ${token.colorBgContainer};
    overflow: hidden;
  `,
  side: css`
    background: ${token.colorBgLayout};
    width: 260px;
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 0 12px;
    box-sizing: border-box;
    border-right: 1px solid ${token.colorBorderSecondary};
  `,
  logo: css`
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 12px;
    margin: 24px 0 12px;
    span {
      font-weight: 700;
      font-size: 17px;
      color: ${token.colorText};
    }
  `,
  conversations: css`
    flex: 1;
    overflow-y: auto;
    margin-top: 8px;
    .ant-conversations-list {
      padding-inline-start: 0;
    }
  `,
  sideFooter: css`
    border-top: 1px solid ${token.colorBorderSecondary};
    padding: 10px 4px;
    font-size: 12px;
    color: ${token.colorTextTertiary};
  `,
  modelSelect: css`
    font-size: 12px;
    .ant-select-selector {
      padding: 0 4px !important;
    }
  `,
  chat: css`
    flex: 1;
    height: 100%;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    padding: ${token.paddingLG}px;
    gap: 16px;
    box-sizing: border-box;
    .ant-bubble-content-updating {
      background-image: linear-gradient(90deg, #ff6b23 0%, #af3cb8 31%, #53b6ff 89%);
      background-size: 100% 2px;
      background-repeat: no-repeat;
      background-position: bottom;
    }
  `,
  startPage: css`
    display: flex;
    width: 100%;
    max-width: 840px;
    flex-direction: column;
    align-items: center;
    height: 100%;
    margin: 0 auto;
  `,
  agentName: css`
    margin-block-start: 22%;
    font-size: 34px;
    font-weight: 700;
    margin-block-end: 40px;
    background: linear-gradient(135deg, #1677ff 0%, #af3cb8 50%, #ff6b23 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  `,
  chatList: css`
    display: flex;
    align-items: center;
    width: 100%;
    height: 100%;
    flex-direction: column;
    max-width: 840px;
    margin: 0 auto;
    overflow: hidden;
  `,
  toolCard: css`
    width: 100%;
    margin: 4px 0;
    font-size: 12px;
    .ant-collapse-header {
      padding: 6px 12px !important;
      align-items: center !important;
    }
    .ant-collapse-content-box {
      padding: 8px 12px !important;
    }
  `,
  toolResult: css`
    white-space: pre-wrap;
    font-family: ${token.fontFamilyCode};
    font-size: 12px;
    color: ${token.colorTextSecondary};
    max-height: 300px;
    overflow-y: auto;
  `,
  fileTreeSider: css`
    background: ${token.colorBgLayout};
    width: 360px;
    min-width: 360px;
    height: 100%;
    display: flex;
    flex-direction: column;
    border-left: 1px solid ${token.colorBorderSecondary};
    box-sizing: border-box;
    overflow: hidden;
  `,
  fileTreeHeader: css`
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px 6px;
    font-size: 12px;
    font-weight: 600;
    color: ${token.colorTextSecondary};
    border-bottom: 1px solid ${token.colorBorderSecondary};
    flex-shrink: 0;
  `,
  fileTreeBody: css`
    flex: 1;
    overflow-y: auto;
    padding: 4px 0;
  `,
  thinkBlink: css`
    animation: thinkBlink 1.5s ease-in-out infinite;
  `,
}))

interface ToolStep {
  callId: string
  name: string
  args: Record<string, unknown>
  result?: string
}

interface TaskItem {
  id: string
  title: string
  status: 'pending' | 'running' | 'done'
  tokens: string
  result?: string
}

interface Message {
  key: string
  role: 'user' | 'assistant' | 'tool_group' | 'task_plan'
  content: string
  loading?: boolean
  streaming?: boolean
  thinking?: string
  thinkingDone?: boolean
  tasks?: TaskItem[]
}

interface ConvMeta {
  sessionId: string
  model: string
}

interface ConvItem {
  key: string
  label: string
  group: string
}

function getDateGroup(isoDate: string): string {
  const today = dayjs().startOf('day')
  const d = dayjs(isoDate).startOf('day')
  const diff = today.diff(d, 'day')
  if (diff === 0) return '今天'
  if (diff === 1) return '昨天'
  return '更早'
}

function deserializeMessages(
  raw: Session['messages'],
  genKey: () => string,
): Message[] {
  const result: Message[] = []
  let i = 0
  while (i < raw.length) {
    const m = raw[i]
    if (m.role === 'user') {
      result.push({ key: genKey(), role: 'user', content: m.content })
      i++
    } else if (m.role === 'assistant' && m.tool_calls?.length) {
      const steps: ToolStep[] = m.tool_calls.map((tc) => ({
        callId: tc.id,
        name: tc.function.name,
        args: (() => {
          try { return JSON.parse(tc.function.arguments) } catch { return {} }
        })(),
        result: undefined,
      }))
      let j = i + 1
      while (j < raw.length && raw[j].role === 'tool') {
        const toolMsg = raw[j]
        const step = steps.find((s) => s.callId === toolMsg.tool_call_id)
        if (step) step.result = toolMsg.content
        j++
      }
      result.push({ key: genKey(), role: 'tool_group', content: JSON.stringify(steps) })
      i = j
    } else if (m.role === 'assistant') {
      result.push({ key: genKey(), role: 'assistant', content: m.content, thinking: m.thinking, thinkingDone: true })
      i++
    } else {
      i++
    }
  }
  return result
}

function TaskPlanBubble({ tasks }: { tasks: TaskItem[] }) {
  const { styles } = useStyle()
  const { token } = antdTheme.useToken()
  return (
    <Flex vertical gap={4} style={{ width: '100%' }}>
      {tasks.map((task) => (
        <Collapse
          key={task.id}
          size="small"
          className={styles.toolCard}
          items={[
            {
              key: task.id,
              label: (
                <Flex gap={8} align="center">
                  {task.status === 'running' && (
                    <LoadingOutlined style={{ color: token.colorPrimary, fontSize: 12 }} />
                  )}
                  {task.status === 'done' && (
                    <CheckCircleOutlined style={{ color: token.colorSuccess, fontSize: 12 }} />
                  )}
                  {task.status === 'pending' && (
                    <span style={{ width: 12, height: 12, borderRadius: '50%', background: token.colorFill, display: 'inline-block' }} />
                  )}
                  <Text style={{ fontSize: 12 }}>{task.title}</Text>
                </Flex>
              ),
              children: (
                <Flex vertical gap={4}>
                  {task.tokens && (
                    <pre className={styles.toolResult}>{task.tokens}</pre>
                  )}
                  {task.result !== undefined && task.result !== task.tokens && (
                    <pre className={styles.toolResult} style={{ borderTop: task.tokens ? `1px solid ${token.colorBorderSecondary}` : undefined, paddingTop: task.tokens ? 4 : undefined }}>{task.result}</pre>
                  )}
                  {!task.tokens && task.result === undefined && (
                    <Text type="secondary" style={{ fontSize: 11 }}>等待中...</Text>
                  )}
                </Flex>
              ),
            },
          ]}
        />
      ))}
    </Flex>
  )
}

function ToolGroupBubble({ steps }: { steps: ToolStep[] }) {
  const { styles } = useStyle()
  return (
    <Flex vertical gap={4} style={{ width: '100%' }}>
      {steps.map((step) => (
        <Collapse
          key={step.callId}
          size="small"
          className={styles.toolCard}
          items={[
            {
              key: step.callId,
              label: (
                <Flex gap={6} align="center">
                  <Tag icon={<CodeOutlined />} color="processing" style={{ margin: 0, fontSize: 11 }}>
                    {step.name}
                  </Tag>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {Object.entries(step.args)
                      .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
                      .join('  ')}
                  </Text>
                </Flex>
              ),
              children: step.result !== undefined ? (
                <pre className={styles.toolResult}>{step.result}</pre>
              ) : (
                <Text type="secondary" style={{ fontSize: 11 }}>执行中...</Text>
              ),
            },
          ]}
        />
      ))}
    </Flex>
  )
}

function toTreeData(node: FileNode, path = ''): DataNode {
  const key = path ? `${path}/${node.name}` : node.name
  return {
    key,
    title: node.name,
    isLeaf: node.type === 'file',
    icon: node.type === 'dir' ? <FolderOutlined /> : <FileOutlined />,
    children: node.children?.map((c) => toTreeData(c, key)),
  }
}

function FileTreeSider({ onFileClick }: { onFileClick: (path: string) => void }) {
  const { styles } = useStyle()
  const [treeData, setTreeData] = useState<DataNode[]>([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const root = await fetchFileTree('.', 3)
      setTreeData(root.children?.map((c) => toTreeData(c)) ?? [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleUpload = async (file: File) => {
    await uploadFile(file, '.')
    load()
    return false
  }

  const handleDownload = (e: React.MouseEvent, path: string) => {
    e.stopPropagation()
    downloadFile(path)
  }

  return (
    <div className={styles.fileTreeSider}>
      <div className={styles.fileTreeHeader}>
        <span>工作区</span>
        <Flex gap={4}>
          <Upload beforeUpload={handleUpload} showUploadList={false}>
            <Tooltip title="上传文件">
              <Button type="text" size="small" icon={<UploadOutlined />} />
            </Tooltip>
          </Upload>
          <Tooltip title="刷新">
            <Button type="text" size="small" icon={<ReloadOutlined spin={loading} />} onClick={load} />
          </Tooltip>
        </Flex>
      </div>
      <div className={styles.fileTreeBody}>
        <Tree.DirectoryTree
          treeData={treeData}
          showIcon={false}
          blockNode
          selectable={false}
          titleRender={(node) => (
            <Flex justify="space-between" align="center" style={{ width: '100%', minWidth: 0 }}>
              <Flex align="center" gap={4} style={{ flex: 1, minWidth: 0 }}>
                {node.isLeaf ? <FileOutlined style={{ flexShrink: 0, fontSize: 12 }} /> : <FolderOutlined style={{ flexShrink: 0, fontSize: 12 }} />}
                <span
                  style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', cursor: node.isLeaf ? 'pointer' : 'default' }}
                  onClick={() => node.isLeaf && onFileClick(String(node.key))}
                >
                  {String(node.title)}
                </span>
              </Flex>
              {node.isLeaf && (
                <Tooltip title="下载">
                  <Button
                    type="text"
                    size="small"
                    icon={<DownloadOutlined />}
                    onClick={(e) => handleDownload(e, String(node.key))}
                    style={{ flexShrink: 0, opacity: 0.6 }}
                  />
                </Tooltip>
              )}
            </Flex>
          )}
        />
      </div>
    </div>
  )
}

export default function ChatPage() {
  const { styles } = useStyle()
  const { token } = antdTheme.useToken()

  const [, setProviders] = useState<Provider[]>([])
  const [allModels, setAllModels] = useState<ModelItem[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('')

  const [conversations, setConversations] = useState<ConvItem[]>([])
  const [convMeta, setConvMeta] = useState<Record<string, ConvMeta>>({})
  const [activeKey, setActiveKey] = useState<string>('')
  const [messages, setMessages] = useState<Record<string, Message[]>>({})
  const [streaming, setStreaming] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)

  const abortRef = useRef<AbortController | null>(null)
  const msgKeyRef = useRef(0)
  const senderRef = useRef<{ focus?: () => void } | null>(null)

  const reloadModels = useCallback(() => {
    Promise.all([fetchProviders(), getPurposeModels('chat')]).then(([ps, chatPurpose]) => {
      setProviders(ps)
      const allAvailable = ps.flatMap((p) => p.models)
      const chatModels = chatPurpose.length > 0
        ? chatPurpose.map((pm) => allAvailable.find((m) => m.provider_id === pm.provider_id && m.id === pm.model_id)).filter(Boolean) as ModelItem[]
        : allAvailable
      setAllModels(chatModels)
      if (chatModels.length > 0) setSelectedModel((prev) => chatModels.find((m) => m.id === prev) ? prev : chatModels[0].id)
    })
  }, [])

  useEffect(() => {
    Promise.all([fetchProviders(), listSessions(), getPurposeModels('chat')]).then(([ps, sessions, chatPurpose]) => {
      setProviders(ps)
      const allAvailable = ps.flatMap((p) => p.models)
      const chatModels = chatPurpose.length > 0
        ? chatPurpose.map((pm) => allAvailable.find((m) => m.provider_id === pm.provider_id && m.id === pm.model_id)).filter(Boolean) as ModelItem[]
        : allAvailable
      setAllModels(chatModels)
      if (chatModels.length > 0) setSelectedModel(chatModels[0].id)

      if (sessions.length === 0) return
      const convItems: ConvItem[] = sessions.map((s) => ({
        key: s.id,
        label: s.title ?? `对话 ${s.id.slice(0, 8)}`,
        group: getDateGroup(s.created_at),
      }))
      const metaMap: Record<string, ConvMeta> = {}
      for (const s of sessions) {
        metaMap[s.id] = { sessionId: s.id, model: s.model }
      }
      setConversations(convItems)
      setConvMeta(metaMap)
    })
  }, [])

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/ws`)
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'reload') window.location.reload()
      } catch {}
    }
    return () => ws.close()
  }, [])

  const genKey = () => `msg-${++msgKeyRef.current}`

  const handleNewConversation = useCallback(async () => {
    if (!selectedModel) return
    const session = await createSession(selectedModel)
    const convKey = session.id
    const newConv: ConvItem = {
      key: convKey,
      label: `新对话 ${conversations.length + 1}`,
      group: getDateGroup(new Date().toISOString()),
    }
    setConversations((prev) => [newConv, ...prev])
    setConvMeta((prev) => ({ ...prev, [convKey]: { sessionId: session.id, model: selectedModel } }))
    setMessages((prev) => ({ ...prev, [convKey]: [] }))
    setActiveKey(convKey)
    localStorage.setItem('activeSessionId', convKey)
  }, [selectedModel, conversations.length])

  const handleActiveChange = useCallback(async (key: string) => {
    setActiveKey(key)
    localStorage.setItem('activeSessionId', key)
    if (messages[key]) return
    const data = await getSession(key)
    const loaded = deserializeMessages(data.messages, genKey)
    setMessages((prev) => ({ ...prev, [key]: loaded }))
  }, [messages])

  const handleModelSwitch = useCallback(
    async (model: string) => {
      setSelectedModel(model)
      if (activeKey && convMeta[activeKey]) {
        await switchModel(convMeta[activeKey].sessionId, model)
        setConvMeta((prev) => ({
          ...prev,
          [activeKey]: { ...prev[activeKey], model },
        }))
      }
    },
    [activeKey, convMeta],
  )

  const handleDeleteConversation = useCallback(
    async (convKey: string) => {
      const meta = convMeta[convKey]
      if (meta) await deleteSession(meta.sessionId)
      setConversations((prev) => prev.filter((c) => c.key !== convKey))
      setConvMeta((prev) => { const n = { ...prev }; delete n[convKey]; return n })
      setMessages((prev) => { const n = { ...prev }; delete n[convKey]; return n })
      if (activeKey === convKey) setActiveKey('')
    },
    [convMeta, activeKey],
  )

  const handleExportConversation = useCallback(async (convKey: string) => {
    const meta = convMeta[convKey]
    if (!meta) {
      message.error('会话不存在或未加载')
      return
    }
    try {
      const result = await exportSession(meta.sessionId)
      if (result.mode === 'tauri_dialog' && result.savedPath) {
        message.success(`导出成功：${result.savedPath}`)
      } else {
        message.success('导出成功，文件已开始下载')
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : '导出失败')
    }
  }, [convMeta])

  const handleSend = useCallback(
    async (content: string) => {
      if (!content.trim() || streaming) return
      setInputValue('')

      let targetKey = activeKey
      let isNewSession = false
      if (!targetKey || !convMeta[targetKey]) {
        if (!selectedModel) return
        const session = await createSession(selectedModel)
        targetKey = session.id
        isNewSession = true
        const newConv: ConvItem = {
          key: targetKey,
          label: content.slice(0, 20),
          group: getDateGroup(new Date().toISOString()),
        }
        setConversations((prev) => [newConv, ...prev])
        setConvMeta((prev) => ({
          ...prev,
          [targetKey]: { sessionId: session.id, model: selectedModel },
        }))
        setMessages((prev) => ({ ...prev, [targetKey]: [] }))
        setActiveKey(targetKey)
        localStorage.setItem('activeSessionId', targetKey)
      }

      const meta = convMeta[targetKey] ?? { sessionId: targetKey, model: selectedModel }
      const currentConv = conversations.find((c) => c.key === targetKey)
      const isDefaultTitle = currentConv?.label ? /^(新对话|对话)\s*\d+$/.test(currentConv.label) : false
      const needsTitle = isNewSession || !currentConv?.label || isDefaultTitle || currentConv.label === content.slice(0, 20)
      console.log('[Title] needsTitle:', needsTitle, 'isNewSession:', isNewSession, 'isDefaultTitle:', isDefaultTitle, 'currentConv?.label:', currentConv?.label, 'content.slice(0, 20):', content.slice(0, 20))
      const userKey = genKey()
      const toolGroupKey = genKey()
      const taskPlanKey = genKey()
      const aiKey = genKey()

      setMessages((prev) => ({
        ...prev,
        [targetKey]: [
          ...(prev[targetKey] ?? []),
          { key: userKey, role: 'user', content },
          { key: toolGroupKey, role: 'tool_group', content: '[]' },
          { key: aiKey, role: 'assistant', content: '', loading: true },
        ],
      }))
      setStreaming(true)

      abortRef.current = streamChat(
        meta.sessionId,
        content,
        (tok) => {
          setMessages((prev) => {
            const msgs = prev[targetKey] ?? []
            return {
              ...prev,
              [targetKey]: msgs.map((m) =>
                m.key === aiKey
                  ? { ...m, loading: false, streaming: true, content: m.content + tok }
                  : m,
              ),
            }
          })
        },
        () => {
          setMessages((prev) => {
            const msgs = prev[targetKey] ?? []
            const toolGroupMsg = msgs.find((m) => m.key === toolGroupKey)
            let steps: ToolStep[] = []
            try { steps = JSON.parse(toolGroupMsg?.content ?? '[]') } catch { steps = [] }
            return {
              ...prev,
              [targetKey]: msgs
                .filter((m) => m.key !== toolGroupKey || steps.length > 0)
                .map((m) =>
                  m.key === aiKey ? { ...m, loading: false, streaming: false, thinkingDone: true } : m,
                ),
            }
          })
          setStreaming(false)
        },
        () => {
          setMessages((prev) => {
            const msgs = prev[targetKey] ?? []
            return {
              ...prev,
              [targetKey]: msgs.map((m) =>
                m.key === aiKey
                  ? { ...m, content: '请求出错，请重试', loading: false, streaming: false, thinkingDone: true }
                  : m,
              ),
            }
          })
          setStreaming(false)
        },
        (event: ToolCallEvent) => {
          setMessages((prev) => {
            const msgs = prev[targetKey] ?? []
            return {
              ...prev,
              [targetKey]: msgs.map((m) => {
                if (m.key !== toolGroupKey) return m
                let steps: ToolStep[] = []
                try { steps = JSON.parse(m.content) } catch { steps = [] }
                const updated: ToolStep[] = [...steps, { callId: event.id, name: event.name, args: event.args }]
                return { ...m, content: JSON.stringify(updated) }
              }),
            }
          })
        },
        (event: ToolResultEvent) => {
          setMessages((prev) => {
            const msgs = prev[targetKey] ?? []
            return {
              ...prev,
              [targetKey]: msgs.map((m) => {
                if (m.key !== toolGroupKey) return m
                let steps: ToolStep[] = []
                try { steps = JSON.parse(m.content) } catch { steps = [] }
                const updated = steps.map((s) =>
                  s.callId === event.id ? { ...s, result: event.content } : s,
                )
                return { ...m, content: JSON.stringify(updated) }
              }),
            }
          })
        },
        (chunk: string) => {
          setMessages((prev) => {
            const msgs = prev[targetKey] ?? []
            return {
              ...prev,
              [targetKey]: msgs.map((m) =>
                m.key === aiKey
                  ? { ...m, loading: false, thinking: (m.thinking ?? '') + chunk }
                  : m,
              ),
            }
          })
        },
        (event: PlanEvent) => {
          const newTasks: TaskItem[] = event.tasks.map((t) => ({
            id: t.id,
            title: t.title,
            status: 'pending',
            tokens: '',
          }))
          setMessages((prev) => {
            const msgs = prev[targetKey] ?? []
            const withoutEmpty = msgs.filter((m) => m.key !== toolGroupKey)
            return {
              ...prev,
              [targetKey]: [
                ...withoutEmpty.filter((m) => m.key !== aiKey),
                { key: taskPlanKey, role: 'task_plan', content: '', tasks: newTasks },
                { key: aiKey, role: 'assistant', content: '', loading: true },
              ],
            }
          })
        },
        (event: WorkerStartEvent) => {
          setMessages((prev) => {
            const msgs = prev[targetKey] ?? []
            return {
              ...prev,
              [targetKey]: msgs.map((m) => {
                if (m.key !== taskPlanKey || !m.tasks) return m
                return { ...m, tasks: m.tasks.map((t) => t.id === event.task_id ? { ...t, status: 'running' as const } : t) }
              }),
            }
          })
        },
        (event: WorkerEventWrapper) => {
          if (event.event.type !== 'token') return
          setMessages((prev) => {
            const msgs = prev[targetKey] ?? []
            return {
              ...prev,
              [targetKey]: msgs.map((m) => {
                if (m.key !== taskPlanKey || !m.tasks) return m
                return {
                  ...m,
                  tasks: m.tasks.map((t) =>
                    t.id === event.task_id
                      ? { ...t, tokens: t.tokens + (event.event.content as string ?? '') }
                      : t,
                  ),
                }
              }),
            }
          })
        },
        (event: WorkerDoneEvent) => {
          setMessages((prev) => {
            const msgs = prev[targetKey] ?? []
            return {
              ...prev,
              [targetKey]: msgs.map((m) => {
                if (m.key !== taskPlanKey || !m.tasks) return m
                return {
                  ...m,
                  tasks: m.tasks.map((t) =>
                    t.id === event.task_id ? { ...t, status: 'done' as const, result: event.result } : t,
                  ),
                }
              }),
            }
          })
        },
      )

      if (needsTitle) {
        console.log('[Title] Calling generateTitle for session:', meta.sessionId, 'content:', content)
        generateTitle(meta.sessionId, content)
          .then((result) => {
            console.log('[Title] generateTitle result:', result)
            if (result.title) {
              setConversations((prev) =>
                prev.map((c) => c.key === targetKey ? { ...c, label: result.title! } : c),
              )
            }
          })
          .catch((err) => {
            console.error('[Title] Failed to generate title:', err)
          })
      } else {
        console.log('[Title] Skipping title generation, needsTitle is false')
      }
    },
    [activeKey, convMeta, streaming, selectedModel, conversations],
  )

  const handleCancel = () => {
    abortRef.current?.abort()
    setStreaming(false)
  }

  const handleFileClick = useCallback((filePath: string) => {
    setInputValue((prev) => prev ? `${prev} @${filePath}` : `@${filePath}`)
    senderRef.current?.focus?.()
  }, [])

  const currentMessages = messages[activeKey] ?? []

  const bubbleRole: BubbleListProps['role'] = {
    assistant: {
      placement: 'start',
      avatar: <Avatar src={appIcon} />,
      variant: 'borderless',
      contentRender: (content, info) => {
        const { thinking, thinkingDone } = (info.extraInfo ?? {}) as { thinking?: string; thinkingDone?: boolean }
        return (
          <>
            {thinking && (
              <Think
                title="深度思考"
                loading={!thinkingDone}
                blink={!thinkingDone}
                defaultExpanded={false}
                classNames={!thinkingDone ? {
                  root: styles.thinkBlink,
                } : undefined}
              >
                <XMarkdown content={thinking} />
              </Think>
            )}
            <XMarkdown content={typeof content === 'string' ? content : ''} />
          </>
        )
      },
    },
    user: {
      placement: 'end',
      avatar: (
        <Avatar
          icon={<UserOutlined />}
          style={{ background: token.colorPrimary }}
        />
      ),
      variant: 'filled',
      shape: 'corner',
    },
    tool_group: {
      placement: 'start',
      avatar: (
        <Avatar
          icon={<CodeOutlined />}
          style={{ background: token.colorFillSecondary, color: token.colorTextSecondary }}
        />
      ),
      variant: 'borderless',
      contentRender: (content) => {
        let steps: ToolStep[] = []
        try {
          steps = JSON.parse(typeof content === 'string' ? content : '[]')
        } catch {
          steps = []
        }
        return <ToolGroupBubble steps={steps} />
      },
    },
    task_plan: {
      placement: 'start',
      avatar: <Avatar src={appIcon} />,
      variant: 'borderless',
      contentRender: (_content, info) => {
        const tasks = (info.extraInfo as { tasks?: TaskItem[] })?.tasks ?? []
        return <TaskPlanBubble tasks={tasks} />
      },
    },
  }

  const currentModel = convMeta[activeKey]?.model ?? selectedModel

  const modelSelector = (
    <Select
      value={currentModel}
      onChange={handleModelSwitch}
      size="small"
      className={styles.modelSelect}
      options={allModels.map((m) => ({ label: m.label, value: m.id }))}
      variant="borderless"
      popupMatchSelectWidth={false}
    />
  )

  return (
    <div className={styles.layout}>
      <div className={styles.side}>
        <div className={styles.logo}>
          <img src={appIcon} alt="" style={{ width: 28, height: 28 }} />
          <span>PandaEvo</span>
        </div>

        <Conversations
          className={styles.conversations}
          items={conversations}
          activeKey={activeKey}
          onActiveChange={handleActiveChange}
          groupable
          creation={{ label: '新建对话', onClick: handleNewConversation }}
          styles={{ item: { padding: '0 8px' } }}
          menu={(conv) => ({
            items: [
              {
                key: 'export',
                label: '导出',
                icon: <DownloadOutlined />,
                onClick: () => handleExportConversation(conv.key),
              },
              {
                key: 'delete',
                label: '删除',
                icon: <DeleteOutlined />,
                danger: true,
                onClick: () => handleDeleteConversation(conv.key),
              },
            ],
          })}
        />

        <div className={styles.sideFooter} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Text type="secondary" style={{ fontSize: 11 }}>PandaEvo</Text>
          <Tooltip title="设置">
            <Button type="text" size="small" icon={<SettingOutlined />} onClick={() => setSettingsOpen(true)} />
          </Tooltip>
        </div>
      </div>

      <div className={styles.chat}>
        {activeKey && currentMessages.length > 0 ? (
          <div className={styles.chatList}>
            <Bubble.List
              style={{ flex: 1, width: '100%', overflowY: 'auto', paddingBottom: 8 }}
              autoScroll
              items={currentMessages.map((m) => ({
                key: m.key,
                role: m.role,
                content: m.content,
                loading: m.loading,
                streaming: m.streaming,
                extraInfo: m.role === 'assistant'
                  ? { thinking: m.thinking, thinkingDone: m.thinkingDone }
                  : m.role === 'task_plan'
                    ? { tasks: m.tasks }
                    : undefined,
              }))}
              role={bubbleRole}
            />
            <Sender
              style={{ width: '100%', flexShrink: 0 }}
              value={inputValue}
              onChange={setInputValue}
              onSubmit={handleSend}
              onCancel={handleCancel}
              loading={streaming}
              placeholder="输入消息，Enter 发送，Shift+Enter 换行"
              submitType="enter"
              autoSize={{ minRows: 3, maxRows: 6 }}
              suffix={false}
              footer={(actionNode) => (
                <Flex justify="space-between" align="center">
                  <Flex gap={8} align="center">
                    {modelSelector}
                  </Flex>
                  {actionNode}
                </Flex>
              )}
            />
          </div>
        ) : (
          <div className={styles.startPage}>
            <div className={styles.agentName}>有什么我可以帮你的？</div>
            <Sender
              style={{ width: '100%', maxWidth: 680 }}
              value={inputValue}
              onChange={setInputValue}
              onSubmit={handleSend}
              onCancel={handleCancel}
              loading={streaming}
              placeholder="输入消息开始对话，Enter 发送"
              submitType="enter"
              autoSize={{ minRows: 3, maxRows: 6 }}
              suffix={false}
              footer={(actionNode) => (
                <Flex justify="space-between" align="center">
                  <Flex gap={8} align="center">
                    {modelSelector}
                  </Flex>
                  {actionNode}
                </Flex>
              )}
            />
          </div>
        )}
      </div>
      <FileTreeSider onFileClick={handleFileClick} />
      <SettingsDrawer open={settingsOpen} onClose={() => { setSettingsOpen(false); reloadModels() }} />
    </div>
  )
}
