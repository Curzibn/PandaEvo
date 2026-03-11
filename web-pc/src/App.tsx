import { useCallback, useEffect, useState } from 'react'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { fetchProviders } from './api/chat'
import ChatPage from './components/ChatPage'
import SetupWizard from './components/SetupWizard'

export default function App() {
  const [needsSetup, setNeedsSetup] = useState(false)
  const [setupChecked, setSetupChecked] = useState(false)

  useEffect(() => {
    fetchProviders().then((list) => {
      setNeedsSetup(!list.some((p) => p.models.length > 0))
      setSetupChecked(true)
    }).catch(() => {
      setSetupChecked(true)
    })
  }, [])

  const onSetupComplete = useCallback(() => setNeedsSetup(false), [])

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: { colorPrimary: '#1677ff', borderRadius: 8 },
      }}
    >
      {setupChecked && needsSetup && <SetupWizard onComplete={onSetupComplete} />}
      {setupChecked && !needsSetup && <ChatPage />}
    </ConfigProvider>
  )
}
