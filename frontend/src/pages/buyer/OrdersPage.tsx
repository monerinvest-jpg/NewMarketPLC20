import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { List, Tag, Typography, Card, Pagination, Empty, Spin } from 'antd'
import { ordersApi } from '@/api'
import type { Order } from '@/types'
import dayjs from 'dayjs'

const { Title, Text } = Typography

const statusLabels: Record<string, string> = {
  pending_payment: 'Ожидает оплаты',
  paid: 'Оплачен',
  processing: 'В обработке',
  shipped: 'Отправлен',
  delivered: 'Доставлен',
  completed: 'Завершён',
  cancelled: 'Отменён',
  refunded: 'Возврат',
}

const statusColors: Record<string, string> = {
  pending_payment: 'orange',
  paid: 'blue',
  processing: 'geekblue',
  shipped: 'cyan',
  delivered: 'green',
  completed: 'success',
  cancelled: 'red',
  refunded: 'purple',
}

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    ordersApi.list({ page, page_size: 10 })
      .then((res) => { setOrders(res.items); setTotal(res.total) })
      .finally(() => setLoading(false))
  }, [page])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  if (orders.length === 0) {
    return <Empty description="У вас пока нет заказов" style={{ margin: 80 }} />
  }

  return (
    <div>
      <Title level={3}>Мои заказы</Title>
      <List
        dataSource={orders}
        renderItem={(order) => (
          <Link to={`/orders/${order.id}`}>
            <Card style={{ marginBottom: 12 }} hoverable bodyStyle={{ padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <Text strong>Заказ #{order.id}</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    {dayjs(order.created_at).format('DD.MM.YYYY HH:mm')} · {order.items.length} товар(ов)
                  </Text>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <Tag color={statusColors[order.status]}>{statusLabels[order.status]}</Tag>
                  <br />
                  <Text strong style={{ fontSize: 16, color: '#b45309' }}>
                    {parseFloat(order.total_price).toLocaleString('ru')} ₽
                  </Text>
                </div>
              </div>
            </Card>
          </Link>
        )}
      />
      <Pagination
        current={page} total={total} pageSize={10}
        style={{ textAlign: 'center', marginTop: 16 }}
        onChange={setPage} showSizeChanger={false}
      />
    </div>
  )
}
