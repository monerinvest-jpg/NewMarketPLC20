import { useEffect, useState } from 'react'
import {
  Row, Col, Card, List, Typography, Button, Input, Tag, Modal, Form, Select, message, Empty, Space,
} from 'antd'
import { PlusOutlined, SendOutlined } from '@ant-design/icons'
import { supportApi } from '@/api'
import type { SupportTicket, SupportTicketStatus } from '@/types'
import dayjs from 'dayjs'

const { Title, Text } = Typography
const { TextArea } = Input

const statusMeta: Record<SupportTicketStatus, { color: string; label: string }> = {
  open: { color: 'blue', label: 'Открыто' },
  in_progress: { color: 'gold', label: 'В работе' },
  pending_user: { color: 'orange', label: 'Ждём вас' },
  resolved: { color: 'green', label: 'Решено' },
  closed: { color: 'default', label: 'Закрыто' },
}

export default function SupportPage() {
  const [tickets, setTickets] = useState<SupportTicket[]>([])
  const [active, setActive] = useState<SupportTicket | null>(null)
  const [reply, setReply] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [form] = Form.useForm()

  const loadList = () => supportApi.myTickets().then(setTickets).catch(() => {})
  const openTicket = (id: number) => supportApi.getTicket(id).then(setActive).catch(() => {})

  useEffect(() => { loadList() }, [])

  const submitNew = async () => {
    const v = await form.validateFields()
    const t = await supportApi.createTicket(v)
    setCreateOpen(false)
    form.resetFields()
    await loadList()
    openTicket(t.id)
    message.success('Обращение создано')
  }

  const sendReply = async () => {
    if (!active || !reply.trim()) return
    await supportApi.addMessage(active.id, reply.trim())
    setReply('')
    openTicket(active.id)
  }

  const closeTicket = async () => {
    if (!active) return
    await supportApi.closeTicket(active.id)
    await loadList()
    openTicket(active.id)
  }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Поддержка</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>Новое обращение</Button>
      </div>

      <Row gutter={16}>
        <Col xs={24} md={9}>
          <Card styles={{ body: { padding: 0 } }}>
            {tickets.length === 0 ? (
              <Empty description="У вас пока нет обращений" style={{ padding: 24 }} />
            ) : (
              <List
                dataSource={tickets}
                renderItem={(t) => (
                  <List.Item
                    onClick={() => openTicket(t.id)}
                    style={{ cursor: 'pointer', padding: '12px 16px', background: active?.id === t.id ? '#fff7ed' : undefined }}
                  >
                    <List.Item.Meta
                      title={<Text strong>{t.subject}</Text>}
                      description={dayjs(t.last_message_at).format('DD.MM.YY HH:mm')}
                    />
                    <Tag color={statusMeta[t.status]?.color}>{statusMeta[t.status]?.label}</Tag>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} md={15}>
          {!active ? (
            <Card><Empty description="Выберите обращение или создайте новое" /></Card>
          ) : (
            <Card
              title={<Space><span>{active.subject}</span><Tag color={statusMeta[active.status]?.color}>{statusMeta[active.status]?.label}</Tag></Space>}
              extra={active.status !== 'closed' && <Button size="small" onClick={closeTicket}>Закрыть</Button>}
            >
              <div style={{ maxHeight: 420, overflowY: 'auto', marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {active.messages?.map((m) => (
                  <div key={m.id} style={{ alignSelf: m.is_staff ? 'flex-start' : 'flex-end', maxWidth: '78%' }}>
                    <div style={{
                      padding: '8px 12px', borderRadius: 12,
                      background: m.is_staff ? '#f1f5f9' : '#b45309',
                      color: m.is_staff ? '#0f172a' : '#fff',
                    }}>
                      {m.text}
                    </div>
                    <Text type="secondary" style={{ fontSize: 11, display: 'block', textAlign: m.is_staff ? 'left' : 'right' }}>
                      {m.is_staff ? 'Поддержка' : 'Вы'} · {dayjs(m.created_at).format('DD.MM HH:mm')}
                    </Text>
                  </div>
                ))}
              </div>
              {active.status !== 'closed' && (
                <div style={{ display: 'flex', gap: 8 }}>
                  <TextArea
                    rows={2} value={reply} onChange={(e) => setReply(e.target.value)}
                    placeholder="Ваше сообщение…" onPressEnter={(e) => { e.preventDefault(); sendReply() }}
                  />
                  <Button type="primary" icon={<SendOutlined />} onClick={sendReply} />
                </div>
              )}
            </Card>
          )}
        </Col>
      </Row>

      <Modal title="Новое обращение" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={submitNew} okText="Отправить">
        <Form form={form} layout="vertical">
          <Form.Item name="subject" label="Тема" rules={[{ required: true, min: 3, message: 'Укажите тему' }]}>
            <Input placeholder="Кратко опишите проблему" />
          </Form.Item>
          <Form.Item name="category" label="Категория">
            <Select
              allowClear placeholder="Выберите категорию"
              options={[
                { value: 'order', label: 'Заказ' },
                { value: 'payment', label: 'Оплата' },
                { value: 'account', label: 'Аккаунт' },
                { value: 'product', label: 'Товар' },
                { value: 'other', label: 'Другое' },
              ]}
            />
          </Form.Item>
          <Form.Item name="message" label="Сообщение" rules={[{ required: true, message: 'Опишите вопрос' }]}>
            <TextArea rows={4} placeholder="Подробно опишите вашу ситуацию" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
