import { useEffect, useState } from 'react'
import { Card, Typography, Button, Input, message, Alert, Tag, Space, Modal } from 'antd'
import { SafetyOutlined } from '@ant-design/icons'
import { twoFAApi } from '@/api'

const { Title, Text, Paragraph } = Typography

export default function TwoFactorPage() {
  const [enabled, setEnabled] = useState(false)
  const [setupData, setSetupData] = useState<{ secret: string; otpauth_url: string; backup_codes: string[] } | null>(null)
  const [code, setCode] = useState('')
  const [disableModal, setDisableModal] = useState(false)
  const [disableCode, setDisableCode] = useState('')

  const loadStatus = () => twoFAApi.status().then((s) => setEnabled(s.enabled))
  useEffect(() => { loadStatus() }, [])

  const handleSetup = async () => {
    const data = await twoFAApi.setup()
    setSetupData(data)
  }

  const handleVerify = async () => {
    try {
      await twoFAApi.verify(code)
      message.success('Двухфакторная аутентификация включена')
      setSetupData(null); setCode(''); loadStatus()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Неверный код')
    }
  }

  const handleDisable = async () => {
    try {
      await twoFAApi.disable(disableCode)
      message.success('2FA отключена')
      setDisableModal(false); setDisableCode(''); loadStatus()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Неверный код')
    }
  }

  return (
    <div style={{ maxWidth: 640 }}>
      <Title level={3}><SafetyOutlined /> Двухфакторная аутентификация</Title>

      {enabled ? (
        <Card>
          <Alert type="success" showIcon message="2FA включена" description="Ваш аккаунт защищён одноразовыми кодами." style={{ marginBottom: 16 }} />
          <Button danger onClick={() => setDisableModal(true)}>Отключить 2FA</Button>
        </Card>
      ) : !setupData ? (
        <Card>
          <Paragraph type="secondary">
            Защитите аккаунт: при входе потребуется код из приложения-аутентификатора (Google Authenticator, Authy и др.).
          </Paragraph>
          <Button type="primary" onClick={handleSetup}>Настроить 2FA</Button>
        </Card>
      ) : (
        <Card title="Завершите настройку">
          <Paragraph>1. Добавьте секрет в приложение-аутентификатор:</Paragraph>
          <Alert
            type="info" style={{ marginBottom: 12 }}
            message={<Text copyable code style={{ fontSize: 16 }}>{setupData.secret}</Text>}
          />
          <Paragraph type="secondary" style={{ fontSize: 12, wordBreak: 'break-all' }}>
            URL: {setupData.otpauth_url}
          </Paragraph>

          <Paragraph>2. Сохраните резервные коды (одноразовые, на случай потери телефона):</Paragraph>
          <Alert type="warning" style={{ marginBottom: 12 }} message={
            <Space wrap>{setupData.backup_codes.map((c) => <Tag key={c} style={{ fontFamily: 'monospace' }}>{c}</Tag>)}</Space>
          } />

          <Paragraph>3. Введите код из приложения для подтверждения:</Paragraph>
          <Space>
            <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="000000" maxLength={6} style={{ width: 140 }} />
            <Button type="primary" onClick={handleVerify}>Подтвердить</Button>
          </Space>
        </Card>
      )}

      <Modal title="Отключить 2FA" open={disableModal} onCancel={() => setDisableModal(false)} onOk={handleDisable}>
        <Paragraph>Введите текущий код из приложения, чтобы отключить:</Paragraph>
        <Input value={disableCode} onChange={(e) => setDisableCode(e.target.value)} placeholder="000000" maxLength={6} style={{ width: 140 }} />
      </Modal>
    </div>
  )
}
