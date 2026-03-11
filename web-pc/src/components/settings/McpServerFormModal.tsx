import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { Button, Form, Input, Modal, Radio, Space } from 'antd'
import { useEffect, useState } from 'react'
import type { McpServerCreate, McpServerInfo, McpServerUpdate } from '../../api/mcp'

interface KVItem {
  key: string
  value: string
}

function KVEditor({ value, onChange }: {
  value?: KVItem[]
  onChange?: (v: KVItem[]) => void
}) {
  const items = value ?? []
  const set = (next: KVItem[]) => onChange?.(next)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {items.map((item, i) => (
        <Space key={i} style={{ width: '100%' }}>
          <Input
            placeholder="KEY"
            value={item.key}
            style={{ width: 140 }}
            onChange={e => set(items.map((x, j) => j === i ? { ...x, key: e.target.value } : x))}
          />
          <Input
            placeholder="VALUE"
            value={item.value}
            style={{ flex: 1 }}
            onChange={e => set(items.map((x, j) => j === i ? { ...x, value: e.target.value } : x))}
          />
          <MinusCircleOutlined onClick={() => set(items.filter((_, j) => j !== i))} style={{ color: '#ff4d4f', cursor: 'pointer' }} />
        </Space>
      ))}
      <Button
        type="dashed"
        icon={<PlusOutlined />}
        size="small"
        onClick={() => set([...items, { key: '', value: '' }])}
        style={{ width: 120 }}
      >
        添加
      </Button>
    </div>
  )
}

function kvToRecord(items: KVItem[]): Record<string, string> | undefined {
  const entries = items.filter(x => x.key.trim())
  if (!entries.length) return undefined
  return Object.fromEntries(entries.map(x => [x.key.trim(), x.value]))
}

function recordToKv(rec?: Record<string, string> | null): KVItem[] {
  if (!rec) return []
  return Object.entries(rec).map(([key, value]) => ({ key, value }))
}

interface FormValues {
  name: string
  transport: 'stdio' | 'http'
  command: string
  args: string
  env: KVItem[]
  url: string
  headers: KVItem[]
}

interface Props {
  open: boolean
  editing?: McpServerInfo | null
  onClose: () => void
  onSubmit: (name: string, body: McpServerCreate | McpServerUpdate) => Promise<void>
}

export default function McpServerFormModal({ open, editing, onClose, onSubmit }: Props) {
  const [form] = Form.useForm<FormValues>()
  const [transport, setTransport] = useState<'stdio' | 'http'>('stdio')
  const [loading, setLoading] = useState(false)
  const isEdit = !!editing

  useEffect(() => {
    if (!open) return
    if (editing) {
      const t = editing.transport
      setTransport(t)
      form.setFieldsValue({
        name: editing.name,
        transport: t,
        command: editing.command ?? '',
        args: (editing.args ?? []).join(' '),
        env: recordToKv(editing.env),
        url: editing.url ?? '',
        headers: recordToKv(editing.headers),
      })
    } else {
      form.resetFields()
      setTransport('stdio')
    }
  }, [open, editing, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    setLoading(true)
    try {
      const args = values.args ? values.args.trim().split(/\s+/) : []
      let body: McpServerCreate | McpServerUpdate
      if (values.transport === 'http') {
        body = { url: values.url, headers: kvToRecord(values.headers ?? []) }
      } else {
        body = {
          command: values.command,
          args,
          env: kvToRecord(values.env ?? []),
        }
      }
      if (!isEdit) {
        (body as McpServerCreate).name = values.name
      }
      await onSubmit(editing?.name ?? values.name, body)
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      title={isEdit ? `编辑 MCP 服务器 · ${editing?.name}` : '添加 MCP 服务器'}
      okText={isEdit ? '保存' : '添加'}
      cancelText="取消"
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={loading}
      width={520}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        {!isEdit && (
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请填写服务器名称' }]}>
            <Input placeholder="my-server" />
          </Form.Item>
        )}
        <Form.Item name="transport" label="传输类型" initialValue="stdio">
          <Radio.Group onChange={e => setTransport(e.target.value)}>
            <Radio value="stdio">stdio（本地进程）</Radio>
            <Radio value="http">HTTP（远程端点）</Radio>
          </Radio.Group>
        </Form.Item>

        {transport === 'stdio' ? (
          <>
            <Form.Item name="command" label="命令" rules={[{ required: true, message: '请填写启动命令' }]}>
              <Input placeholder="npx / uvx / python" />
            </Form.Item>
            <Form.Item name="args" label="参数">
              <Input placeholder="-y @company/mcp-server（空格分隔）" />
            </Form.Item>
            <Form.Item name="env" label="环境变量">
              <KVEditor />
            </Form.Item>
          </>
        ) : (
          <>
            <Form.Item name="url" label="端点 URL" rules={[{ required: true, message: '请填写端点 URL' }, { type: 'url', message: '请输入有效的 URL' }]}>
              <Input placeholder="https://api.example.com/mcp" />
            </Form.Item>
            <Form.Item name="headers" label="请求头">
              <KVEditor />
            </Form.Item>
          </>
        )}
      </Form>
    </Modal>
  )
}
