import { useEffect, useState } from 'react'
import {
  Row, Col, Card, List, Typography, Button, Tag, Modal, Form, Input, Select, message, Empty, Space,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { disputesApi, ordersApi } from '@/api'
import DisputeThread from '@/components/common/DisputeThread'
import { disputeStatusMeta } from '@/lib/disputeMeta'
import type { Dispute } from '@/types'
import dayjs from 'dayjs'

const { Title, Text } = Typography

export default function DisputesPage() {
  const [disputes, setDisputes] = useState<Dispute[]>([])
  const [active, setActive] = useState<Dispute | null>(null)
  const [orders, setOrders] = useState<any[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [form] = Form.useForm()

  const load = () => disputesApi.mine().then(setDisputes).catch(() => {})
  const openOne = (id: number) => disputesApi.get(id).then(setActive).catch(() => {})

  useEffect(() => {
    load()
    ordersApi.list().then((r: any) => setOrders(r.items || r)).catch(() => {})
  }, [])

  const submit = async () => {
    const v = await form.validateFields()
    const d = await disputesApi.open(v)
    setCreateOpen(false); form.resetFields(); await load(); openOne(d.id)
    message.success('Спор открыт')
  }

  const send = async (text: string) => { if (active) { await disputesApi.message(active.id, text); openOne(active.id) } }
  const escalate = async () => { if (active) { await disputesApi.escalate(active.id); await load(); openOne(active.id); message.success('Передано в арбитраж') } }
  const cancel = async () => { if (active) { await disputesApi.cancel(active.id); await load(); openOne(active.id) } }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Споры</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>Открыть спор</Button>
      </div>

      <Row gutter={16}>
        <Col xs={24} md={9}>
          <Card styles={{ body: { padding: 0 } }}>
            {disputes.length === 0 ? <Empty description="Споров нет" style={{ padding: 24 }} /> : (
              <List
                dataSource={disputes}
                renderItem={(d) => (
                  <List.Item onClick={() => openOne(d.id)} style={{ cursor: 'pointer', padding: '12px 16px', background: active?.id === d.id ? '#fff7ed' : undefined }}>
                    <List.Item.Meta title={<Text strong>{d.subject}</Text>} description={`Заказ #${d.order_id} · ${dayjs(d.last_message_at).format('DD.MM.YY')}`} />
                    <Tag color={disputeStatusMeta[d.status].color}>{disputeStatusMeta[d.status].label}</Tag>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} md={15}>
          {!active ? <Card><Empty description="Выберите спор" /></Card> : (
            <Card
              title={<Space><span>{active.subject}</span><Tag color={disputeStatusMeta[active.status].color}>{disputeStatusMeta[active.status].label}</Tag></Space>}
              extra={active.status === 'open' && (
                <Space>
                  <Button size="small" onClick={escalate}>В арбитраж</Button>
                  <Button size="small" danger onClick={cancel}>Отозвать</Button>
                </Space>
              )}
            >
              {active.refund_amount && Number(active.refund_amount) > 0 && (
                <Text type="success" style={{ display: 'block', marginBottom: 8 }}>
                  Возврат: {Number(active.refund_amount).toLocaleString('ru')} ₽
                </Text>
              )}
              <DisputeThread dispute={active} myRole="buyer" onSend={send} />
            </Card>
          )}
        </Col>
      </Row>

      <Modal title="Открыть спор" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={submit} okText="Открыть">
        <Form form={form} layout="vertical">
          <Form.Item name="order_id" label="Заказ" rules={[{ required: true, message: 'Выберите заказ' }]}>
            <Select placeholder="Выберите заказ"
              options={orders.map((o) => ({ value: o.id, label: `Заказ #${o.id} — ${Number(o.total_price).toLocaleString('ru')} ₽` }))} />
          </Form.Item>
          <Form.Item name="subject" label="Тема" rules={[{ required: true, min: 3 }]}><Input placeholder="Кратко суть проблемы" /></Form.Item>
          <Form.Item name="reason" label="Описание" rules={[{ required: true, min: 5 }]}><Input.TextArea rows={4} placeholder="Опишите проблему подробно" /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
