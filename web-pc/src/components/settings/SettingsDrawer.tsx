import { Drawer, Tabs } from 'antd'
import McpServersPanel from './McpServersPanel'
import ProvidersPanel from './ProvidersPanel'
import PurposesPanel from './PurposesPanel'
import SkillsPanel from './SkillsPanel'

interface Props {
  open: boolean
  onClose: () => void
}

export default function SettingsDrawer({ open, onClose }: Props) {
  return (
    <Drawer
      title="设置"
      placement="right"
      width={560}
      open={open}
      onClose={onClose}
      destroyOnHidden
      styles={{ body: { padding: '16px 20px' } }}
    >
      <Tabs
        items={[
          { key: 'providers', label: '大模型', children: <ProvidersPanel /> },
          { key: 'purposes', label: '用途', children: <PurposesPanel /> },
          { key: 'mcp', label: 'MCP 服务器', children: <McpServersPanel /> },
          { key: 'skills', label: '技能', children: <SkillsPanel /> },
        ]}
      />
    </Drawer>
  )
}
