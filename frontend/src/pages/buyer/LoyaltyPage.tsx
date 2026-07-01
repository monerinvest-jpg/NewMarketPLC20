import { useEffect, useState } from 'react'
import { Card, Typography, Progress, Tag, Row, Col, Statistic, Alert, List } from 'antd'
import { CrownOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { loyaltyApi } from '@/api'
import type { LoyaltyStatus } from '@/types'
import dayjs from 'dayjs'

const { Title, Text, Paragraph } = Typography

export default function LoyaltyPage() {
  const [status, setStatus] = useState<LoyaltyStatus | null>(null)

  useEffect(() => { loyaltyApi.me().then(setStatus).catch(() => {}) }, [])

  if (!status) return null
  const cur = status.current
  const next = status.next
  const spend = Number(status.qualifying_spend)
  const progressPct = next
    ? Math.min(100, Math.round((spend - Number(cur?.min_spend || 0)) / (Number(next.min_spend) - Number(cur?.min_spend || 0)) * 100))
    : 100

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: 24 }}>
      <Title level={3}><CrownOutlined /> Программа лояльности</Title>

      <Card style={{ marginBottom: 16, borderTop: `4px solid ${cur?.color || '#b45309'}` }}>
        <Row gutter={16} align="middle">
          <Col xs={24} md={8}>
            <Text type="secondary">Ваш уровень</Text>
            <Title level={2} style={{ margin: '4px 0', color: cur?.color }}>{cur?.name || '—'}</Title>
            <Tag color="orange">Кэшбэк {Number(cur?.cashback_percent || 0)}%</Tag>
            {cur?.free_shipping && <Tag color="green">Бесплатная доставка</Tag>}
          </Col>
          <Col xs={24} md={16}>
            <Statistic title="Зачтённые покупки" value={`${spend.toLocaleString('ru')} ₽`} />
            {next ? (
              <div style={{ marginTop: 12 }}>
                <Text type="secondary">До уровня «{next.name}»: {Number(status.to_next_amount).toLocaleString('ru')} ₽</Text>
                <Progress percent={progressPct} strokeColor={next.color || '#b45309'} />
              </div>
            ) : (
              <Tag color="gold" style={{ marginTop: 12 }}>Максимальный уровень достигнут 🎉</Tag>
            )}
          </Col>
        </Row>
      </Card>

      {status.days_to_downgrade != null && (
        <Alert
          type={status.days_to_downgrade <= 14 ? 'warning' : 'info'} showIcon icon={<ClockCircleOutlined />}
          style={{ marginBottom: 16 }}
          message={`До понижения уровня: ${status.days_to_downgrade} дн.`}
          description={status.downgrade_at
            ? `Совершите покупку до ${dayjs(status.downgrade_at).format('DD.MM.YYYY')}, чтобы сохранить уровень «${cur?.name}».`
            : undefined}
        />
      )}

      {cur?.perks && (
        <Card title="Ваши привилегии" style={{ marginBottom: 16 }}>
          <Paragraph>{cur.perks}</Paragraph>
        </Card>
      )}

      <Card title="Все уровни">
        <List
          dataSource={status.all_tiers}
          renderItem={(t: any) => (
            <List.Item style={{ opacity: cur && t.level <= cur.level ? 1 : 0.7 }}>
              <List.Item.Meta
                avatar={<CrownOutlined style={{ fontSize: 22, color: t.color }} />}
                title={<span>{t.name} {cur?.id === t.id && <Tag color="orange">текущий</Tag>}</span>}
                description={`От ${Number(t.min_spend).toLocaleString('ru')} ₽ · кэшбэк ${Number(t.cashback_percent)}%${t.free_shipping ? ' · бесплатная доставка' : ''}${t.retention_days ? ` · активность раз в ${t.retention_days} дн.` : ''}`}
              />
            </List.Item>
          )}
        />
      </Card>
    </div>
  )
}
