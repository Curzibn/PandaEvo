import { useEffect, useRef, useState } from 'react'
import { Button, Form, Input, Modal, Space, Tag, Typography, message, type InputRef } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { type ProviderPayload, type ProviderUpdatePayload } from '../../api/providers'

interface Preset {
  label: string
  name: string
  api_base: string
  models: string[]
}

const PRESETS: Preset[] = [
  { label: '阿里云百炼', name: 'dashscope', api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', models: [] },
  { label: 'OpenAI', name: 'openai', api_base: 'https://api.openai.com/v1', models: [] },
  { label: 'Anthropic', name: 'anthropic', api_base: 'https://api.anthropic.com/v1', models: [] },
  { label: 'Google', name: 'google', api_base: 'https://generativelanguage.googleapis.com/v1beta', models: [] },
  { label: '自定义', name: '', api_base: '', models: [] },
]

interface Props {
  open: boolean
  editName?: string
  initialValues?: {
    api_key?: string
    api_base?: string | null
    models?: { id: string }[]
  }
  onSubmit: (payload: ProviderPayload | ProviderUpdatePayload) => Promise<void>
  onCancel: () => void
}

export default function ProviderFormModal({ open, editName, initialValues, onSubmit, onCancel }: Props) {
  const isEdit = !!editName
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [selectedPreset, setSelectedPreset] = useState<Preset | null>(null)
  const [models, setModels] = useState<string[]>([])
  const [modelInput, setModelInput] = useState('')
  const modelInputRef = useRef<InputRef | null>(null)

  useEffect(() => {
    if (open) {
      if (isEdit && initialValues) {
        form.setFieldsValue({
          api_key: initialValues.api_key ?? '',
          api_base: initialValues.api_base ?? '',
        })
        setModels(initialValues.models?.map((m) => m.id) ?? [])
      } else {
        form.resetFields()
        setModels([])
      }
      setSelectedPreset(null)
      setModelInput('')
    }
  }, [open, isEdit, initialValues, form])

  const applyPreset = (preset: Preset) => {
    setSelectedPreset(preset)
    form.setFieldsValue({ name: preset.name, api_base: preset.api_base })
    setModels(preset.models)
    setModelInput('')
  }

  const handleAddModel = () => {
    const val = modelInput.trim()
    if (val) {
      addModel(val)
      setModelInput('')
      modelInputRef.current?.focus()
    }
  }

  const removeModel = (id: string) => setModels((prev) => prev.filter((m) => m !== id))

  const addModel = (id: string) => {
    if (id && !models.includes(id)) {
      setModels((prev) => [...prev, id])
    }
  }

  const handleOk = async () => {
    const values = await form.validateFields()
    const apiBase = !isEdit && selectedPreset && selectedPreset.name !== ''
      ? selectedPreset.api_base
      : (values.api_base || null)
    setLoading(true)
    try {
      if (isEdit) {
        await onSubmit({
          api_key: !values.api_key || values.api_key.trim() === '' ? null : values.api_key,
          api_base: apiBase,
          models: models.map((id) => ({ id })),
        } satisfies ProviderUpdatePayload)
      } else {
        await onSubmit({
          name: values.name,
          api_key: values.api_key,
          api_base: apiBase,
          models: models.map((id) => ({ id })),
        } satisfies ProviderPayload)
      }
    } catch (e: unknown) {
      message.error(e instanceof Error ? e.message : '操作失败')
      throw e
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title={isEdit ? `编辑 Provider · ${editName}` : '添加大模型 Provider'}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      okText={isEdit ? '保存' : '添加'}
      cancelText="取消"
      confirmLoading={loading}
      width={520}
      destroyOnClose
    >
      {!isEdit && (
        <div style={{ marginBottom: 16 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
            选择预设快速填充
          </Typography.Text>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {PRESETS.map((p) => (
              <Button
                key={p.name || 'custom'}
                size="small"
                type={selectedPreset?.label === p.label ? 'primary' : 'default'}
                onClick={() => applyPreset(p)}
              >
                {p.label}
              </Button>
            ))}
          </div>
        </div>
      )}

      <Form form={form} layout="vertical" requiredMark={false}>
        {!isEdit && (
          <Form.Item
            label="Provider 名称"
            name="name"
            rules={[{ required: true, message: '请填写 Provider 名称' }]}
          >
            <Input placeholder="如 dashscope、openai" />
          </Form.Item>
        )}

        <Form.Item
          label="API Key"
          name="api_key"
          rules={isEdit ? [] : [{ required: true, message: '请填写 API Key' }]}
          extra={isEdit ? '留空则不修改' : undefined}
        >
          <Input.Password placeholder="sk-..." />
        </Form.Item>

        <Form.Item
          label="API Base URL"
          name="api_base"
          hidden={!isEdit && selectedPreset !== null && selectedPreset.name !== ''}
        >
          <Input placeholder="https://api.openai.com/v1" />
        </Form.Item>

        <Form.Item label="模型列表">
          <Space.Compact style={{ width: '100%', marginBottom: models.length > 0 ? 10 : 0 }}>
            <Input
              ref={modelInputRef}
              placeholder="输入模型 ID，如 gpt-4o"
              value={modelInput}
              onChange={(e) => setModelInput(e.target.value)}
              onPressEnter={handleAddModel}
            />
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleAddModel}
              disabled={!modelInput.trim()}
            >
              添加
            </Button>
          </Space.Compact>
          {models.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {models.map((id) => (
                <Tag key={id} closable onClose={() => removeModel(id)} style={{ fontSize: 12 }}>
                  {id.split('/').pop() ?? id}
                </Tag>
              ))}
            </div>
          )}
        </Form.Item>
      </Form>
    </Modal>
  )
}
