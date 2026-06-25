import { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Typography, Spin } from 'antd'
import {
  ShoppingCartOutlined, DollarOutlined, UserOutlined,
  AppstoreOutlined, WarningOutlined,
} from '@ant-design/icons'
import { adminApi } from '@/api'
import type { DashboardStats } from '@/types'

const { Title } = Typography

export default function AdminDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)

  useEffect(() => {
    adminApi.dashboard().then(setStats)
  }, [])

  if (!stats) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div>
      <Title level={3}>Дашборд</Title>
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic
              title="Заказы всего" value={stats.total_orders}
              prefix={<ShoppingCartOutlined />}
            />
            <Typography.Text type="secondary">+{stats.orders_today} сегодня</Typography.Text>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Выручка всего" value={parseFloat(stats.total_revenue)}
              prefix={<DollarOutlined />} suffix="₽"
            />
            <Typography.Text type="secondary">+{parseFloat(stats.revenue_today).toLocaleString('ru')} ₽ сегодня</Typography.Text>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Пользователи" value={stats.total_users} prefix={<UserOutlined />} />
            <Typography.Text type="secondary">+{stats.new_users_today} сегодня</Typography.Text>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Товары" value={stats.total_products} prefix={<AppstoreOutlined />} />
            <Typography.Text type="secondary">{stats.pending_moderation} на модерации</Typography.Text>
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="Открытые жалобы" value={stats.open_reports}
              prefix={<WarningOutlined />}
              valueStyle={{ color: stats.open_reports > 0 ? '#cf1322' : undefined }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
