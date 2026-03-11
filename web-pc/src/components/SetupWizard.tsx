import { useState } from 'react'
import { Button, Form, Input, List, Modal, Space, Tag, Typography, message } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { type ProviderPayload } from '../api/providers'
import { setPurposeModels } from '../api/purposes'

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

interface ProviderFormData {
  id: string
  name: string
  api_key: string
  api_base: string | null
  models: string[]
  selectedPreset: Preset | null
}

interface Props {
  onComplete: () => void
}

export default function SetupWizard({ onComplete }: Props) {
  const [providers, setProviders] = useState<ProviderFormData[]>([])
  const [loading, setLoading] = useState(false)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [modelInputs, setModelInputs] = useState<Record<string, string>>({})

  const addProvider = () => {
    const newProvider: ProviderFormData = {
      id: Date.now().toString(),
      name: '',
      api_key: '',
      api_base: null,
      models: [],
      selectedPreset: null,
    }
    setProviders((prev) => [...prev, newProvider])
    setEditingIndex(providers.length)
  }

  const removeProvider = (index: number) => {
    setProviders((prev) => prev.filter((_, i) => i !== index))
    if (editingIndex === index) {
      setEditingIndex(null)
    } else if (editingIndex !== null && editingIndex > index) {
      setEditingIndex(editingIndex - 1)
    }
  }

  const applyPreset = (index: number, preset: Preset) => {
    setProviders((prev) => {
      const updated = [...prev]
      updated[index] = {
        ...updated[index],
        name: preset.name || '',
        api_base: preset.api_base || null,
        models: preset.models,
        selectedPreset: preset,
      }
      return updated
    })
  }

  const updateProvider = (index: number, updates: Partial<ProviderFormData>) => {
    setProviders((prev) => {
      const updated = [...prev]
      updated[index] = { ...updated[index], ...updates }
      return updated
    })
  }

  const addModel = (id: string, model: string) => {
    const provider = providers.find((p) => p.id === id)
    if (provider && model && !provider.models.includes(model)) {
      updateProvider(providers.indexOf(provider), { models: [...provider.models, model] })
      setModelInputs((prev) => ({ ...prev, [id]: '' }))
    }
  }

  const handleAddModel = (id: string) => {
    const val = (modelInputs[id] ?? '').trim()
    if (val) addModel(id, val)
  }

  const removeModel = (index: number, modelId: string) => {
    const provider = providers[index]
    updateProvider(index, { models: provider.models.filter((m) => m !== modelId) })
  }

  const handleOk = async () => {
    if (providers.length === 0) {
      message.warning('请至少添加一个 Provider')
      return
    }

    const hasModel = providers.some((p) => p.models.length > 0)
    if (!hasModel) {
      message.warning('至少需要添加一个模型')
      return
    }

    for (const provider of providers) {
      if (!provider.name || !provider.api_key) {
        message.warning(`Provider "${provider.name || '未命名'}" 缺少必要信息`)
        return
      }
    }

    setLoading(true)
    try {
      const createdProviders: { provider_id: string; model_id: string }[] = []
      for (const provider of providers) {
        const payload: ProviderPayload = {
          name: provider.name,
          api_key: provider.api_key,
          api_base: provider.api_base,
          models: provider.models.map((id) => ({ id })),
        }
        const res = await fetch('/api/providers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          throw new Error(err.detail ?? `创建 Provider 失败 (${res.status})`)
        }
        const created = await res.json()
        for (const m of created.models) {
          createdProviders.push({ provider_id: m.provider_id, model_id: m.id })
        }
      }

      if (createdProviders.length > 0) {
        await setPurposeModels('chat', createdProviders)
      }

      message.success('大模型配置成功，正在进入聊天界面...')
      onComplete()
    } catch (e: unknown) {
      message.error(e instanceof Error ? e.message : '配置失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open
      closable={false}
      maskClosable={false}
      title={null}
      footer={
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Button onClick={addProvider} icon={<PlusOutlined />}>
            添加 Provider
          </Button>
          <Button type="primary" loading={loading} onClick={handleOk}>
            完成配置，进入聊天
          </Button>
        </Space>
      }
      width={720}
      styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}
    >
      <div style={{ marginBottom: 20 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          欢迎使用 PandaEvo
        </Typography.Title>
        <Typography.Text type="secondary">
          请先配置至少一个大模型 Provider。完成后可在「设置 → 用途」中调整每个用途使用的模型及顺序。
        </Typography.Text>
      </div>

      {providers.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={addProvider}>
            添加第一个 Provider
          </Button>
        </div>
      ) : (
        <List
          dataSource={providers}
          renderItem={(provider, index) => (
            <List.Item
              actions={[
                <Button
                  key="edit"
                  type="link"
                  onClick={() => setEditingIndex(editingIndex === index ? null : index)}
                >
                  {editingIndex === index ? '收起' : '编辑'}
                </Button>,
                <Button
                  key="del"
                  type="link"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => removeProvider(index)}
                />,
              ]}
            >
              <List.Item.Meta
                title={<Typography.Text strong>{provider.name || '未命名 Provider'}</Typography.Text>}
                description={
                  editingIndex === index ? (
                    <div style={{ marginTop: 16 }}>
                      <div style={{ marginBottom: 16 }}>
                        <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
                          选择预设快速填充
                        </Typography.Text>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                          {PRESETS.map((p) => (
                            <Button
                              key={p.name || 'custom'}
                              size="small"
                              type={provider.selectedPreset?.label === p.label ? 'primary' : 'default'}
                              onClick={() => applyPreset(index, p)}
                            >
                              {p.label}
                            </Button>
                          ))}
                        </div>
                      </div>

                      <Form layout="vertical" size="small">
                        <Form.Item label="Provider 名称" required>
                          <Input
                            placeholder="如 dashscope、openai"
                            value={provider.name}
                            onChange={(e) => updateProvider(index, { name: e.target.value })}
                          />
                        </Form.Item>

                        <Form.Item label="API Key" required>
                          <Input.Password
                            placeholder="sk-..."
                            value={provider.api_key}
                            onChange={(e) => updateProvider(index, { api_key: e.target.value })}
                          />
                        </Form.Item>

                        <Form.Item
                          label="API Base URL"
                          hidden={provider.selectedPreset !== null && provider.selectedPreset.name !== ''}
                        >
                          <Input
                            placeholder="https://api.openai.com/v1"
                            value={provider.api_base || ''}
                            onChange={(e) => updateProvider(index, { api_base: e.target.value || null })}
                          />
                        </Form.Item>

                        <Form.Item label="模型列表">
                          <Space.Compact style={{ width: '100%', marginBottom: provider.models.length > 0 ? 10 : 0 }}>
                            <Input
                              placeholder="输入模型 ID，如 gpt-4o"
                              value={modelInputs[provider.id] ?? ''}
                              onChange={(e) => setModelInputs((prev) => ({ ...prev, [provider.id]: e.target.value }))}
                              onPressEnter={() => handleAddModel(provider.id)}
                            />
                            <Button
                              type="primary"
                              icon={<PlusOutlined />}
                              onClick={() => handleAddModel(provider.id)}
                              disabled={!(modelInputs[provider.id] ?? '').trim()}
                            >
                              添加
                            </Button>
                          </Space.Compact>
                          {provider.models.length > 0 && (
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                              {provider.models.map((id) => (
                                <Tag key={id} closable onClose={() => removeModel(index, id)} style={{ fontSize: 12 }}>
                                  {id.split('/').pop() ?? id}
                                </Tag>
                              ))}
                            </div>
                          )}
                        </Form.Item>
                      </Form>
                    </div>
                  ) : (
                    <div>
                      {provider.api_base && (
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {provider.api_base}
                        </Typography.Text>
                      )}
                      {provider.models.length > 0 && (
                        <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                          {provider.models.map((id) => (
                            <Tag key={id} style={{ fontSize: 11 }}>{id.split('/').pop() ?? id}</Tag>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                }
              />
            </List.Item>
          )}
        />
      )}
    </Modal>
  )
}
