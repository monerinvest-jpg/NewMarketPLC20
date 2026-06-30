import { useEffect, useState } from 'react'
import { Card, Form, Input, Button, Typography, message, Spin, Row, Col, Switch, Tabs } from 'antd'
import { adminApi } from '@/api'
import type { Setting } from '@/types'

const { Title, Text } = Typography

const sections: Record<string, { title: string; keys: string[] }> = {
  commission: { title: 'Комиссии и платформа', keys: ['global_commission_percent', 'enable_premoderation', 'enable_review_premoderation', 'enable_paid_placement', 'site_name', 'site_description', 'support_email'] },
  referral: { title: 'Реферальная программа', keys: ['referral_buyer_bonus_percent', 'referral_buyer_min_order_amount', 'referral_seller_bonus_percent', 'referral_bonus_max_discount_percent'] },
  orders: { title: 'Заказы', keys: ['order_auto_complete_days', 'order_auto_delivered_days'] },
  delivery: { title: 'Доставка', keys: ['delivery_enabled_services'] },
  gifts: { title: 'Подарки', keys: ['gift_wrap_price'] },
  bnpl: { title: 'Оплата частями (BNPL)', keys: ['bnpl_enabled', 'bnpl_provider_name', 'bnpl_parts', 'bnpl_interval_days', 'bnpl_min_order'] },
  trust: { title: 'Доверие и VIP', keys: ['trust_badges_enabled', 'vip_price', 'vip_duration_days', 'vip_auto_rating_min', 'vip_auto_reviews_min', 'kyc_required_for_payout'] },
  integrations: { title: 'Интеграции (API-ключи)', keys: ['yookassa_shop_id', 'yookassa_secret_key', 'cdek_client_id', 'cdek_client_secret'] },
}

export default function AdminSettings() {
  const [settings, setSettings] = useState<Setting[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    adminApi.getSettings().then((data) => {
      setSettings(data)
      const values: Record<string, string> = {}
      data.forEach((s) => { values[s.key] = s.value })
      form.setFieldsValue(values)
    }).finally(() => setLoading(false))
  }, [])

  const settingsMap = Object.fromEntries(settings.map((s) => [s.key, s]))

  const handleSave = async (values: Record<string, string>) => {
    setSaving(true)
    try {
      await adminApi.bulkUpdateSettings(values)
      message.success('Настройки сохранены')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  const renderField = (key: string) => {
    const setting = settingsMap[key]
    if (!setting) return null

    if (key === 'enable_premoderation' || key === 'enable_review_premoderation' || key === 'enable_paid_placement') {
      return (
        <Form.Item key={key} label={setting.description} valuePropName="checked" name={key}
          getValueFromEvent={(checked) => String(checked)}
          getValueProps={(value) => ({ checked: value === 'true' })}
        >
          <Switch />
        </Form.Item>
      )
    }

    const isSecret = key.includes('secret') || key.includes('key')
    return (
      <Form.Item key={key} label={setting.description || key} name={key}>
        {isSecret ? <Input.Password /> : <Input />}
      </Form.Item>
    )
  }

  return (
    <div>
      <Title level={3}>Настройки платформы</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        Все параметры платформы редактируются здесь. Изменения применяются немедленно.
      </Text>

      <Form form={form} layout="vertical" onFinish={handleSave}>
        <Tabs
          items={Object.entries(sections).map(([key, section]) => ({
            key,
            label: section.title,
            children: (
              <Card>
                <Row gutter={24}>
                  {section.keys.map((k) => (
                    <Col span={12} key={k}>{renderField(k)}</Col>
                  ))}
                </Row>
              </Card>
            ),
          }))}
        />
        <Button type="primary" htmlType="submit" size="large" loading={saving} style={{ marginTop: 24 }}>
          Сохранить все настройки
        </Button>
      </Form>
    </div>
  )
}
