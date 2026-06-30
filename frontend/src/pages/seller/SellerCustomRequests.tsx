import { useEffect, useState } from 'react'
import {
  Typography, Card, List, Tag, Button, Input, Empty, Spin, message, Row, Col, Descriptions,
  Space, Form, InputNumber, Popconfirm, Divider,
} from 'antd'
import { sellerCustomApi } from '@/api'
import { useAuthStore } from '@/store/authStore'
import { statusMeta } from '@/pages/buyer/CustomRequestsPage'

const { Title, Text, Paragraph } = Typography

export default function SellerCustomRequests() {
  const me = useAuthStore((s) => s.user)
  const [list, setList] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [active, setActive] = useState<any>(null)
  const [text, setText] = useState('')
  const [offerForm] = Form.useForm()

  const load = () => { setLoading(true); sellerCustomApi.list().then(setList).finally(() => setLoading(false)) }
  useEffect(() => { load() }, [])

  const open = async (id: number) => {
    const r = await sellerCustomApi.get(id); setActive(r)
    offerForm.setFieldsValue({ price: r.quoted_price ? Number(r.quoted_price) : undefined, days: r.quoted_days, deposit_percent: r.deposit_percent ? Number(r.deposit_percent) : undefined, note: r.offer_note })
  }
  const refresh = async () => { if (active) await open(active.id); load() }

  const send = async () => { if (!text.trim()) return; await sellerCustomApi.message(active.id, text.trim()); setText(''); refresh() }
  const sendOffer = async () => {
    const v = await offerForm.validateFields()
    await sellerCustomApi.offer(active.id, v); message.success('Оферта отправлена'); refresh()
  }
  const setStatus = async (s: string) => { await sellerCustomApi.status(active.id, s); refresh() }
  const decline = async () => { await sellerCustomApi.decline(active.id); message.success('Отклонено'); refresh() }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <Title level={3}>Запросы на изготовление</Title>
      <Paragraph type="secondary">Индивидуальные заказы покупателей: обсудите детали, выставьте оферту и ведите статус работы.</Paragraph>
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
                {active.budget && <Descriptions.Item label="Бюджет покупателя">{Number(active.budget).toLocaleString('ru')} ₽</Descriptions.Item>}
                {active.deadline && <Descriptions.Item label="Желаемый срок">{new Date(active.deadline).toLocaleDateString('ru')}</Descriptions.Item>}
              </Descriptions>

              {['new', 'quoted'].includes(active.status) && (
                <>
                  <Divider orientation="left" plain>Оферта</Divider>
                  <Form form={offerForm} layout="inline" style={{ marginBottom: 12, rowGap: 8, flexWrap: 'wrap' }}>
                    <Form.Item name="price" label="Цена ₽" rules={[{ required: true }]}><InputNumber min={1} /></Form.Item>
                    <Form.Item name="days" label="Срок, дн."><InputNumber min={1} /></Form.Item>
                    <Form.Item name="deposit_percent" label="Предоплата %"><InputNumber min={0} max={100} /></Form.Item>
                    <Form.Item name="note" label="Комментарий" style={{ flex: 1, minWidth: 200 }}><Input /></Form.Item>
                    <Button type="primary" onClick={sendOffer}>Отправить оферту</Button>
                  </Form>
                </>
              )}

              {['accepted', 'in_production', 'ready'].includes(active.status) && (
                <Space style={{ marginBottom: 12 }} wrap>
                  {active.status === 'accepted' && <Button onClick={() => setStatus('in_production')}>В работу</Button>}
                  {active.status === 'in_production' && <Button onClick={() => setStatus('ready')}>Готов</Button>}
                  {active.status === 'ready' && <Button type="primary" onClick={() => setStatus('completed')}>Завершить</Button>}
                </Space>
              )}

              <div style={{ maxHeight: 260, overflowY: 'auto', marginBottom: 12 }}>
                {active.messages?.map((m: any) => (
                  <div key={m.id} style={{ textAlign: m.sender_id === me?.id ? 'right' : 'left', marginBottom: 6 }}>
                    <span style={{ display: 'inline-block', padding: '6px 10px', borderRadius: 8, background: m.sender_id === me?.id ? '#f3e3cf' : '#f5f5f5', maxWidth: '80%' }}>{m.text}</span>
                  </div>
                ))}
              </div>

              {!['completed', 'declined', 'cancelled'].includes(active.status) && (
                <>
                  <Space.Compact style={{ width: '100%' }}>
                    <Input value={text} onChange={(e) => setText(e.target.value)} onPressEnter={send} placeholder="Сообщение покупателю..." />
                    <Button type="primary" onClick={send}>Отправить</Button>
                  </Space.Compact>
                  <Popconfirm title="Отклонить запрос?" onConfirm={decline}>
                    <Button danger size="small" type="text" style={{ marginTop: 8 }}>Отклонить запрос</Button>
                  </Popconfirm>
                </>
              )}
            </Card>
          )}
        </Col>
      </Row>
    </div>
  )
}
