import { useEffect, useState } from 'react'
import { Card, Table, Typography, Button, Tag, Space, Modal, Input, message, Empty, Spin, Tooltip } from 'antd'
import { WarningOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { adminApi } from '@/api'
import dayjs from 'dayjs'

const { Title, Text } = Typography

interface QueueItem {
  product_id: number
  title: string
  shop_id: number
  shop_name?: string
  price: number
  created_at: string
  priority: number
  flags: string[]
}

export default function AdminModerationQueue() {
  const [items, setItems] = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<number[]>([])
  const [rejectModal, setRejectModal] = useState<{ open: boolean; ids: number[] }>({ open: false, ids: [] })
  const [reason, setReason] = useState('')

  const load = () => {
    setLoading(true)
    adminApi.moderationQueue().then(setItems).catch(() => {}).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const approve = async (ids: number[]) => {
    try {
      await adminApi.bulkModerate(ids, 'active')
      message.success(`Одобрено: ${ids.length}`)
      setSelected([]); load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const reject = async () => {
    if (!reason.trim()) { message.warning('Укажите причину'); return }
    try {
      await adminApi.bulkModerate(rejectModal.ids, 'rejected', reason)
      message.success(`Отклонено: ${rejectModal.ids.length}`)
      setRejectModal({ open: false, ids: [] }); setReason(''); setSelected([]); load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const priorityTag = (p: number) => {
    if (p >= 100) return <Tag color="red">Высокий</Tag>
    if (p >= 30) return <Tag color="orange">Средний</Tag>
    if (p > 0) return <Tag color="gold">Низкий</Tag>
    return <Tag color="default">—</Tag>
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div>
      <Title level={3}>Очередь модерации товаров</Title>
      <Text type="secondary">
        Товары на проверке, отсортированы по приоритету. Авто-флаги подсказывают, на что обратить внимание.
      </Text>

      {selected.length > 0 && (
        <div style={{ margin: '16px 0', padding: '8px 12px', background: '#fff7e6', borderRadius: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
          <Text>Выбрано: {selected.length}</Text>
          <Button size="small" type="primary" onClick={() => approve(selected)}>Одобрить выбранные</Button>
          <Button size="small" danger onClick={() => setRejectModal({ open: true, ids: selected })}>Отклонить выбранные</Button>
          <Button size="small" type="text" onClick={() => setSelected([])}>Сбросить</Button>
        </div>
      )}

      <Card style={{ marginTop: 16 }}>
        {items.length === 0 ? (
          <Empty description="Очередь пуста — нет товаров на модерации" />
        ) : (
          <Table
            dataSource={items}
            rowKey="product_id"
            rowSelection={{ selectedRowKeys: selected, onChange: (k) => setSelected(k as number[]) }}
            pagination={{ pageSize: 20 }}
            columns={[
              { title: 'Приоритет', dataIndex: 'priority', width: 110, render: priorityTag, sorter: (a, b) => b.priority - a.priority },
              {
                title: 'Товар', render: (_, r) => (
                  <Link to={`/products/${r.product_id}`} target="_blank">{r.title}</Link>
                ),
              },
              { title: 'Магазин', dataIndex: 'shop_name', render: (v) => v || '—' },
              { title: 'Цена', dataIndex: 'price', width: 110, render: (v) => `${v.toLocaleString('ru')} ₽` },
              {
                title: 'Авто-флаги', dataIndex: 'flags',
                render: (flags: string[]) => flags.length === 0 ? <Text type="secondary">—</Text> : (
                  <Space wrap>
                    {flags.map((f, i) => (
                      <Tooltip key={i} title={f}>
                        <Tag icon={<WarningOutlined />} color="volcano">{f.split(':')[0]}</Tag>
                      </Tooltip>
                    ))}
                  </Space>
                ),
              },
              { title: 'Добавлен', dataIndex: 'created_at', width: 130, render: (v) => dayjs(v).format('DD.MM.YY HH:mm') },
              {
                title: 'Действия', width: 180,
                render: (_, r) => (
                  <Space>
                    <Button size="small" type="primary" onClick={() => approve([r.product_id])}>Одобрить</Button>
                    <Button size="small" danger onClick={() => setRejectModal({ open: true, ids: [r.product_id] })}>Отклонить</Button>
                  </Space>
                ),
              },
            ]}
          />
        )}
      </Card>

      <Modal
        title="Причина отклонения"
        open={rejectModal.open}
        onCancel={() => setRejectModal({ open: false, ids: [] })}
        onOk={reject}
        okText="Отклонить"
      >
        <Input.TextArea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Опишите причину — она будет отправлена продавцу" />
      </Modal>
    </div>
  )
}
