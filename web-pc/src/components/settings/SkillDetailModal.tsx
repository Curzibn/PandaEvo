import { Modal, Tabs, Descriptions, Tag, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { getSkill, type SkillDetail } from '../../api/skills'
import ReactMarkdown from 'react-markdown'

const { Text, Paragraph } = Typography

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

interface SkillDetailModalProps {
  open: boolean
  skillName: string
  onClose: () => void
}

export default function SkillDetailModal({ open, skillName, onClose }: SkillDetailModalProps) {
  const [skill, setSkill] = useState<SkillDetail | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (open && skillName) {
      setLoading(true)
      getSkill(skillName)
        .then(setSkill)
        .catch((e) => {
          console.error('Failed to load skill:', e)
        })
        .finally(() => setLoading(false))
    } else {
      setSkill(null)
    }
  }, [open, skillName])

  if (!skill) {
    return (
      <Modal
        open={open}
        onCancel={onClose}
        title="技能详情"
        footer={null}
        width={800}
        loading={loading}
      />
    )
  }

  const items = [
    {
      key: 'overview',
      label: '概览',
      children: (
        <Descriptions column={1} bordered size="small">
          <Descriptions.Item label="名称">{skill.name}</Descriptions.Item>
          <Descriptions.Item label="描述">{skill.description}</Descriptions.Item>
          <Descriptions.Item label="来源">
            <Tag color={SOURCE_COLOR[skill.source]}>{SOURCE_LABEL[skill.source]}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="路径">
            <Text code style={{ fontSize: 12 }}>
              {skill.path}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="优先级">{skill.priority}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={skill.eligible ? 'success' : 'error'}>
              {skill.eligible ? '满足条件' : '不满足条件'}
            </Tag>
            <Tag color={skill.enabled ? 'success' : 'default'} style={{ marginLeft: 8 }}>
              {skill.enabled ? '已启用' : '已禁用'}
            </Tag>
          </Descriptions.Item>
          {skill.license && (
            <Descriptions.Item label="许可证">{skill.license}</Descriptions.Item>
          )}
          {skill.compatibility && (
            <Descriptions.Item label="兼容性">{skill.compatibility}</Descriptions.Item>
          )}
          {skill.disable_model_invocation && (
            <Descriptions.Item label="调用方式">
              <Tag color="purple">手动调用</Tag>
            </Descriptions.Item>
          )}
          {skill.requires && (
            <Descriptions.Item label="依赖要求">
              {skill.requires.bins && skill.requires.bins.length > 0 && (
                <div>
                  <Text strong>二进制文件：</Text>
                  {skill.requires.bins.map((bin) => (
                    <Tag key={bin} style={{ marginTop: 4 }}>
                      {bin}
                    </Tag>
                  ))}
                </div>
              )}
              {skill.requires.env && skill.requires.env.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text strong>环境变量：</Text>
                  {skill.requires.env.map((env) => (
                    <Tag key={env} style={{ marginTop: 4 }}>
                      {env}
                    </Tag>
                  ))}
                </div>
              )}
              {skill.requires.config && skill.requires.config.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text strong>配置项：</Text>
                  {skill.requires.config.map((cfg) => (
                    <Tag key={cfg} style={{ marginTop: 4 }}>
                      {cfg}
                    </Tag>
                  ))}
                </div>
              )}
            </Descriptions.Item>
          )}
          {skill.metadata && Object.keys(skill.metadata).length > 0 && (
            <Descriptions.Item label="元数据">
              {Object.entries(skill.metadata).map(([key, value]) => (
                <div key={key} style={{ marginBottom: 4 }}>
                  <Text strong>{key}:</Text> <Text>{value}</Text>
                </div>
              ))}
            </Descriptions.Item>
          )}
        </Descriptions>
      ),
    },
    {
      key: 'content',
      label: '内容',
      children: (
        <div
          style={{
            maxHeight: '60vh',
            overflow: 'auto',
            padding: '12px',
            background: '#fafafa',
            borderRadius: 4,
          }}
        >
          <ReactMarkdown>{skill.content}</ReactMarkdown>
        </div>
      ),
    },
    ...(skill.resources
      ? [
          {
            key: 'resources',
            label: '资源',
            children: (
              <div>
                {skill.resources.scripts && Object.keys(skill.resources.scripts).length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <Text strong>脚本：</Text>
                    <ul style={{ marginTop: 8 }}>
                      {Object.entries(skill.resources.scripts).map(([key, value]) => (
                        <li key={key}>
                          <Text code>{key}</Text>: <Text>{value}</Text>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {skill.resources.references &&
                  Object.keys(skill.resources.references).length > 0 && (
                    <div style={{ marginBottom: 16 }}>
                      <Text strong>参考：</Text>
                      <ul style={{ marginTop: 8 }}>
                        {Object.entries(skill.resources.references).map(([key, value]) => (
                          <li key={key}>
                            <Text code>{key}</Text>: <Text>{value}</Text>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                {skill.resources.assets && Object.keys(skill.resources.assets).length > 0 && (
                  <div>
                    <Text strong>资源文件：</Text>
                    <ul style={{ marginTop: 8 }}>
                      {Object.entries(skill.resources.assets).map(([key, value]) => (
                        <li key={key}>
                          <Text code>{key}</Text>: <Text>{value}</Text>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {(!skill.resources.scripts ||
                  Object.keys(skill.resources.scripts).length === 0) &&
                  (!skill.resources.references ||
                    Object.keys(skill.resources.references).length === 0) &&
                  (!skill.resources.assets || Object.keys(skill.resources.assets).length === 0) && (
                  <Paragraph type="secondary">暂无资源文件</Paragraph>
                )}
              </div>
            ),
          },
        ]
      : []),
  ]

  return (
    <Modal open={open} onCancel={onClose} title="技能详情" footer={null} width={800}>
      <Tabs items={items} />
    </Modal>
  )
}
