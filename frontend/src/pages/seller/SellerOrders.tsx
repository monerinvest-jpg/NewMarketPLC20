import { useEffect, useState } from 'react'
import { Table, Tag, Button, Modal, Input, message, Typography, Space, Radio, Select } from 'antd'
import { PrinterOutlined } from '@ant-design/icons'
import { subOrdersApi } from '@/api'
import type { SellerSubOrder } from '@/api'
import dayjs from 'dayjs'

const { Title, Text } = Typography

// Per-seller sub-order fulfillment statuses (the seller controls only their slice).
const statusLabels: Record<string, { label: string; color: string }> = {
  processing: { label: 'В обработке', color: 'geekblue' },
  shipped: { label: 'Отправлен', color: 'cyan' },
  delivered: { label: 'Доставлен', color: 'green' },
  completed: { label: 'Завершён', color: 'success' },
  cancelled: { label: 'Отменён', color: 'red' },
}

// Allowed forward transitions a seller can apply to their sub-order.
const nextStatuses: Record<string, string[]> = {
  processing: ['shipped', 'cancelled'],
  shipped: ['delivered'],
  delivered: ['completed'],
  completed: [],
  cancelled: [],
}

export default function SellerOrders() {
  const [subOrders, setSubOrders] = useState<SellerSubOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [shipModal, setShipModal] = useState<{ open: boolean; sub?: SellerSubOrder; target?: string }>({ open: false })
  const [trackingNumber, setTrackingNumber] = useState('')
  const [shipMode, setShipMode] = useState<'api' | 'manual'>('api')
  const [carrier, setCarrier] = useState('cdek')
  const [cityTo, setCityTo] = useState('')
  const [recipientName, setRecipientName] = useState('')
  const [recipientPhone, setRecipientPhone] = useState('')
  const [shipping, setShipping] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      setSubOrders(await subOrdersApi.mySeller())
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [])

  const applyStatus = async (sub: SellerSubOrder, status: string, tracking?: string) => {
    try {
      await subOrdersApi.updateStatus(sub.id, status, tracking)
      message.success('Статус обновлён')
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const handleTransition = (sub: SellerSubOrder, target: string) => {
    // Shipping asks for a tracking number; other transitions apply immediately.
    if (target === 'shipped') {
      setShipModal({ open: true, sub, target })
      setTrackingNumber(sub.tracking_number || '')
    } else {
      applyStatus(sub, target)
    }
  }

  const confirmShip = async () => {
    if (!shipModal.sub) return
    if (shipMode === 'api') {
      // Register a shipment with the carrier — tracking number comes back automatically
      setShipping(true)
      try {
        const res = await subOrdersApi.createShipment(shipModal.sub.id, {
          delivery_service: carrier,
          to_city: cityTo || undefined,
          recipient_name: recipientName || undefined,
          recipient_phone: recipientPhone || undefined,
        })
        message.success(`Отгрузка оформлена. Трек: ${res.tracking_number || '—'}`)
        setShipModal({ open: false })
        load()
      } catch (e: any) {
        message.error(e.response?.data?.detail || 'Не удалось оформить отгрузку')
      } finally {
        setShipping(false)
      }
    } else {
      await applyStatus(shipModal.sub, 'shipped', trackingNumber)
      setShipModal({ open: false })
    }
  }

  const downloadLabel = (sub: SellerSubOrder) => {
    const token = localStorage.getItem('access_token')
    fetch(subOrdersApi.labelUrl(sub.id), { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => { if (!r.ok) throw new Error(); return r.blob() })
      .then((blob) => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = `label-${sub.id}.pdf`; a.click()
        URL.revokeObjectURL(url)
      })
      .catch(() => message.error('Сначала оформите отгрузку'))
  }

  return (
    <div>
      <Title level={3}>Заказы (мои отправления)</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        Показаны только ваши позиции. Для заказов из нескольких магазинов вы управляете доставкой своей части независимо.
      </Text>

      <Table
        loading={loading}
        dataSource={subOrders}
        rowKey="id"
        expandable={{
          expandedRowRender: (sub) => (
            <div style={{ paddingLeft: 8 }}>
              {sub.items.map((it, idx) => (
                <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                  <Text>
                    {it.title}
                    {it.variant_name ? <Text type="secondary"> ({it.variant_name})</Text> : null}
                    {' '}× {it.quantity}
                  </Text>
                  <Text>{(it.price_at_time * it.quantity).toLocaleString('ru')} ₽</Text>
                </div>
              ))}
            </div>
          ),
        }}
        columns={[
          { title: 'Заказ №', dataIndex: 'order_id', width: 90, render: (v) => `#${v}` },
          { title: 'Дата', dataIndex: 'created_at', render: (v) => v ? dayjs(v).format('DD.MM.YYYY HH:mm') : '—' },
          { title: 'Позиций', render: (_, s) => s.items.reduce((n, i) => n + i.quantity, 0) },
          { title: 'Ваш доход', dataIndex: 'net_total', render: (v) => `${v.toLocaleString('ru')} ₽` },
          { title: 'Трек-номер', dataIndex: 'tracking_number', render: (v) => v || '—' },
          {
            title: 'Статус', dataIndex: 'status',
            render: (s) => <Tag color={statusLabels[s]?.color}>{statusLabels[s]?.label || s}</Tag>,
          },
          {
            title: 'Действия',
            render: (_, sub) => {
              const options = nextStatuses[sub.status] || []
              return (
                <Space wrap>
                  {options.map((target) => (
                    <Button
                      key={target} size="small"
                      type={target === 'shipped' ? 'primary' : 'default'}
                      danger={target === 'cancelled'}
                      onClick={() => handleTransition(sub, target)}
                    >
                      {statusLabels[target]?.label || target}
                    </Button>
                  ))}
                  {sub.tracking_number && (
                    <Button size="small" icon={<PrinterOutlined />} onClick={() => downloadLabel(sub)}>
                      Этикетка
                    </Button>
                  )}
                  {options.length === 0 && !sub.tracking_number && <Text type="secondary">—</Text>}
                </Space>
              )
            },
          },
        ]}
      />

      <Modal
        title="Оформление отправки"
        open={shipModal.open}
        onCancel={() => setShipModal({ open: false })}
        onOk={confirmShip}
        confirmLoading={shipping}
        okText={shipMode === 'api' ? 'Оформить отгрузку' : 'Сохранить трек'}
        width={520}
      >
        <Radio.Group value={shipMode} onChange={(e) => setShipMode(e.target.value)} style={{ marginBottom: 16 }}>
          <Radio.Button value="api">Через API перевозчика</Radio.Button>
          <Radio.Button value="manual">Ввести трек вручную</Radio.Button>
        </Radio.Group>

        {shipMode === 'api' ? (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text type="secondary">Система создаст отправление и получит трек-номер автоматически. Без ключей API — демо-режим с тестовым треком.</Text>
            <Select
              value={carrier} onChange={setCarrier} style={{ width: '100%' }}
              options={[
                { value: 'cdek', label: 'СДЭК (полная интеграция)' },
                { value: 'russianpost', label: 'Почта России' },
                { value: 'boxberry', label: 'Boxberry' },
                { value: 'yandex', label: 'Яндекс Доставка' },
              ]}
            />
            <Input placeholder="Город получателя" value={cityTo} onChange={(e) => setCityTo(e.target.value)} />
            <Input placeholder="ФИО получателя" value={recipientName} onChange={(e) => setRecipientName(e.target.value)} />
            <Input placeholder="Телефон получателя" value={recipientPhone} onChange={(e) => setRecipientPhone(e.target.value)} />
          </Space>
        ) : (
          <Input
            placeholder="Трек-номер (СДЭК, Почта России и т.д.)"
            value={trackingNumber}
            onChange={(e) => setTrackingNumber(e.target.value)}
          />
        )}
      </Modal>
    </div>
  )
}
