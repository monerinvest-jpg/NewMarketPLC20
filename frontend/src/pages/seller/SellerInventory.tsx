import { useEffect, useState } from 'react'
import { Card, Table, Typography, Button, InputNumber, Input, message, Tag, Modal, Space, Alert, Empty, Spin } from 'antd'
import { inventoryApi, productsApi } from '@/api'
import type { LowStockItem, StockMovement, Product } from '@/types'
import dayjs from 'dayjs'

const { Title, Text } = Typography

const reasonLabels: Record<string, { label: string; color: string }> = {
  restock: { label: 'Пополнение', color: 'green' },
  order: { label: 'Заказ', color: 'blue' },
  cancel: { label: 'Возврат (отмена)', color: 'cyan' },
  manual: { label: 'Вручную', color: 'orange' },
  import: { label: 'Импорт', color: 'purple' },
}

export default function SellerInventory() {
  const [lowStock, setLowStock] = useState<LowStockItem[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [adjustModal, setAdjustModal] = useState<{ open: boolean; product?: Product }>({ open: false })
  const [change, setChange] = useState(0)
  const [note, setNote] = useState('')
  const [movements, setMovements] = useState<StockMovement[]>([])
  const [movementsModal, setMovementsModal] = useState<{ open: boolean; title?: string }>({ open: false })

  const load = async () => {
    setLoading(true)
    try {
      const [low, prods] = await Promise.all([
        inventoryApi.lowStock(),
        productsApi.myProducts({ page_size: 100 }),
      ])
      setLowStock(low)
      setProducts((prods as any).items || [])
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [])

  const submitAdjust = async () => {
    if (!adjustModal.product || change === 0) { message.warning('Укажите изменение количества'); return }
    try {
      await inventoryApi.adjustStock(adjustModal.product.id, change, note || undefined)
      message.success('Остаток обновлён')
      setAdjustModal({ open: false }); setChange(0); setNote('')
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const showMovements = async (product: Product) => {
    const m = await inventoryApi.movements(product.id)
    setMovements(m)
    setMovementsModal({ open: true, title: product.title })
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div>
      <Title level={3}>Склад</Title>

      {lowStock.length > 0 && (
        <Alert
          type="warning" showIcon style={{ marginBottom: 16 }}
          message={`Заканчивается товар: ${lowStock.length} поз.`}
          description={lowStock.map((l) => `${l.title} (${l.quantity})`).join(', ')}
        />
      )}

      <Card>
        <Table
          dataSource={products}
          rowKey="id"
          pagination={{ pageSize: 20 }}
          columns={[
            { title: 'Товар', dataIndex: 'title', ellipsis: true },
            {
              title: 'Остаток', dataIndex: 'quantity', width: 110,
              render: (q) => <Tag color={q <= 5 ? 'red' : q <= 20 ? 'orange' : 'green'}>{q} шт.</Tag>,
              sorter: (a, b) => a.quantity - b.quantity,
            },
            {
              title: 'Действия', width: 260,
              render: (_, p) => (
                <Space>
                  <Button size="small" type="primary" onClick={() => setAdjustModal({ open: true, product: p })}>Изменить остаток</Button>
                  <Button size="small" onClick={() => showMovements(p)}>История</Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title={`Изменить остаток: ${adjustModal.product?.title || ''}`}
        open={adjustModal.open}
        onCancel={() => setAdjustModal({ open: false })}
        onOk={submitAdjust}
      >
        <Text type="secondary">Положительное число — пополнение, отрицательное — списание.</Text>
        <div style={{ marginTop: 12 }}>
          <InputNumber value={change} onChange={(v) => setChange(v ?? 0)} style={{ width: '100%' }} placeholder="+10 или -3" />
          <Input style={{ marginTop: 8 }} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Комментарий (необязательно)" />
        </div>
      </Modal>

      <Modal
        title={`История движений: ${movementsModal.title || ''}`}
        open={movementsModal.open}
        onCancel={() => setMovementsModal({ open: false })}
        footer={null}
        width={640}
      >
        {movements.length === 0 ? <Empty description="Нет движений" /> : (
          <Table
            dataSource={movements} rowKey="id" size="small" pagination={{ pageSize: 10 }}
            columns={[
              { title: 'Дата', dataIndex: 'created_at', render: (v) => dayjs(v).format('DD.MM.YY HH:mm') },
              { title: 'Изменение', dataIndex: 'change', render: (v) => <Text type={v > 0 ? 'success' : 'danger'}>{v > 0 ? `+${v}` : v}</Text> },
              { title: 'Остаток', dataIndex: 'quantity_after' },
              { title: 'Причина', dataIndex: 'reason', render: (v) => <Tag color={reasonLabels[v]?.color}>{reasonLabels[v]?.label || v}</Tag> },
              { title: 'Заметка', dataIndex: 'note', render: (v) => v || '—' },
            ]}
          />
        )}
      </Modal>
    </div>
  )
}
