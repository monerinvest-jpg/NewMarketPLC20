import { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Typography, Spin, Empty, Table } from 'antd'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { adminApi } from '@/api'
import type { PlatformAnalytics } from '@/types'

const { Title } = Typography

export default function AdminPlatformAnalytics() {
  const [data, setData] = useState<PlatformAnalytics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminApi.platformAnalytics().then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (!data) return <Empty description="Нет данных" />

  return (
    <div>
      <Title level={3}>Аналитика платформы</Title>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12}>
          <Card><Statistic title="GMV (оборот)" value={data.gmv} suffix="₽" valueStyle={{ color: '#b45309' }} /></Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card><Statistic title="Доход платформы (комиссии)" value={data.platform_revenue} suffix="₽" valueStyle={{ color: '#4d7c0f' }} /></Card>
        </Col>
      </Row>

      {(data as any).finance && (() => {
        const f = (data as any).finance
        return (
          <>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col xs={12} md={6}><Card size="small"><Statistic title="Чистая прибыль" value={f.net_profit} suffix="₽" valueStyle={{ color: f.net_profit >= 0 ? '#4d7c0f' : '#cf1322' }} /></Card></Col>
              <Col xs={12} md={6}><Card size="small"><Statistic title="Расход на рефералов" value={f.referral_cost} suffix="₽" /></Card></Col>
              <Col xs={12} md={6}><Card size="small"><Statistic title="Выплачено всего" value={f.payouts_paid} suffix="₽" /></Card></Col>
              <Col xs={12} md={6}><Card size="small"><Statistic title="Выплаты в ожидании" value={f.payouts_pending} suffix="₽" valueStyle={{ color: '#d46b08' }} /></Card></Col>
            </Row>
            <Card size="small" title="Обязательства перед пользователями (мы держим на балансах)" style={{ marginBottom: 24 }}>
              <Row gutter={16}>
                <Col xs={12} md={6}><Statistic title="Балансы продавцов" value={f.liabilities.seller_balances} suffix="₽" /></Col>
                <Col xs={12} md={6}><Statistic title="Реферальные балансы" value={f.liabilities.referral_balances} suffix="₽" /></Col>
                <Col xs={12} md={6}><Statistic title="Бонусные балансы" value={f.liabilities.bonus_balances} suffix="₽" /></Col>
                <Col xs={12} md={6}><Statistic title="Ожидающие выводы" value={f.liabilities.pending_payouts} suffix="₽" /></Col>
              </Row>
            </Card>
          </>
        )
      })()}

      <Card title="Заказы и выручка за 30 дней" style={{ marginBottom: 24 }}>
        {data.trend.length === 0 ? <Empty /> : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.trend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line yAxisId="left" type="monotone" dataKey="revenue" stroke="#b45309" strokeWidth={2} name="Выручка ₽" />
              <Line yAxisId="right" type="monotone" dataKey="orders" stroke="#3f8600" strokeWidth={2} name="Заказы" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card title="Топ магазинов">
            <Table
              dataSource={data.top_shops} rowKey="name" pagination={false} size="small"
              columns={[
                { title: 'Магазин', dataIndex: 'name' },
                { title: 'Продаж', dataIndex: 'items', width: 80 },
                { title: 'Оборот', dataIndex: 'net', render: (v) => `${v.toLocaleString('ru')} ₽` },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="Новые пользователи за 30 дней">
            {data.user_growth.length === 0 ? <Empty /> : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={data.user_growth}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#b45309" name="Новые юзеры" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
