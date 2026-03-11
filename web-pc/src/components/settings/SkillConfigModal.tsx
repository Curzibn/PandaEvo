import { Form, Input, Modal, Switch, message } from 'antd'
import { useEffect, useState } from 'react'
import { getSkill, updateSkillConfig, type SkillInfo, type SkillConfigUpdate } from '../../api/skills'

interface KVEditorProps {
  value?: Record<string, string>
  onChange?: (value: Record<string, string>) => void
}

function KVEditor({ value = {}, onChange }: KVEditorProps) {
  const [items, setItems] = useState<Array<{ key: string; value: string }>>(() => {
    return Object.entries(value).map(([k, v]) => ({ key: k, value: v }))
  })

  useEffect(() => {
    const newItems = Object.entries(value).map(([k, v]) => ({ key: k, value: v }))
    setItems(newItems.length > 0 ? newItems : [{ key: '', value: '' }])
  }, [value])

  const updateItem = (index: number, field: 'key' | 'value', val: string) => {
    const newItems = [...items]
    newItems[index] = { ...newItems[index], [field]: val }
    setItems(newItems)
    const obj: Record<string, string> = {}
    for (const item of newItems) {
      if (item.key.trim()) {
        obj[item.key.trim()] = item.value
      }
    }
    onChange?.(obj)
  }

  const addItem = () => {
    setItems([...items, { key: '', value: '' }])
  }

  const removeItem = (index: number) => {
    if (items.length === 1) {
      setItems([{ key: '', value: '' }])
      onChange?.({})
      return
    }
    const newItems = items.filter((_, i) => i !== index)
    setItems(newItems)
    const obj: Record<string, string> = {}
    for (const item of newItems) {
      if (item.key.trim()) {
        obj[item.key.trim()] = item.value
      }
    }
    onChange?.(obj)
  }

  return (
    <div style={{ border: '1px solid #d9d9d9', borderRadius: 4, padding: 8 }}>
      {items.map((item, index) => (
        <div key={index} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <Input
            placeholder="键"
            value={item.key}
            onChange={(e) => updateItem(index, 'key', e.target.value)}
            style={{ flex: 1 }}
          />
          <Input
            placeholder="值"
            value={item.value}
            onChange={(e) => updateItem(index, 'value', e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            type="button"
            onClick={() => removeItem(index)}
            style={{
              padding: '4px 8px',
              border: '1px solid #d9d9d9',
              borderRadius: 4,
              background: '#fff',
              cursor: 'pointer',
            }}
          >
            删除
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={addItem}
        style={{
          padding: '4px 8px',
          border: '1px solid #d9d9d9',
          borderRadius: 4,
          background: '#fff',
          cursor: 'pointer',
          width: '100%',
        }}
      >
        添加
      </button>
    </div>
  )
}

interface JSONEditorProps {
  value?: Record<string, unknown>
  onChange?: (value: Record<string, unknown>) => void
}

function JSONEditor({ value = {}, onChange }: JSONEditorProps) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2))
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setText(JSON.stringify(value, null, 2))
  }, [value])

  const handleChange = (val: string) => {
    setText(val)
    try {
      const parsed = JSON.parse(val)
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        setError(null)
        onChange?.(parsed)
      } else {
        setError('必须是有效的 JSON 对象')
      }
    } catch {
      setError('无效的 JSON')
    }
  }

  return (
    <div>
      <Input.TextArea
        value={text}
        onChange={(e) => handleChange(e.target.value)}
        rows={8}
        style={{ fontFamily: 'monospace' }}
        status={error ? 'error' : undefined}
      />
      {error && <div style={{ color: '#ff4d4f', marginTop: 4, fontSize: 12 }}>{error}</div>}
    </div>
  )
}

interface SkillConfigModalProps {
  open: boolean
  skill: SkillInfo
  onClose: () => void
  onSubmit: () => void
}

export default function SkillConfigModal({ open, skill, onClose, onSubmit }: SkillConfigModalProps) {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [, setCurrentSkill] = useState<SkillInfo | null>(null)

  useEffect(() => {
    if (open) {
      getSkill(skill.name)
        .then((detail) => {
          setCurrentSkill(detail)
          form.setFieldsValue({
            enabled: detail.enabled,
            env: detail.env || {},
            api_key: detail.api_key || '',
            config: detail.config || {},
          })
        })
        .catch((e) => {
          console.error('Failed to load skill:', e)
          form.setFieldsValue({
            enabled: skill.enabled,
            env: {},
            api_key: '',
            config: {},
          })
        })
    } else {
      form.resetFields()
      setCurrentSkill(null)
    }
  }, [open, skill.name, skill.enabled, form])

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      setLoading(true)
      const update: SkillConfigUpdate = {}
      if (values.enabled !== undefined) {
        update.enabled = values.enabled
      }
      if (values.env !== undefined) {
        update.env = values.env
      }
      if (values.api_key !== undefined && values.api_key !== '') {
        update.api_key = values.api_key
      }
      if (values.config !== undefined) {
        update.config = values.config
      }
      await updateSkillConfig(skill.name, update)
      message.success('配置已更新')
      onSubmit()
    } catch (e: unknown) {
      if (e && typeof e === 'object' && 'errorFields' in e) {
        return
      }
      message.error(`更新失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      onOk={handleSubmit}
      title={`配置技能: ${skill.name}`}
      width={600}
      confirmLoading={loading}
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item label="启用" name="enabled" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item label="环境变量" name="env">
          <KVEditor />
        </Form.Item>
        <Form.Item label="API 密钥" name="api_key">
          <Input.Password placeholder="留空则不更新" />
        </Form.Item>
        <Form.Item label="自定义配置" name="config">
          <JSONEditor />
        </Form.Item>
      </Form>
    </Modal>
  )
}
