import { useEffect, useState } from 'react'
import {
  Row, Col, Card, Table, Typography, Button, Tag, Statistic, Modal, Form, Select, InputNumber, Input, message, Empty, Space,
} from 'antd'
import { disputesApi } from '@/api'
import DisputeThread from '@/components/common/DisputeThread'
import { disputeStatusMeta } from '@/lib/disputeMeta'
import type { Dispute } from '@/types'
import dayjs from 'dayjs'

const { Title, Text } = Typography

export default function DisputeDesk() {
  const [disputes, setDisputes] = useState<Dispute[]>([])
  const [active, setActive] = useState<Dispute | null>(null)
  const [stats, setStats] = useState<{ open: number; in_mediation: number; resolved: number } | null>(null)
  const [statusFilter, setStatusFilter] = useState<string | undefined>('in_mediation')
  const [resolveOpen, setResolveOpen] = useState(false)
  const [form] = Form.useForm()
  const resolution = Form.useWatch('resolution', form)

  const load = () => disputesApi.staffQueue(statusFilter).then(setDisputes).catch(() => {})
  const loadStats = () => disputesApi.staffStats().then(setStats).catch(() => {})
  const openOne = (id: number) => disputesApi.get(id).then(setActive).catch(() => {})

  useEffect(() => { load() }, [statusFilter])
  useEffect(() => { loadStats() }, [])

  const send = async (text: string) => { if (active) { await disputesApi.message(active.id, text); openOne(active.id) } }
  const assignMe = async () => { if (active) { await disputesApi.assignMe(active.id); openOne(active.id); load() } }

  const submitResolve = async () => {
    const v = await form.validateFields()
    await disputesApi.resolve(active!.id, { resolution: v.resolution, refund_amount: v.refund_amount, note: v.note })
    setResolveOpen(false); form.resetFields(); openOne(active!.id); load(); loadStats()
    message.success('Спор решён')
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>Арбитраж споров</Title>
      {stats && (
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col xs={8} md={4}><Card size="small"><Statistic title="Обсуждение" value={stats.open} /></Card></Col>
          <Col xs={8} md={4}><Card size="small"><Statistic title="В арбитраже" value={stats.in_mediation} valueStyle={{ color: '#d48806' }} /></Card></Col>
          <Col xs={8} md={4}><Card size="small"><Statistic title="Решено" value={stats.resolved} valueStyle={{ color: '#3f8600' }} /></Card></Col>
        </Row>
      )}

      <Space style={{ marginBottom: 16 }}>
        <Select style={{ width: 200 }} value={statusFilter} onChange={setStatusFilter} allowClear placeholder="Все статусы"
          options={Object.entries(disputeStatusMeta).map(([v, m]) => ({ value: v, label: m.label }))} />
      </Space>

      <Row gutter={16}>
        <Col xs={24} lg={13}>
          <Card styles={{ body: { padding: 0 } }}>
            <Table<Dispute>
              dataSource={disputes} rowKey="id" size="small" pagination={{ pageSize: 10 }}
              onRow={(r) => ({ onClick: () => openOne(r.id), style: { cursor: 'pointer' } })}
              columns={[
                { title: '№', dataIndex: 'id', width: 60 },
                { title: 'Тема', dataIndex: 'subject', ellipsis: true },
                { title: 'Заказ', dataIndex: 'order_id', width: 90, render: (v) => `#${v}` },
                { title: 'Статус', dataIndex: 'status', width: 120, render: (v) => <Tag color={disputeStatusMeta[v].color}>{disputeStatusMeta[v].label}</Tag> },
                { title: 'Обновлён', dataIndex: 'last_message_at', width: 120, render: (v) => dayjs(v).format('DD.MM HH:mm') },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={11}>
          {!active ? <Card><Empty description="Выберите спор" /></Card> : (
            <Card
              title={<Space wrap><span>#{active.id} {active.subject}</span><Tag color={disputeStatusMeta[active.status].color}>{disputeStatusMeta[active.status].label}</Tag></Space>}
              extra={active.status !== 'resolved' && active.status !== 'cancelled' && (
                <Space>
                  {active.mediator_id == null && <Button size="small" onClick={assignMe}>Взять</Button>}
                  <Button size="small" type="primary" onClick={() => setResolveOpen(true)}>Решить</Button>
                </Space>
              )}
            >
              <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>Причина: {active.reason}</Text>
              <DisputeThread dispute={active} myRole="mediator" onSend={send} />
            </Card>
          )}
        </Col>
      </Row>

      <Modal title="Решение по спору" open={resolveOpen} onCancel={() => setResolveOpen(false)} onOk={submitResolve} okText="Применить">
        <Form form={form} layout="vertical" initialValues={{ resolution: 'buyer_favor' }}>
          <Form.Item name="resolution" label="Исход" rules={[{ required: true }]}>
            <Select options={[
              { value: 'buyer_favor', label: 'В пользу покупателя (полный возврат)' },
              { value: 'partial', label: 'Частичный возврат' },
              { value: 'seller_favor', label: 'В пользу продавца (без возврата)' },
            ]} />
          </Form.Item>
          {(resolution === 'buyer_favor' || resolution === 'partial') && (
            <Form.Item name="refund_amount" label="Сумма возврата, ₽" rules={[{ required: true, message: 'Укажите сумму' }]}>
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
          )}
          <Form.Item name="note" label="Комментарий"><Input.TextArea rows={2} placeholder="Обоснование решения" /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
