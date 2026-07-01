import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Card, Typography, Tag, Steps, Divider, Spin, Empty,
  Descriptions, Button, message, Modal, Input, InputNumber
} from 'antd'
import { ordersApi, returnsApi, subOrdersApi } from '@/api'
import type { Order, FiscalReceipt } from '@/types'
import type { BuyerSubOrder } from '@/api'
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
  pending_payment: 'orange', paid: 'blue', processing: 'geekblue',
  shipped: 'cyan', delivered: 'green', completed: 'success',
  cancelled: 'red', refunded: 'purple',
}

const stepOrder = ['pending_payment', 'paid', 'processing', 'shipped', 'delivered', 'completed']

const subOrderStatusLabels: Record<string, string> = {
  processing: 'В обработке',
  shipped: 'Отправлен',
  delivered: 'Доставлен',
  completed: 'Завершён',
  cancelled: 'Отменён',
}

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [order, setOrder] = useState<Order | null>(null)
  const [subOrders, setSubOrders] = useState<BuyerSubOrder[]>([])
  const [receipts, setReceipts] = useState<FiscalReceipt[]>([])
  const [loading, setLoading] = useState(true)
  const [returnModal, setReturnModal] = useState<{ open: boolean; itemId?: number; maxQty?: number }>({ open: false })
  const [returnReason, setReturnReason] = useState('')
  const [returnQty, setReturnQty] = useState(1)
  const [installment, setInstallment] = useState<any>(null)

  const submitReturn = async () => {
    if (!returnModal.itemId) return
    if (returnReason.trim().length < 5) { message.warning('Опишите причину подробнее'); return }
    try {
      await returnsApi.create(returnModal.itemId, returnQty, returnReason)
      message.success('Заявка на возврат отправлена')
      setReturnModal({ open: false }); setReturnReason(''); setReturnQty(1)
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  useEffect(() => {
    ordersApi.get(parseInt(id!))
      .then(setOrder)
      .catch(() => message.error('Заказ не найден'))
      .finally(() => setLoading(false))
    subOrdersApi.forOrder(parseInt(id!)).then(setSubOrders).catch(() => {})
    ordersApi.receipts(parseInt(id!)).then(setReceipts).catch(() => {})
    ordersApi.installmentPlan(parseInt(id!)).then(setInstallment).catch(() => {})
  }, [id])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (!order) return <Empty description="Заказ не найден" />

  const currentStep = stepOrder.indexOf(order.status)
  const isCancelled = order.status === 'cancelled' || order.status === 'refunded'

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <Title level={3}>Заказ #{order.id}</Title>
      <Text type="secondary">{dayjs(order.created_at).format('DD.MM.YYYY HH:mm')}</Text>

      <Card style={{ marginTop: 16, marginBottom: 16 }}>
        {isCancelled ? (
          <Tag color={statusColors[order.status]} style={{ fontSize: 14, padding: '4px 12px' }}>
            {statusLabels[order.status]}
          </Tag>
        ) : (
          <Steps
            current={currentStep}
            size="small"
            items={stepOrder.map((s) => ({ title: statusLabels[s] }))}
          />
        )}
      </Card>

      {subOrders.length > 0 && (
        <Card title="Отслеживание по продавцам" style={{ marginBottom: 16 }}>
          {subOrders.map((so) => (
            <div key={so.id} style={{ paddingBottom: 12, marginBottom: 12, borderBottom: '1px solid #f0f0f0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <Text strong>{so.shop_name || `Магазин #${so.shop_id}`}</Text>
                <Tag color={statusColors[so.status] || 'default'}>
                  {subOrderStatusLabels[so.status] || so.status}
                </Tag>
              </div>
              <Text type="secondary" style={{ fontSize: 13 }}>
                {so.items.map((it) => `${it.title}${it.variant_name ? ` (${it.variant_name})` : ''} ×${it.quantity}`).join(', ')}
              </Text>
              {so.tracking_number && (
                <div style={{ marginTop: 6 }}>
                  <Text style={{ fontSize: 13 }}>Трек-номер: </Text>
                  {so.tracking_url ? (
                    <a href={so.tracking_url} target="_blank" rel="noreferrer">
                      {so.tracking_number} (отследить)
                    </a>
                  ) : (
                    <Text code>{so.tracking_number}</Text>
                  )}
                  {so.delivery_service && <Text type="secondary" style={{ fontSize: 12 }}> · {so.delivery_service}</Text>}
                </div>
              )}
            </div>
          ))}
        </Card>
      )}

      <Card title="Товары" style={{ marginBottom: 16 }}>
        {order.items.map((item) => {
          const img = item.product.images.find((i) => i.is_main) || item.product.images[0]
          return (
            <div key={item.id} style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
              <Link to={`/products/${item.product_id}`}>
                {img ? (
                  <img src={img.url} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 8 }} />
                ) : (
                  <div style={{ width: 56, height: 56, background: '#f5f5f5', borderRadius: 8 }} />
                )}
              </Link>
              <div style={{ flex: 1 }}>
                <Text>{item.product.title}</Text>
                {item.variant_name && <Text type="secondary"> ({item.variant_name})</Text>}<br />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {item.quantity} × {parseFloat(item.price_at_time).toLocaleString('ru')} ₽
                </Text>
              </div>
              <div style={{ textAlign: 'right' }}>
                <Text strong>{(parseFloat(item.price_at_time) * item.quantity).toLocaleString('ru')} ₽</Text>
                {(order.status === 'delivered' || order.status === 'completed') && (
                  <div>
                    <Button
                      size="small" type="link"
                      onClick={() => { setReturnModal({ open: true, itemId: item.id, maxQty: item.quantity }); setReturnQty(1) }}
                    >
                      Оформить возврат
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </Card>

      <Modal
        title="Заявка на возврат" open={returnModal.open}
        onCancel={() => setReturnModal({ open: false })} onOk={submitReturn} okText="Отправить заявку"
      >
        <Text>Количество к возврату:</Text>
        <InputNumber
          min={1} max={returnModal.maxQty || 1} value={returnQty}
          onChange={(v) => setReturnQty(v || 1)} style={{ width: '100%', margin: '8px 0 16px' }}
        />
        <Text>Причина возврата:</Text>
        <Input.TextArea
          rows={3} value={returnReason} onChange={(e) => setReturnReason(e.target.value)}
          placeholder="Например: товар не подошёл по размеру / брак / не соответствует описанию"
          style={{ marginTop: 8 }}
        />
      </Modal>

      <Card title="Доставка" style={{ marginBottom: 16 }}>
        <Descriptions column={1} size="small">
          <Descriptions.Item label="Адрес">{order.delivery_address}</Descriptions.Item>
          {order.delivery_info?.tracking_number && !subOrders.some((s) => s.tracking_number) && (
            <Descriptions.Item label="Трек-номер">{order.delivery_info.tracking_number}</Descriptions.Item>
          )}
          {order.delivery_info && (
            <Descriptions.Item label="Срок доставки">{order.delivery_info.estimated_days} дн.</Descriptions.Item>
          )}
          {order.is_gift && (
            <Descriptions.Item label="🎁 Подарок">
              {order.gift_wrap ? 'С подарочной упаковкой' : 'Без упаковки'}
              {order.gift_message ? ` · «${order.gift_message}»` : ''}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      {installment && (
        <Card size="small" title={`Оплата частями · ${installment.provider}`} style={{ marginBottom: 16 }}>
          <Text type="secondary">
            {installment.parts} платежа по ~{Number(installment.part_amount).toLocaleString('ru')} ₽
          </Text>
          <div style={{ marginTop: 8 }}>
            {installment.schedule?.map((s: any, i: number) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #f3e3cf' }}>
                <Text>{i === 0 ? 'Сегодня' : new Date(s.due_date).toLocaleDateString('ru')}</Text>
                <Text strong>{Number(s.amount).toLocaleString('ru')} ₽</Text>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card title="Оплата">
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <Text>Сумма товаров:</Text><Text>{parseFloat(order.subtotal).toLocaleString('ru')} ₽</Text>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <Text>Доставка:</Text><Text>{parseFloat(order.delivery_cost).toLocaleString('ru')} ₽</Text>
        </div>
        {parseFloat(order.bonus_used) > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <Text>Бонусы:</Text><Text style={{ color: '#52c41a' }}>−{parseFloat(order.bonus_used).toLocaleString('ru')} ₽</Text>
          </div>
        )}
        {parseFloat(order.coupon_discount) > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <Text>Скидка по купону:</Text><Text style={{ color: '#52c41a' }}>−{parseFloat(order.coupon_discount).toLocaleString('ru')} ₽</Text>
          </div>
        )}
        <Divider />
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <Text strong style={{ fontSize: 18 }}>Итого:</Text>
          <Text strong style={{ fontSize: 18, color: '#b45309' }}>
            {parseFloat(order.total_price).toLocaleString('ru')} ₽
          </Text>
        </div>
        {order.payment?.confirmation_url && order.status === 'pending_payment' && (
          <Button type="primary" block style={{ marginTop: 16 }} href={order.payment.confirmation_url}>
            Перейти к оплате
          </Button>
        )}

        {receipts.length > 0 && (
          <>
            <Divider />
            <Text strong>Кассовые чеки (54-ФЗ)</Text>
            {receipts.map((r) => {
              const map: Record<string, { c: string; t: string }> = {
                succeeded: { c: 'green', t: 'Чек зарегистрирован' },
                pending: { c: 'gold', t: 'Чек формируется' },
                canceled: { c: 'volcano', t: 'Чек отклонён' },
                failed: { c: 'red', t: 'Ошибка фискализации' },
              }
              const m = map[r.status] || { c: 'default', t: r.status }
              return (
                <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                  <Text type="secondary">
                    {r.type === 'income_refund' ? 'Возврат прихода' : 'Приход'} · {parseFloat(r.total).toLocaleString('ru')} ₽
                  </Text>
                  <Tag color={m.c}>{m.t}</Tag>
                </div>
              )
            })}
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
              Чек придёт на {receipts[0].customer_contact} от оператора фискальных данных.
            </Text>
          </>
        )}
      </Card>
    </div>
  )
}
