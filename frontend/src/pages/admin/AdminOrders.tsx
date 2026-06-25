import { useEffect, useState } from 'react'
import { Table, Tag, Select, Button, Modal, message, Typography, Descriptions, Popconfirm } from 'antd'
import { adminApi } from '@/api'
import type { Order } from '@/types'
import dayjs from 'dayjs'

const { Title } = Typography

const statusLabels: Record<string, { label: string; color: string }> = {
  pending_payment: { label: 'Ожидает оплаты', color: 'orange' },
  paid: { label: 'Оплачен', color: 'blue' },
  processing: { label: 'В обработке', color: 'geekblue' },
  shipped: { label: 'Отправлен', color: 'cyan' },
  delivered: { label: 'Доставлен', color: 'green' },
  completed: { label: 'Завершён', color: 'success' },
  cancelled: { label: 'Отменён', color: 'red' },
  refunded: { label: 'Возврат', color: 'purple' },
}

export default function AdminOrders() {
  const [orders, setOrders] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [detailOrder, setDetailOrder] = useState<Order | null>(null)

  const load = () => {
    setLoading(true)
    adminApi.listOrders({ page, status: statusFilter })
      .then((res) => { setOrders(res.items); setTotal(res.total) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page, statusFilter])

  const handleStatusChange = async (orderId: number, status: string) => {
    await adminApi.updateOrderStatus(orderId, status)
    message.success('Статус обновлён')
    load()
  }

  const handleRefund = async (orderId: number) => {
    try {
      await adminApi.refundOrder(orderId)
      message.success('Возврат инициирован')
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка возврата')
    }
  }

  return (
    <div>
      <Title level={3}>Заказы</Title>
      <Select
        placeholder="Все статусы" allowClear style={{ width: 200, marginBottom: 16 }}
        value={statusFilter} onChange={setStatusFilter}
        options={Object.entries(statusLabels).map(([k, v]) => ({ value: k, label: v.label }))}
      />

      <Table
        loading={loading}
        dataSource={orders}
        rowKey="id"
        pagination={{ current: page, total, pageSize: 20, onChange: setPage, showSizeChanger: false }}
        columns={[
          { title: '№', dataIndex: 'id', width: 60 },
          { title: 'Дата', dataIndex: 'created_at', render: (v) => dayjs(v).format('DD.MM.YYYY HH:mm') },
          { title: 'Покупатель ID', dataIndex: 'buyer_id' },
          { title: 'Сумма', dataIndex: 'total_price', render: (v) => `${parseFloat(v).toLocaleString('ru')} ₽` },
          {
            title: 'Статус', dataIndex: 'status',
            render: (s) => <Tag color={statusLabels[s]?.color}>{statusLabels[s]?.label}</Tag>,
          },
          {
            title: 'Действия',
            render: (_, order) => (
              <>
                <Button size="small" onClick={() => setDetailOrder(order)}>Детали</Button>
                {(order.status === 'paid' || order.status === 'processing') && (
                  <Popconfirm title="Инициировать возврат?" onConfirm={() => handleRefund(order.id)}>
                    <Button size="small" danger style={{ marginLeft: 8 }}>Возврат</Button>
                  </Popconfirm>
                )}
              </>
            ),
          },
        ]}
      />

      <Modal
        title={`Заказ #${detailOrder?.id}`}
        open={!!detailOrder}
        onCancel={() => setDetailOrder(null)}
        footer={null}
        width={680}
      >
        {detailOrder && (
          <>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="Статус">
                <Select
                  value={detailOrder.status} style={{ width: 200 }}
                  onChange={(v) => { handleStatusChange(detailOrder.id, v); setDetailOrder({ ...detailOrder, status: v as any }) }}
                  options={Object.entries(statusLabels).map(([k, v]) => ({ value: k, label: v.label }))}
                />
              </Descriptions.Item>
              <Descriptions.Item label="Адрес">{detailOrder.delivery_address}</Descriptions.Item>
              <Descriptions.Item label="Сумма товаров">{parseFloat(detailOrder.subtotal).toLocaleString('ru')} ₽</Descriptions.Item>
              <Descriptions.Item label="Доставка">{parseFloat(detailOrder.delivery_cost).toLocaleString('ru')} ₽</Descriptions.Item>
              <Descriptions.Item label="Комиссия платформы (всего)">{parseFloat(detailOrder.platform_fee).toLocaleString('ru')} ₽ (~{detailOrder.commission_percent_used}%)</Descriptions.Item>
              <Descriptions.Item label="Выплата продавцам (всего)">{parseFloat(detailOrder.seller_net).toLocaleString('ru')} ₽</Descriptions.Item>
              <Descriptions.Item label="Итого">{parseFloat(detailOrder.total_price).toLocaleString('ru')} ₽</Descriptions.Item>
              {detailOrder.delivery_info?.tracking_number && (
                <Descriptions.Item label="Трек-номер">{detailOrder.delivery_info.tracking_number}</Descriptions.Item>
              )}
            </Descriptions>

            <Typography.Title level={5} style={{ marginTop: 16 }}>
              Разбивка по продавцам {detailOrder.items.length > 1 && '(заказ из нескольких магазинов)'}
            </Typography.Title>
            <Table
              size="small"
              pagination={false}
              dataSource={detailOrder.items}
              rowKey="id"
              columns={[
                { title: 'Магазин ID', dataIndex: 'shop_id', width: 90 },
                { title: 'Товар', render: (_, item) => item.product.title },
                { title: 'Кол-во', dataIndex: 'quantity', width: 70 },
                { title: 'Комиссия', dataIndex: 'commission_percent_used', width: 90, render: (v) => `${v}%` },
                { title: 'Выплата', dataIndex: 'seller_net', render: (v) => `${parseFloat(v).toLocaleString('ru')} ₽` },
                {
                  title: 'Статус выплаты', dataIndex: 'payout_status', width: 110,
                  render: (v) => (
                    <Tag color={v === 'paid' ? 'green' : v === 'refunded' ? 'red' : 'orange'}>
                      {v === 'paid' ? 'Выплачено' : v === 'refunded' ? 'Возврат' : 'Ожидание'}
                    </Tag>
                  ),
                },
              ]}
            />
          </>
        )}
      </Modal>
    </div>
  )
}
