import { useEffect, useState } from 'react'
import { Card, Typography, Row, Col, Statistic, Spin, Divider, Alert } from 'antd'
import { adminApi } from '@/api'

const { Title, Text } = Typography

export default function AdminReconciliation() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminApi.reconciliation().then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (!data) return <Card>Нет данных</Card>

  const money = (v: number) => `${v.toLocaleString('ru')} ₽`

  return (
    <div>
      <Title level={3}>Финансовая реконсиляция</Title>
      <Text type="secondary">Сводка денежных потоков платформы для сверки.</Text>

      <Row gutter={16} style={{ marginTop: 16, marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card><Statistic title="Валовые продажи (GMV)" value={data.gross_sales} formatter={() => money(data.gross_sales)} valueStyle={{ color: '#b45309' }} /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card><Statistic title="Комиссия платформы" value={data.platform_commission} formatter={() => money(data.platform_commission)} valueStyle={{ color: '#237804' }} /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card><Statistic title="Возвраты" value={data.refunds_total} formatter={() => money(data.refunds_total)} valueStyle={{ color: '#cf1322' }} /></Card>
        </Col>
      </Row>

      <Card title="Расчёты с продавцами" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col xs={12} sm={6}><Statistic title="Выплачено (net)" value={data.seller_net_paid} formatter={() => money(data.seller_net_paid)} /></Col>
          <Col xs={12} sm={6}><Statistic title="Ожидает (net)" value={data.seller_net_pending} formatter={() => money(data.seller_net_pending)} /></Col>
          <Col xs={12} sm={6}><Statistic title="Выводы выплачены" value={data.payouts_paid} formatter={() => money(data.payouts_paid)} /></Col>
          <Col xs={12} sm={6}><Statistic title="Выводы в очереди" value={data.payouts_pending} formatter={() => money(data.payouts_pending)} /></Col>
        </Row>
        <Divider />
        <Alert
          type="info"
          message={`Текущие обязательства перед продавцами: ${money(data.outstanding_liability)}`}
          description="Net, заработанный продавцами, но ещё не выплаченный — это сумма, которую платформа должна перечислить."
        />
      </Card>
    </div>
  )
}
