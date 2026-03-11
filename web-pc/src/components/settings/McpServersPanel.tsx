import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { Badge, Button, Empty, List, Popconfirm, Tag, Tooltip, message } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import {
  type McpServerCreate,
  type McpServerInfo,
  type McpServerUpdate,
  createMcpServer,
  deleteMcpServer,
  listMcpServers,
  reconnectMcpServer,
  updateMcpServer,
} from '../../api/mcp'
import McpServerFormModal from './McpServerFormModal'

const SOURCE_LABEL: Record<string, string> = {
  builtin: '预置',
  yaml: '配置文件',
  db: '自定义',
}

const SOURCE_COLOR: Record<string, string> = {
  builtin: 'blue',
  yaml: 'default',
  db: 'green',
}

const TRANSPORT_COLOR: Record<string, string> = {
  stdio: 'purple',
  http: 'cyan',
}

function StatusBadge({ status }: { status: McpServerInfo['status'] }) {
  if (status === 'connected') return <Badge status="success" text="已连接" />
  if (status === 'error') return <Badge status="error" text="连接失败" />
  return <Badge status="default" text="未连接" />
}

export default function McpServersPanel() {
  const [servers, setServers] = useState<McpServerInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [reconnecting, setReconnecting] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<McpServerInfo | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      setServers(await listMcpServers())
    } catch {
      message.error('加载 MCP 服务器列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const handleReconnect = async (name: string) => {
    setReconnecting(name)
    try {
      const updated = await reconnectMcpServer(name)
      setServers(prev => prev.map(s => s.name === name ? updated : s))
      message.success(`${name} 重连成功`)
    } catch (e: unknown) {
      message.error(`重连失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setReconnecting(null)
    }
  }

  const handleDelete = async (name: string) => {
    setDeleting(name)
    try {
      await deleteMcpServer(name)
      setServers(prev => prev.filter(s => s.name !== name))
      message.success(`${name} 已删除`)
    } catch (e: unknown) {
      message.error(`删除失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setDeleting(null)
    }
  }

  const handleSubmit = async (name: string, body: McpServerCreate | McpServerUpdate) => {
    if (editing) {
      const updated = await updateMcpServer(name, body as McpServerUpdate)
      setServers(prev => prev.map(s => s.name === name ? updated : s))
      message.success(`${name} 已更新`)
    } else {
      const created = await createMcpServer(body as McpServerCreate)
      setServers(prev => [...prev, created])
      message.success(`${name} 添加成功`)
    }
  }

  return (
    <div style={{ padding: '0 4px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>MCP 服务器</span>
        <Button
          type="primary"
          size="small"
          icon={<PlusOutlined />}
          onClick={() => { setEditing(null); setFormOpen(true) }}
        >
          添加服务器
        </Button>
      </div>

      <List
        loading={loading}
        dataSource={servers}
        locale={{ emptyText: <Empty description="暂无 MCP 服务器" imageStyle={{ height: 48 }} /> }}
        renderItem={(server) => (
          <List.Item
            style={{ padding: '10px 0', borderBottom: '1px solid rgba(0,0,0,0.06)' }}
            actions={[
              <Tooltip title="重连" key="reconnect">
                <Button
                  type="text"
                  size="small"
                  icon={<ReloadOutlined spin={reconnecting === server.name} />}
                  onClick={() => handleReconnect(server.name)}
                  disabled={!!reconnecting}
                />
              </Tooltip>,
              ...(server.editable ? [
                <Tooltip title="编辑" key="edit">
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => { setEditing(server); setFormOpen(true) }}
                  />
                </Tooltip>,
                <Popconfirm
                  key="delete"
                  title={`确认删除 ${server.name}？`}
                  okText="删除"
                  okType="danger"
                  cancelText="取消"
                  onConfirm={() => handleDelete(server.name)}
                >
                  <Tooltip title="删除">
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      loading={deleting === server.name}
                    />
                  </Tooltip>
                </Popconfirm>,
              ] : []),
            ]}
          >
            <List.Item.Meta
              title={
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 500 }}>{server.name}</span>
                  <Tag color={SOURCE_COLOR[server.source]} style={{ margin: 0 }}>
                    {SOURCE_LABEL[server.source]}
                  </Tag>
                  <Tag color={TRANSPORT_COLOR[server.transport]} style={{ margin: 0 }}>
                    {server.transport.toUpperCase()}
                  </Tag>
                </div>
              }
              description={
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <StatusBadge status={server.status} />
                  {server.status === 'connected' && (
                    <span style={{ fontSize: 12, color: '#8c8c8c' }}>{server.tool_count} 个工具</span>
                  )}
                  {server.error && (
                    <Tooltip title={server.error}>
                      <span style={{ fontSize: 12, color: '#ff4d4f', cursor: 'help', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>
                        {server.error}
                      </span>
                    </Tooltip>
                  )}
                  <span style={{ fontSize: 12, color: '#8c8c8c' }}>
                    {server.transport === 'http' ? server.url : `${server.command ?? ''} ${(server.args ?? []).join(' ')}`.trim()}
                  </span>
                </div>
              }
            />
          </List.Item>
        )}
      />

      <McpServerFormModal
        open={formOpen}
        editing={editing}
        onClose={() => { setFormOpen(false); setEditing(null) }}
        onSubmit={handleSubmit}
      />
    </div>
  )
}
