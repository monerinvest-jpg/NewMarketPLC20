import { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Typography, Spin, Empty, Table } from 'antd'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { adminApi } from '@/api'
import type { SellerAnalytics } from '@/types'

const { Title } = Typography

export default function SellerAnalyticsPage() {
  const [data, setData] = useState<SellerAnalytics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminApi.sellerAnalytics().then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (!data) return <Empty description="Нет данных" />

  return (
    <div>
      <Title level={3}>Аналитика продаж</Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card><Statistic title="Товаров продано" value={data.items_sold} /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card><Statistic title="Заработано всего" value={data.total_earned} suffix="₽" valueStyle={{ color: '#3f8600' }} /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card><Statistic title="Текущий баланс" value={data.current_balance} suffix="₽" valueStyle={{ color: '#b45309' }} /></Card>
        </Col>
      </Row>

      <Card title="Выручка за последние 30 дней" style={{ marginBottom: 24 }}>
        {data.revenue_by_day.length === 0 ? (
          <Empty description="Пока нет продаж" />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.revenue_by_day}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => `${v.toLocaleString('ru')} ₽`} />
              <Line type="monotone" dataKey="revenue" stroke="#b45309" strokeWidth={2} name="Выручка" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>

      <Card title="Топ-5 товаров">
        {data.top_products.length === 0 ? (
          <Empty description="Пока нет продаж" />
        ) : (
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={data.top_products}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="title" tick={{ fontSize: 10 }} interval={0} angle={-15} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="qty" fill="#b45309" name="Продано шт." />
                </BarChart>
              </ResponsiveContainer>
            </Col>
            <Col xs={24} md={12}>
              <Table
                dataSource={data.top_products}
                rowKey="title"
                pagination={false}
                size="small"
                columns={[
                  { title: 'Товар', dataIndex: 'title' },
                  { title: 'Шт.', dataIndex: 'qty', width: 70 },
                  { title: 'Выручка', dataIndex: 'revenue', render: (v) => `${v.toLocaleString('ru')} ₽` },
                ]}
              />
            </Col>
          </Row>
        )}
      </Card>
    </div>
  )
}
