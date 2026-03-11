import { useCallback, useEffect, useState } from 'react'
import { Button, Empty, List, Popconfirm, Tag, Typography, message } from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import { fetchProviders, type Provider } from '../../api/chat'
import { createProvider, deleteProvider, updateProvider, type ProviderPayload, type ProviderUpdatePayload } from '../../api/providers'
import ProviderFormModal from './ProviderFormModal'

export default function ProvidersPanel() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Provider | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setProviders(await fetchProviders())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const openAdd = () => {
    setEditTarget(null)
    setModalOpen(true)
  }

  const openEdit = (p: Provider) => {
    setEditTarget(p)
    setModalOpen(true)
  }

  const handleSubmit = async (payload: ProviderPayload | ProviderUpdatePayload) => {
    try {
      if (editTarget) {
        await updateProvider(editTarget.name, payload as ProviderUpdatePayload)
        message.success('Provider 已更新')
      } else {
        await createProvider(payload as ProviderPayload)
        message.success('Provider 已添加')
      }
      setModalOpen(false)
      await load()
    } catch (e: unknown) {
      message.error(e instanceof Error ? e.message : '操作失败')
    }
  }

  const handleDelete = async (name: string) => {
    try {
      await deleteProvider(name)
      message.success('Provider 已删除')
      await load()
    } catch (e: unknown) {
      message.error(e instanceof Error ? e.message : '删除失败')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
          添加 Provider
        </Button>
      </div>

      <List
        loading={loading}
        dataSource={providers}
        locale={{ emptyText: <Empty description="暂无大模型配置" /> }}
        renderItem={(p) => (
          <List.Item
            actions={[
              <Button
                key="edit"
                type="text"
                icon={<EditOutlined />}
                onClick={() => openEdit(p)}
              />,
              <Popconfirm
                key="del"
                title={`确定删除 ${p.name}？`}
                okText="删除"
                okButtonProps={{ danger: true }}
                cancelText="取消"
                onConfirm={() => handleDelete(p.name)}
              >
                <Button type="text" danger icon={<DeleteOutlined />} />
              </Popconfirm>,
            ]}
          >
            <List.Item.Meta
              title={<Typography.Text strong>{p.name}</Typography.Text>}
              description={
                <div>
                  {p.api_base && (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {p.api_base}
                    </Typography.Text>
                  )}
                  <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {p.models.map((m) => (
                      <Tag key={m.id} style={{ fontSize: 11 }}>{m.label}</Tag>
                    ))}
                  </div>
                </div>
              }
            />
          </List.Item>
        )}
      />

      <ProviderFormModal
        open={modalOpen}
        editName={editTarget?.name}
        initialValues={
          editTarget
            ? {
                api_key: '',
                api_base: editTarget.api_base,
                models: editTarget.models.map((m) => ({ id: m.id })),
              }
            : undefined
        }
        onSubmit={handleSubmit}
        onCancel={() => setModalOpen(false)}
      />
    </div>
  )
}
