import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Table, Row, Col, Statistic, Spin, Alert, Typography, Space,
} from 'antd'
import { adminApi } from '@/api'

const { Title, Text } = Typography

const money = (v: any) => `${parseFloat(v || 0).toLocaleString('ru')} ₽`
const dt = (v: string) => new Date(v).toLocaleString('ru')

export default function AdminShopDetail() {
  const { id } = useParams()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    adminApi.shopDetail(Number(id)).then(setData).finally(() => setLoading(false))
  }, [id])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (!data) return <Alert type="error" message="Магазин не найден" />

  const shop = data.shop
  const s = data.stats

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      <Space style={{ marginBottom: 12 }}>
        <Link to="/admin/shops">← К списку магазинов</Link>
        {data.owner && <Link to={`/admin/users/${data.owner.id}`}>· Владелец: {data.owner.full_name}</Link>}
      </Space>
      <Title level={3} style={{ marginTop: 0 }}>
        {shop.name} <Text type="secondary" style={{ fontSize: 15 }}>#{shop.id}</Text>{' '}
        <Tag color={shop.status === 'active' ? 'green' : shop.status === 'suspended' ? 'red' : 'orange'}>{shop.status}</Tag>
      </Title>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Оборот (GMV)" value={parseFloat(s.gross_sales)} precision={2} suffix="₽" /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Комиссия платформы" value={parseFloat(s.platform_fees)} precision={2} suffix="₽" valueStyle={{ color: '#b45309' }} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Заработок продавца" value={parseFloat(s.seller_net)} precision={2} suffix="₽" /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Выплачено" value={parseFloat(s.payouts_paid)} precision={2} suffix="₽" /></Card></Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card title="Магазин" size="small" style={{ marginBottom: 16 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Описание">{shop.description || '—'}</Descriptions.Item>
              <Descriptions.Item label="Комиссия">{shop.commission_percent != null ? `${shop.commission_percent}%` : 'по умолчанию'}</Descriptions.Item>
              <Descriptions.Item label="Товаров">{s.products_count}</Descriptions.Item>
              <Descriptions.Item label="Заказов">{s.orders_count}</Descriptions.Item>
              <Descriptions.Item label="Активен">{shop.is_active ? 'да' : 'нет'}</Descriptions.Item>
              {shop.moderation_reason && <Descriptions.Item label="Причина модерации">{shop.moderation_reason}</Descriptions.Item>}
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="Владелец" size="small" style={{ marginBottom: 16 }}>
            {data.owner ? (
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Имя"><Link to={`/admin/users/${data.owner.id}`}>{data.owner.full_name}</Link></Descriptions.Item>
                <Descriptions.Item label="Email">{data.owner.email}</Descriptions.Item>
                <Descriptions.Item label="Роль">{data.owner.role}</Descriptions.Item>
                <Descriptions.Item label="Баланс">{money(data.owner.balance)}</Descriptions.Item>
              </Descriptions>
            ) : <Text type="secondary">—</Text>}
          </Card>
        </Col>
      </Row>

      <Card title="Последние заказы магазина" size="small">
        <Table
          rowKey="id" size="small" pagination={false} dataSource={data.recent_orders}
          columns={[
            { title: '№', dataIndex: 'id', render: (v) => <Link to={`/orders/${v}`}>#{v}</Link> },
            { title: 'Сумма', dataIndex: 'total_price', render: money },
            { title: 'Статус', dataIndex: 'status' },
            { title: 'Дата', dataIndex: 'created_at', render: dt },
          ]}
        />
      </Card>
    </div>
  )
}
