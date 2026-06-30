import { useEffect, useState } from 'react'
import {
  Typography, Card, List, Tag, Button, Input, Empty, Spin, message, Row, Col, Alert, Descriptions, Space, Popconfirm,
} from 'antd'
import { customApi } from '@/api'
import { useAuthStore } from '@/store/authStore'

const { Title, Text, Paragraph } = Typography

export const statusMeta: Record<string, { label: string; color: string }> = {
  new: { label: 'Новый', color: 'default' },
  quoted: { label: 'Оферта получена', color: 'blue' },
  accepted: { label: 'Принят', color: 'cyan' },
  in_production: { label: 'В работе', color: 'gold' },
  ready: { label: 'Готов', color: 'green' },
  completed: { label: 'Завершён', color: 'success' },
  declined: { label: 'Отклонён', color: 'red' },
  cancelled: { label: 'Отменён', color: 'volcano' },
}

export default function CustomRequestsPage() {
  const me = useAuthStore((s) => s.user)
  const [list, setList] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [active, setActive] = useState<any>(null)
  const [text, setText] = useState('')

  const load = () => { setLoading(true); customApi.mine().then(setList).finally(() => setLoading(false)) }
  useEffect(() => { load() }, [])

  const open = async (id: number) => setActive(await customApi.get(id))
  const refresh = async () => { if (active) setActive(await customApi.get(active.id)); load() }

  const send = async () => {
    if (!text.trim()) return
    await customApi.message(active.id, text.trim()); setText(''); refresh()
  }
  const accept = async () => { await customApi.accept(active.id); message.success('Оферта принята'); refresh() }
  const cancel = async () => { await customApi.cancel(active.id); message.success('Запрос отменён'); refresh() }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <Title level={3}>Индивидуальные заказы</Title>
      <Paragraph type="secondary">Запросы на изготовление под заказ: переписка с мастером, оферта, статус работы.</Paragraph>
      <Row gutter={16}>
        <Col xs={24} md={9}>
          {list.length === 0 ? <Empty description="Пока нет запросов" /> : (
            <List
              dataSource={list}
              renderItem={(r) => (
                <Card size="small" hoverable style={{ marginBottom: 8, borderColor: active?.id === r.id ? '#b45309' : undefined }} onClick={() => open(r.id)}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <Text strong>{r.title}</Text>
                    <Tag color={statusMeta[r.status]?.color}>{statusMeta[r.status]?.label}</Tag>
                  </div>
                  {r.quoted_price && <Text type="secondary" style={{ fontSize: 12 }}>Оферта: {Number(r.quoted_price).toLocaleString('ru')} ₽</Text>}
                </Card>
              )}
            />
          )}
        </Col>
        <Col xs={24} md={15}>
          {!active ? <Card><Empty description="Выберите запрос" /></Card> : (
            <Card title={<span>{active.title} <Tag color={statusMeta[active.status]?.color}>{statusMeta[active.status]?.label}</Tag></span>}>
              <Descriptions column={1} size="small" style={{ marginBottom: 12 }}>
                <Descriptions.Item label="Описание">{active.description}</Descriptions.Item>
                {active.budget && <Descriptions.Item label="Бюджет">{Number(active.budget).toLocaleString('ru')} ₽</Descriptions.Item>}
                {active.deadline && <Descriptions.Item label="Срок">{new Date(active.deadline).toLocaleDateString('ru')}</Descriptions.Item>}
              </Descriptions>

              {active.status === 'quoted' && (
                <Alert
                  type="info" showIcon style={{ marginBottom: 12 }}
                  message={`Оферта: ${Number(active.quoted_price).toLocaleString('ru')} ₽${active.quoted_days ? `, срок ${active.quoted_days} дн.` : ''}${active.deposit_percent ? `, предоплата ${active.deposit_percent}%` : ''}`}
                  description={
                    <div>
                      {active.offer_note && <Paragraph style={{ marginBottom: 8 }}>{active.offer_note}</Paragraph>}
                      <Button type="primary" onClick={accept}>Принять оферту</Button>
                    </div>
                  }
                />
              )}

              <div style={{ maxHeight: 280, overflowY: 'auto', marginBottom: 12 }}>
                {active.messages?.map((m: any) => (
                  <div key={m.id} style={{ textAlign: m.sender_id === me?.id ? 'right' : 'left', marginBottom: 6 }}>
                    <span style={{ display: 'inline-block', padding: '6px 10px', borderRadius: 8, background: m.sender_id === me?.id ? '#f3e3cf' : '#f5f5f5', maxWidth: '80%' }}>
                      {m.text}
                    </span>
                  </div>
                ))}
              </div>

              {!['completed', 'declined', 'cancelled'].includes(active.status) && (
                <Space.Compact style={{ width: '100%' }}>
                  <Input value={text} onChange={(e) => setText(e.target.value)} onPressEnter={send} placeholder="Сообщение мастеру..." />
                  <Button type="primary" onClick={send}>Отправить</Button>
                </Space.Compact>
              )}
              {!['completed', 'declined', 'cancelled'].includes(active.status) && (
                <Popconfirm title="Отменить запрос?" onConfirm={cancel}>
                  <Button danger size="small" type="text" style={{ marginTop: 8 }}>Отменить запрос</Button>
                </Popconfirm>
              )}
            </Card>
          )}
        </Col>
      </Row>
    </div>
  )
}
