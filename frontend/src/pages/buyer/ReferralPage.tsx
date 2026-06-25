import { useEffect, useState } from 'react'
import { Card, Typography, Statistic, Row, Col, Input, Button, message, Alert, Spin } from 'antd'
import { CopyOutlined, ShareAltOutlined } from '@ant-design/icons'
import { usersApi } from '@/api'
import type { ReferralStats } from '@/types'

const { Title, Text, Paragraph } = Typography

export default function ReferralPage() {
  const [stats, setStats] = useState<ReferralStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    usersApi.getReferralStats().then(setStats).finally(() => setLoading(false))
  }, [])

  const handleCopy = () => {
    if (stats) {
      navigator.clipboard.writeText(stats.referral_link)
      message.success('Ссылка скопирована!')
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (!stats) return null

  return (
    <div style={{ maxWidth: 700, margin: '0 auto' }}>
      <Title level={3}>Реферальная программа</Title>
      <Paragraph type="secondary">
        Приглашайте друзей и получайте бонусы за каждого, кто совершит покупку или начнёт продавать на платформе!
      </Paragraph>

      <Card style={{ marginBottom: 24, background: 'linear-gradient(135deg, #fff7ed, #ffedd5)' }}>
        <Text strong>Ваша реферальная ссылка:</Text>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <Input value={stats.referral_link} readOnly size="large" />
          <Button type="primary" icon={<CopyOutlined />} size="large" onClick={handleCopy}>
            Скопировать
          </Button>
        </div>
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          Код: <Text strong copyable>{stats.referral_code}</Text>
        </Text>
      </Card>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card><Statistic title="Приглашено" value={stats.total_referred} /></Card>
        </Col>
        <Col span={8}>
          <Card><Statistic title="Выплачено наград" value={stats.paid_rewards} /></Card>
        </Col>
        <Col span={8}>
          <Card><Statistic title="Бонусный баланс" value={parseFloat(stats.bonus_balance)} suffix="₽" /></Card>
        </Col>
      </Row>

      <Alert
        type="info"
        showIcon
        message="Как это работает"
        description={
          <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
            <li>Поделитесь ссылкой с другом</li>
            <li>Если друг — покупатель: после его первой покупки вы получите бонусные баллы</li>
            <li>Если друг — продавец: после его первого завершённого заказа вы получите денежное вознаграждение на баланс</li>
            <li>Бонусными баллами можно оплатить часть любого вашего заказа</li>
          </ul>
        }
      />
    </div>
  )
}
