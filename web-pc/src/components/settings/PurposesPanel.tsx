import { useCallback, useEffect, useState } from 'react'
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import {
  Button,
  Divider,
  Empty,
  Flex,
  Select,
  Spin,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import { fetchProviders, type ModelItem, type Provider } from '../../api/chat'
import {
  ALL_PURPOSES,
  PURPOSE_LABELS,
  getPurposeModels,
  setPurposeModels,
  type Purpose,
  type PurposeModelItem,
} from '../../api/purposes'

const PURPOSE_COLORS: Record<Purpose, string> = {
  chat: 'blue',
  title: 'purple',
  worker: 'green',
}

const PURPOSE_DESCS: Record<Purpose, string> = {
  chat: '对话时可切换的模型，按序号排列为可选项',
  title: '依次尝试生成标题，全部失败则使用对话模型',
  worker: '依次尝试作为子智能体执行任务，全部失败则使用对话模型',
}

interface PurposeSectionProps {
  purpose: Purpose
  allModels: ModelItem[]
  providers: Provider[]
}

function PurposeSection({ purpose, allModels, providers }: PurposeSectionProps) {
  const [items, setItems] = useState<PurposeModelItem[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await getPurposeModels(purpose))
    } finally {
      setLoading(false)
    }
  }, [purpose])

  useEffect(() => { load() }, [load])

  const save = async (next: PurposeModelItem[]) => {
    setSaving(true)
    try {
      const saved = await setPurposeModels(
        purpose,
        next.map((it) => ({ provider_id: it.provider_id, model_id: it.model_id })),
      )
      setItems(saved)
    } catch (e: unknown) {
      message.error(e instanceof Error ? e.message : '保存失败')
      await load()
    } finally {
      setSaving(false)
    }
  }

  const moveUp = (idx: number) => {
    if (idx === 0) return
    const next = [...items]
    ;[next[idx - 1], next[idx]] = [next[idx], next[idx - 1]]
    save(next)
  }

  const moveDown = (idx: number) => {
    if (idx === items.length - 1) return
    const next = [...items]
    ;[next[idx], next[idx + 1]] = [next[idx + 1], next[idx]]
    save(next)
  }

  const remove = (idx: number) => {
    const next = items.filter((_, i) => i !== idx)
    save(next)
  }

  const add = (value: string) => {
    const [providerId, modelId] = value.split('::')
    if (items.some((it) => it.provider_id === providerId && it.model_id === modelId)) {
      message.warning('该模型已在列表中')
      return
    }
    const provider = providers.find((p) => p.models.some((m) => m.provider_id === providerId && m.id === modelId))
    if (!provider) return
    const model = provider.models.find((m) => m.provider_id === providerId && m.id === modelId)
    if (!model) return
    const next: PurposeModelItem[] = [
      ...items,
      {
        provider_id: providerId,
        provider_name: provider.name,
        model_id: modelId,
        label: model.label,
        sort_order: items.length,
      },
    ]
    save(next)
  }

  const addedKeys = new Set(items.map((it) => `${it.provider_id}::${it.model_id}`))
  const selectOptions = providers.flatMap((p) =>
    p.models
      .filter((m) => !addedKeys.has(`${m.provider_id}::${m.id}`))
      .map((m) => ({
        value: `${m.provider_id}::${m.id}`,
        label: `${p.name} / ${m.label}`,
      })),
  )

  return (
    <div>
      <Flex align="center" gap={8} style={{ marginBottom: 4 }}>
        <Tag color={PURPOSE_COLORS[purpose]} style={{ margin: 0, fontSize: 13, padding: '2px 10px' }}>
          {PURPOSE_LABELS[purpose]}
        </Tag>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {PURPOSE_DESCS[purpose]}
        </Typography.Text>
      </Flex>

      <Spin spinning={loading || saving} size="small">
        {items.length === 0 && !loading && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂未配置模型"
            style={{ margin: '8px 0' }}
          />
        )}
        {items.map((item, idx) => (
          <Flex
            key={`${item.provider_id}::${item.model_id}`}
            align="center"
            gap={8}
            style={{
              padding: '6px 8px',
              borderRadius: 6,
              marginBottom: 4,
              background: 'var(--ant-color-fill-quaternary, rgba(0,0,0,0.02))',
            }}
          >
            <Typography.Text
              type="secondary"
              style={{ fontSize: 11, width: 18, textAlign: 'right', flexShrink: 0 }}
            >
              {idx + 1}
            </Typography.Text>
            <Flex flex={1} vertical style={{ minWidth: 0 }}>
              <Typography.Text style={{ fontSize: 13 }}>{item.label}</Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                {item.provider_name}
              </Typography.Text>
            </Flex>
            <Tooltip title="上移">
              <Button
                type="text"
                size="small"
                icon={<ArrowUpOutlined />}
                disabled={idx === 0 || saving}
                onClick={() => moveUp(idx)}
              />
            </Tooltip>
            <Tooltip title="下移">
              <Button
                type="text"
                size="small"
                icon={<ArrowDownOutlined />}
                disabled={idx === items.length - 1 || saving}
                onClick={() => moveDown(idx)}
              />
            </Tooltip>
            <Tooltip title="移除">
              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
                disabled={saving}
                onClick={() => remove(idx)}
              />
            </Tooltip>
          </Flex>
        ))}

        <Select
          placeholder={<><PlusOutlined /> 添加模型</>}
          style={{ width: '100%', marginTop: 4 }}
          options={selectOptions}
          value={null}
          onChange={add}
          disabled={saving || selectOptions.length === 0}
          showSearch
          filterOption={(input, opt) =>
            (opt?.label as string ?? '').toLowerCase().includes(input.toLowerCase())
          }
          notFoundContent={
            allModels.length === 0
              ? '请先在「大模型」标签页添加 Provider'
              : '所有模型已添加'
          }
        />
      </Spin>
    </div>
  )
}

export default function PurposesPanel() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [allModels, setAllModels] = useState<ModelItem[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    fetchProviders()
      .then((ps) => {
        setProviders(ps)
        setAllModels(ps.flatMap((p) => p.models))
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <Spin style={{ display: 'block', margin: '40px auto' }} />
  }

  return (
    <Flex vertical gap={0}>
      {ALL_PURPOSES.map((purpose, i) => (
        <div key={purpose}>
          <PurposeSection purpose={purpose} allModels={allModels} providers={providers} />
          {i < ALL_PURPOSES.length - 1 && <Divider style={{ margin: '16px 0' }} />}
        </div>
      ))}
    </Flex>
  )
}
