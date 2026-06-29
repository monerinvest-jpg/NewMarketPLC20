import { useEffect, useState } from 'react'
import {
  Typography, Table, Tag, Button, Modal, Form, Input, Select, Switch, InputNumber,
  message, Space, Popconfirm, Alert, Row, Col,
} from 'antd'
import { SendOutlined, PlusOutlined } from '@ant-design/icons'
import { adminApi } from '@/api'

const { Title, Paragraph } = Typography

const statusMeta: Record<string, { label: string; color: string }> = {
  draft: { label: 'Черновик', color: 'default' },
  sending: { label: 'Отправляется', color: 'processing' },
  sent: { label: 'Отправлена', color: 'green' },
  failed: { label: 'Ошибка', color: 'red' },
}

export default function AdminCampaigns() {
  const [rows, setRows] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()
  const [count, setCount] = useState<number | null>(null)

  const load = () => {
    setLoading(true)
    adminApi.listCampaigns().then(setRows).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const buildSegment = (v: any) => ({
    role: v.role || undefined,
    active_within_days: v.active_within_days || undefined,
    only_verified_email: !!v.only_verified_email,
    has_referral_balance: !!v.has_referral_balance,
  })

  const preview = async () => {
    const v = form.getFieldsValue()
    try {
      const r = await adminApi.previewSegment(buildSegment(v))
      setCount(r.count)
    } catch { message.error('Ошибка предпросмотра') }
  }

  const create = async () => {
    const v = await form.validateFields()
    try {
      await adminApi.createCampaign({
        title: v.title, channel: v.channel, subject: v.subject, body: v.body, link: v.link,
        segment: buildSegment(v),
      })
      message.success('Кампания создана (черновик)')
      setOpen(false); form.resetFields(); setCount(null); load()
    } catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
  }

  const send = async (id: number) => {
    try { await adminApi.sendCampaign(id); message.success('Рассылка запущена'); load() }
    catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <Title level={3} style={{ marginTop: 0 }}>Рассылки</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setOpen(true); setCount(null); form.setFieldsValue({ channel: 'email' }) }}>
          Новая рассылка
        </Button>
      </div>
      <Paragraph type="secondary">
        Отправляйте письма (Postbox) или внутренние уведомления выбранному сегменту пользователей.
        Отписавшиеся и неактивные исключаются автоматически.
      </Paragraph>

      <Table
        loading={loading} rowKey="id" dataSource={rows} pagination={false}
        columns={[
          { title: 'Название', dataIndex: 'title' },
          { title: 'Канал', dataIndex: 'channel', render: (c) => <Tag>{c === 'email' ? 'Email' : 'Уведомление'}</Tag> },
          { title: 'Получателей', dataIndex: 'recipients' },
          { title: 'Отправлено', dataIndex: 'sent_count' },
          { title: 'Статус', dataIndex: 'status', render: (s) => <Tag color={statusMeta[s]?.color}>{statusMeta[s]?.label || s}</Tag> },
          { title: 'Создана', dataIndex: 'created_at', render: (v) => new Date(v).toLocaleString('ru') },
          {
            title: '', render: (_, r) => r.status === 'draft' || r.status === 'failed' ? (
              <Popconfirm title={`Отправить ${r.recipients} получателям?`} onConfirm={() => send(r.id)}>
                <Button size="small" type="primary" icon={<SendOutlined />}>Отправить</Button>
              </Popconfirm>
            ) : '—',
          },
        ]}
      />

      <Modal title="Новая рассылка" open={open} onOk={create} onCancel={() => setOpen(false)} okText="Создать черновик" width={640}>
        <Form form={form} layout="vertical">
          <Row gutter={12}>
            <Col span={16}><Form.Item name="title" label="Название (внутреннее)" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={8}>
              <Form.Item name="channel" label="Канал">
                <Select options={[{ value: 'email', label: 'Email' }, { value: 'inapp', label: 'Уведомление' }]} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="subject" label="Тема / Заголовок"><Input /></Form.Item>
          <Form.Item name="body" label="Текст" rules={[{ required: true }]}><Input.TextArea rows={4} /></Form.Item>
          <Form.Item name="link" label="Ссылка (необязательно)"><Input placeholder="/catalog или https://..." /></Form.Item>

          <Alert type="info" showIcon style={{ marginBottom: 12 }} message="Сегмент получателей" />
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="role" label="Роль">
                <Select allowClear placeholder="любая" options={[
                  { value: 'buyer', label: 'Покупатели' }, { value: 'seller', label: 'Продавцы' },
                ]} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="active_within_days" label="Активны за N дней">
                <InputNumber min={1} style={{ width: '100%' }} placeholder="не важно" />
              </Form.Item>
            </Col>
          </Row>
          <Space size="large">
            <Form.Item name="only_verified_email" label="Только подтв. email" valuePropName="checked"><Switch /></Form.Item>
            <Form.Item name="has_referral_balance" label="С реф. балансом" valuePropName="checked"><Switch /></Form.Item>
          </Space>
          <div>
            <Button onClick={preview}>Посчитать получателей</Button>
            {count !== null && <Tag color="blue" style={{ marginLeft: 8 }}>≈ {count} получателей</Tag>}
          </div>
        </Form>
      </Modal>
    </div>
  )
}
