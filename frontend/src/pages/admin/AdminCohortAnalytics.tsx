import { useEffect, useState } from 'react'
import { Card, Typography, Row, Col, Statistic, Table, Spin, Empty } from 'antd'
import { adminApi } from '@/api'

const { Title, Text } = Typography

function retentionColor(pct: number) {
  if (pct >= 60) return '#237804'
  if (pct >= 40) return '#52c41a'
  if (pct >= 20) return '#bae637'
  if (pct > 0) return '#fff1b8'
  return '#fafafa'
}

export default function AdminCohortAnalytics() {
  const [cohorts, setCohorts] = useState<any>(null)
  const [ltv, setLtv] = useState<any>(null)
  const [funnel, setFunnel] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      adminApi.cohorts(6).catch(() => null),
      adminApi.ltv().catch(() => null),
      adminApi.funnel(30).catch(() => null),
    ]).then(([c, l, f]) => { setCohorts(c); setLtv(l); setFunnel(f) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  const maxOffset = cohorts?.cohorts?.reduce((m: number, c: any) => Math.max(m, c.retention.length), 0) || 0

  return (
    <div>
      <Title level={3}>Когортная аналитика</Title>

      {/* LTV */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card><Statistic title="Средний LTV покупателя" value={ltv?.avg_ltv || 0} suffix="₽" valueStyle={{ color: '#b45309' }} /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card><Statistic title="Среднее число заказов" value={ltv?.avg_orders || 0} precision={2} /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card><Statistic title="Покупателей с заказами" value={ltv?.buyer_count || 0} /></Card>
        </Col>
      </Row>

      {/* Funnel */}
      <Card title="Воронка конверсии (30 дней)" style={{ marginBottom: 24 }}>
        {!funnel?.stages?.length ? <Empty /> : (
          <div>
            {funnel.stages.map((s: any, i: number) => (
              <div key={i} style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <Text>{s.stage}</Text>
                  <Text strong>{s.count.toLocaleString('ru')} ({s.percent}%)</Text>
                </div>
                <div style={{ background: '#f0f0f0', borderRadius: 6, overflow: 'hidden', height: 24 }}>
                  <div style={{ width: `${s.percent}%`, height: '100%', background: '#b45309', transition: 'width .4s' }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Cohort retention heatmap */}
      <Card title="Удержание по когортам (месяц регистрации → активность)" style={{ marginBottom: 24 }}>
        {!cohorts?.cohorts?.length ? <Empty /> : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ padding: 8, textAlign: 'left', borderBottom: '1px solid #eee' }}>Когорта</th>
                  <th style={{ padding: 8, borderBottom: '1px solid #eee' }}>Размер</th>
                  {Array.from({ length: maxOffset }).map((_, i) => (
                    <th key={i} style={{ padding: 8, borderBottom: '1px solid #eee' }}>М{i}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cohorts.cohorts.map((c: any) => (
                  <tr key={c.cohort}>
                    <td style={{ padding: 8 }}>{c.cohort}</td>
                    <td style={{ padding: 8, textAlign: 'center' }}>{c.size}</td>
                    {Array.from({ length: maxOffset }).map((_, i) => {
                      const cell = c.retention[i]
                      return (
                        <td key={i} style={{ padding: 8, textAlign: 'center', background: cell ? retentionColor(cell.percent) : '#fafafa' }}>
                          {cell ? `${cell.percent}%` : '—'}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Top buyers */}
      <Card title="Топ покупателей по LTV">
        <Table
          dataSource={ltv?.top_buyers || []}
          rowKey="email"
          pagination={false}
          size="small"
          columns={[
            { title: 'Покупатель', dataIndex: 'email' },
            { title: 'Заказов', dataIndex: 'orders', width: 100 },
            { title: 'Выручка', dataIndex: 'revenue', render: (v) => `${v.toLocaleString('ru')} ₽` },
          ]}
        />
      </Card>
    </div>
  )
}
