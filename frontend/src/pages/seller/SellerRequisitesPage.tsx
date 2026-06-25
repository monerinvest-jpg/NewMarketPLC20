import { useEffect, useState } from 'react'
import { Card, Typography, Button, Form, message, Spin } from 'antd'
import { shopsApi } from '@/api'
import RequisitesFields from '@/components/common/RequisitesFields'

const { Title, Text } = Typography

export default function SellerRequisitesPage() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    shopsApi.getMyRequisites()
      .then((r) => form.setFieldsValue(r))
      .catch(() => {}) // none yet — empty form
      .finally(() => setLoading(false))
  }, [])

  const onFinish = async (values: any) => {
    setSaving(true)
    try {
      await shopsApi.updateMyRequisites(values)
      message.success('Реквизиты сохранены')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div style={{ maxWidth: 600 }}>
      <Title level={3}>Налоговые реквизиты</Title>
      <Text type="secondary">Эти данные используются для документов и выплат. Поля зависят от налогового режима.</Text>
      <Card style={{ marginTop: 16 }}>
        <Form layout="vertical" form={form} onFinish={onFinish}>
          <RequisitesFields form={form} />
          <Button type="primary" htmlType="submit" loading={saving} style={{ marginTop: 8 }}>
            Сохранить
          </Button>
        </Form>
      </Card>
    </div>
  )
}
