import { useEffect, useState } from 'react'
import { Typography, Card, Alert, Input, Button, Space, Spin, message } from 'antd'
import { adminApi } from '@/api'

const { Title, Paragraph, Text } = Typography

export default function AdminMetrics() {
  const [url, setUrl] = useState('')
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    adminApi.getSettings()
      .then((rows: any[]) => {
        const v = rows.find((r) => r.key === 'grafana_dashboard_url')?.value || ''
        setUrl(v); setDraft(v)
      })
      .finally(() => setLoading(false))
  }, [])

  const save = async () => {
    setSaving(true)
    try {
      await adminApi.updateSetting('grafana_dashboard_url', draft)
      setUrl(draft)
      message.success('Сохранено')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    } finally { setSaving(false) }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div>
      <Title level={3}>Метрики (Grafana)</Title>
      <Paragraph type="secondary">
        Технические и бизнес-метрики платформы из Prometheus отображаются в Grafana.
        Укажите URL дашборда (режим kiosk/anonymous или signed-URL) — он встроится ниже.
      </Paragraph>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space.Compact style={{ width: '100%', maxWidth: 800 }}>
          <Input
            value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="https://grafana.example.com/d/abc/marketplace?kiosk&theme=light"
          />
          <Button type="primary" loading={saving} onClick={save}>Сохранить</Button>
        </Space.Compact>
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Совет: в Grafana включите анонимный доступ или kiosk-режим, иначе iframe попросит логин.
          </Text>
        </div>
      </Card>

      {url ? (
        <Card bodyStyle={{ padding: 0 }}>
          <iframe
            title="Grafana"
            src={url}
            style={{ width: '100%', height: '78vh', border: 'none', borderRadius: 8 }}
          />
        </Card>
      ) : (
        <Alert
          type="info" showIcon
          message="Дашборд не настроен"
          description="Поднимите Prometheus + Grafana (см. infra/ansible/observability.yml), затем вставьте URL дашборда выше."
        />
      )}
    </div>
  )
}
