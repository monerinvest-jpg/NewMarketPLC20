import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Table, Row, Col, Statistic, Spin, Alert, Typography, Space,
  Button, Modal, Form, Input, InputNumber, Switch, message,
} from 'antd'
import { EditOutlined } from '@ant-design/icons'
import { adminApi } from '@/api'

const { Title, Text } = Typography

const money = (v: any) => `${parseFloat(v || 0).toLocaleString('ru')} ₽`
const dt = (v: string) => new Date(v).toLocaleString('ru')

export default function AdminShopDetail() {
  const { id } = useParams()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [editOpen, setEditOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()

  const load = () => {
    setLoading(true)
    adminApi.shopDetail(Number(id)).then(setData).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [id])

  const openEdit = () => {
    const sh = data.shop
    form.setFieldsValue({
      name: sh.name, description: sh.description, tagline: sh.tagline,
      contact_email: sh.contact_email, contact_phone: sh.contact_phone,
      accent_color: sh.accent_color,
      commission_percent: sh.commission_percent != null ? parseFloat(sh.commission_percent) : null,
      is_active: sh.is_active,
    })
    setEditOpen(true)
  }

  const saveEdit = async () => {
    const v = await form.validateFields()
    setSaving(true)
    try {
      await adminApi.updateShop(Number(id), v)
      message.success('Магазин обновлён')
      setEditOpen(false)
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка сохранения')
    } finally { setSaving(false) }
  }

  const moderate = async (status: string) => {
    let reason: string | undefined
    if (status !== 'active') {
      reason = window.prompt('Причина (обязательно):') || ''
      if (!reason) return
    }
    try {
      await adminApi.moderateShop(Number(id), status, reason)
      message.success('Статус магазина изменён')
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (!data) return <Alert type="error" message="Магазин не найден" />

  const shop = data.shop
  const s = data.stats

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      <Space style={{ marginBottom: 12 }}>
        <Link to="/admin/shops">← К списку магазинов</Link>
        {data.owner && <Link to={`/admin/users/${data.owner.id}`}>· Владелец: {data.owner.full_name}</Link>}
      </Space>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <Title level={3} style={{ marginTop: 0 }}>
          {shop.name} <Text type="secondary" style={{ fontSize: 15 }}>#{shop.id}</Text>{' '}
          <Tag color={shop.status === 'active' ? 'green' : shop.status === 'suspended' ? 'red' : 'orange'}>{shop.status}</Tag>
        </Title>
        <Space wrap>
          <Button icon={<EditOutlined />} type="primary" onClick={openEdit}>Редактировать</Button>
          {shop.status !== 'active' && <Button onClick={() => moderate('active')}>Одобрить</Button>}
          {shop.status === 'active' && <Button danger onClick={() => moderate('suspended')}>Заблокировать</Button>}
          {shop.status === 'pending' && <Button danger onClick={() => moderate('rejected')}>Отклонить</Button>}
        </Space>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Оборот (GMV)" value={parseFloat(s.gross_sales)} precision={2} suffix="₽" /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Комиссия платформы" value={parseFloat(s.platform_fees)} precision={2} suffix="₽" valueStyle={{ color: '#b45309' }} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Заработок продавца" value={parseFloat(s.seller_net)} precision={2} suffix="₽" /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Выплачено" value={parseFloat(s.payouts_paid)} precision={2} suffix="₽" /></Card></Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card title="Магазин" size="small" style={{ marginBottom: 16 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Описание">{shop.description || '—'}</Descriptions.Item>
              <Descriptions.Item label="Комиссия">{shop.commission_percent != null ? `${shop.commission_percent}%` : 'по умолчанию'}</Descriptions.Item>
              <Descriptions.Item label="Товаров">{s.products_count}</Descriptions.Item>
              <Descriptions.Item label="Заказов">{s.orders_count}</Descriptions.Item>
              <Descriptions.Item label="Активен">{shop.is_active ? 'да' : 'нет'}</Descriptions.Item>
              {shop.moderation_reason && <Descriptions.Item label="Причина модерации">{shop.moderation_reason}</Descriptions.Item>}
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="Владелец" size="small" style={{ marginBottom: 16 }}>
            {data.owner ? (
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Имя"><Link to={`/admin/users/${data.owner.id}`}>{data.owner.full_name}</Link></Descriptions.Item>
                <Descriptions.Item label="Email">{data.owner.email}</Descriptions.Item>
                <Descriptions.Item label="Роль">{data.owner.role}</Descriptions.Item>
                <Descriptions.Item label="Баланс">{money(data.owner.balance)}</Descriptions.Item>
              </Descriptions>
            ) : <Text type="secondary">—</Text>}
          </Card>
        </Col>
      </Row>

      <Card title="Последние заказы магазина" size="small">
        <Table
          rowKey="id" size="small" pagination={false} dataSource={data.recent_orders}
          columns={[
            { title: '№', dataIndex: 'id', render: (v) => <Link to={`/orders/${v}`}>#{v}</Link> },
            { title: 'Сумма', dataIndex: 'total_price', render: money },
            { title: 'Статус', dataIndex: 'status' },
            { title: 'Дата', dataIndex: 'created_at', render: dt },
          ]}
        />
      </Card>

      <Modal
        title="Редактирование магазина" open={editOpen} onOk={saveEdit} confirmLoading={saving}
        onCancel={() => setEditOpen(false)} okText="Сохранить" width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Название" rules={[{ required: true, min: 2 }]}><Input /></Form.Item>
          <Form.Item name="tagline" label="Слоган"><Input /></Form.Item>
          <Form.Item name="description" label="Описание"><Input.TextArea rows={3} /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="contact_email" label="Контактный email"><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="contact_phone" label="Контактный телефон"><Input /></Form.Item></Col>
          </Row>
          <Row gutter={12}>
            <Col span={8}><Form.Item name="accent_color" label="Цвет акцента"><Input placeholder="#b45309" /></Form.Item></Col>
            <Col span={8}>
              <Form.Item name="commission_percent" label="Комиссия %">
                <InputNumber min={0} max={100} style={{ width: '100%' }} placeholder="глоб." />
              </Form.Item>
            </Col>
            <Col span={8}><Form.Item name="is_active" label="Активен" valuePropName="checked"><Switch /></Form.Item></Col>
          </Row>
        </Form>
      </Modal>
    </div>
  )
}
