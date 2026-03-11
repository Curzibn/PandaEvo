import { EyeOutlined, ReloadOutlined, SettingOutlined } from '@ant-design/icons'
import { Badge, Button, Empty, Input, List, Select, Space, Switch, Tag, Tooltip, message } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { listSkills, type SkillInfo, updateSkillConfig } from '../../api/skills'
import SkillConfigModal from './SkillConfigModal'
import SkillDetailModal from './SkillDetailModal'

const SOURCE_LABEL: Record<string, string> = {
  workspace: '工作区',
  user: '用户',
  data_dir: '服务',
}

const SOURCE_COLOR: Record<string, string> = {
  workspace: 'blue',
  user: 'green',
  data_dir: 'orange',
}

function StatusBadge({ eligible, enabled }: { eligible: boolean; enabled: boolean }) {
  if (!eligible) {
    return <Badge status="error" text="不满足条件" />
  }
  if (enabled) {
    return <Badge status="success" text="已启用" />
  }
  return <Badge status="default" text="已禁用" />
}

export default function SkillsPanel() {
  const [skills, setSkills] = useState<SkillInfo[]>([])
  const [filteredSkills, setFilteredSkills] = useState<SkillInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [sourceFilter, setSourceFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [detailOpen, setDetailOpen] = useState(false)
  const [configOpen, setConfigOpen] = useState(false)
  const [selectedSkill, setSelectedSkill] = useState<SkillInfo | null>(null)
  const [updating, setUpdating] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listSkills()
      setSkills(data)
    } catch (e: unknown) {
      message.error(`加载技能列表失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    let filtered = skills

    if (searchText) {
      const lower = searchText.toLowerCase()
      filtered = filtered.filter(
        (s) => s.name.toLowerCase().includes(lower) || s.description.toLowerCase().includes(lower)
      )
    }

    if (sourceFilter !== 'all') {
      filtered = filtered.filter((s) => s.source === sourceFilter)
    }

    if (statusFilter !== 'all') {
      if (statusFilter === 'enabled') {
        filtered = filtered.filter((s) => s.enabled)
      } else if (statusFilter === 'disabled') {
        filtered = filtered.filter((s) => !s.enabled)
      } else if (statusFilter === 'eligible') {
        filtered = filtered.filter((s) => s.eligible)
      } else if (statusFilter === 'ineligible') {
        filtered = filtered.filter((s) => !s.eligible)
      }
    }

    setFilteredSkills(filtered)
  }, [skills, searchText, sourceFilter, statusFilter])

  const handleToggleEnabled = async (skill: SkillInfo) => {
    setUpdating(skill.name)
    try {
      await updateSkillConfig(skill.name, { enabled: !skill.enabled })
      setSkills((prev) =>
        prev.map((s) => (s.name === skill.name ? { ...s, enabled: !s.enabled } : s))
      )
      message.success(`${skill.name} ${skill.enabled ? '已禁用' : '已启用'}`)
    } catch (e: unknown) {
      message.error(`更新失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setUpdating(null)
    }
  }

  const handleViewDetail = (skill: SkillInfo) => {
    setSelectedSkill(skill)
    setDetailOpen(true)
  }

  const handleEditConfig = (skill: SkillInfo) => {
    setSelectedSkill(skill)
    setConfigOpen(true)
  }

  const handleConfigSubmit = async () => {
    await refresh()
    setConfigOpen(false)
    setSelectedSkill(null)
  }

  return (
    <div style={{ padding: '0 4px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>技能</span>
        <Button type="text" size="small" icon={<ReloadOutlined />} onClick={refresh} loading={loading}>
          刷新
        </Button>
      </div>

      <Space direction="vertical" style={{ width: '100%', marginBottom: 12 }} size="small">
        <Input.Search
          placeholder="搜索技能名称或描述"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
        />
        <Space>
          <Select
            value={sourceFilter}
            onChange={setSourceFilter}
            style={{ width: 100 }}
            size="small"
            options={[
              { label: '全部来源', value: 'all' },
              { label: '工作区', value: 'workspace' },
              { label: '用户', value: 'user' },
              { label: '服务', value: 'data_dir' },
            ]}
          />
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: 120 }}
            size="small"
            options={[
              { label: '全部状态', value: 'all' },
              { label: '已启用', value: 'enabled' },
              { label: '已禁用', value: 'disabled' },
              { label: '满足条件', value: 'eligible' },
              { label: '不满足条件', value: 'ineligible' },
            ]}
          />
        </Space>
      </Space>

      <List
        loading={loading}
        dataSource={filteredSkills}
        locale={{ emptyText: <Empty description="暂无技能" imageStyle={{ height: 48 }} /> }}
        renderItem={(skill) => (
          <List.Item
            style={{ padding: '10px 0', borderBottom: '1px solid rgba(0,0,0,0.06)' }}
            actions={[
              <Tooltip title="查看详情" key="detail">
                <Button
                  type="text"
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => handleViewDetail(skill)}
                />
              </Tooltip>,
              <Tooltip title="配置" key="config">
                <Button
                  type="text"
                  size="small"
                  icon={<SettingOutlined />}
                  onClick={() => handleEditConfig(skill)}
                />
              </Tooltip>,
              <Switch
                key="enabled"
                checked={skill.enabled}
                size="small"
                loading={updating === skill.name}
                onChange={() => handleToggleEnabled(skill)}
              />,
            ]}
          >
            <List.Item.Meta
              title={
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 500 }}>{skill.name}</span>
                  <Tag color={SOURCE_COLOR[skill.source]} style={{ margin: 0 }}>
                    {SOURCE_LABEL[skill.source]}
                  </Tag>
                  {skill.disable_model_invocation && (
                    <Tag color="purple" style={{ margin: 0 }}>
                      手动调用
                    </Tag>
                  )}
                </div>
              }
              description={
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ fontSize: 13, color: '#595959' }}>{skill.description}</span>
                  <StatusBadge eligible={skill.eligible} enabled={skill.enabled} />
                  {skill.requires && (
                    <div style={{ fontSize: 12, color: '#8c8c8c' }}>
                      {skill.requires.bins && skill.requires.bins.length > 0 && (
                        <span>需要: {skill.requires.bins.join(', ')}</span>
                      )}
                      {skill.requires.env && skill.requires.env.length > 0 && (
                        <span style={{ marginLeft: 8 }}>
                          环境变量: {skill.requires.env.join(', ')}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              }
            />
          </List.Item>
        )}
      />

      {selectedSkill && (
        <>
          <SkillDetailModal
            open={detailOpen}
            skillName={selectedSkill.name}
            onClose={() => {
              setDetailOpen(false)
              setSelectedSkill(null)
            }}
          />
          <SkillConfigModal
            open={configOpen}
            skill={selectedSkill}
            onClose={() => {
              setConfigOpen(false)
              setSelectedSkill(null)
            }}
            onSubmit={handleConfigSubmit}
          />
        </>
      )}
    </div>
  )
}
