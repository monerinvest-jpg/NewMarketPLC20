import { useEffect, useState } from 'react'
import { Card, Table, Typography, Button, InputNumber, Form, Input, Switch, message, Modal, Popconfirm, Tag } from 'antd'
import { loyaltyApi } from '@/api'
import type { LoyaltyTier } from '@/types'

const { Title, Paragraph } = Typography

export default function AdminLoyaltyTiers() {
  const [tiers, setTiers] = useState<LoyaltyTier[]>([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<LoyaltyTier | null>(null)
  const [form] = Form.useForm()

  const load = () => loyaltyApi.adminList().then(setTiers).catch(() => {})
  useEffect(() => { load() }, [])

  const openModal = (t?: LoyaltyTier) => {
    setEditing(t || null)
    form.setFieldsValue(t || { level: tiers.length + 1, free_shipping: false, is_active: true, retention_days: 0 })
    setOpen(true)
  }

  const submit = async () => {
    const v = await form.validateFields()
    if (editing) await loyaltyApi.adminUpdate(editing.id, v)
    else await loyaltyApi.adminCreate(v)
    message.success('Сохранено')
    setOpen(false); form.resetFields(); load()
  }

  const del = async (id: number) => { await loyaltyApi.adminDelete(id); load() }

  return (
    <div>
      <Title level={3}>Программа лояльности</Title>
      <Paragraph type="secondary">
        Настройте уровни: порог суммы покупок, кэшбэк, привилегии и срок неактивности до понижения (0 — без понижения).
      </Paragraph>
      <Card extra={<Button type="primary" onClick={() => openModal()}>Добавить уровень</Button>}>
        <Table<LoyaltyTier>
          dataSource={tiers} rowKey="id" pagination={false}
          columns={[
            { title: 'Уровень', dataIndex: 'level', width: 80 },
            { title: 'Название', dataIndex: 'name', render: (v, t) => <Tag color="default" style={{ borderColor: t.color || undefined }}>{v}</Tag> },
            { title: 'Порог, ₽', dataIndex: 'min_spend', render: (v) => Number(v).toLocaleString('ru') },
            { title: 'Кэшбэк', dataIndex: 'cashback_percent', render: (v) => `${Number(v)}%` },
            { title: 'Бесплат. доставка', dataIndex: 'free_shipping', render: (v) => v ? <Tag color="green">Да</Tag> : '—' },
            { title: 'Распад, дн.', dataIndex: 'retention_days', render: (v) => v || '—' },
            { title: 'Активен', dataIndex: 'is_active', render: (v) => v ? <Tag color="green">Да</Tag> : <Tag>Нет</Tag> },
            { title: '', render: (_, t) => (
              <>
                <Button size="small" onClick={() => openModal(t)}>Изменить</Button>{' '}
                <Popconfirm title="Удалить уровень?" onConfirm={() => del(t.id)}><Button size="small" danger>Удалить</Button></Popconfirm>
              </>
            ) },
          ]}
        />
      </Card>

      <Modal title={editing ? `Изменить: ${editing.name}` : 'Новый уровень'} open={open} onCancel={() => setOpen(false)} onOk={submit} okText="Сохранить">
        <Form form={form} layout="vertical">
          {!editing && <Form.Item name="key" label="Ключ (латиницей)" rules={[{ required: true }]}><Input placeholder="platinum" /></Form.Item>}
          <Form.Item name="name" label="Название" rules={[{ required: true }]}><Input placeholder="Платина" /></Form.Item>
          <Form.Item name="level" label="Порядковый уровень" rules={[{ required: true }]}><InputNumber min={1} style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="min_spend" label="Порог суммы покупок, ₽" rules={[{ required: true }]}><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="cashback_percent" label="Кэшбэк, %" rules={[{ required: true }]}><InputNumber min={0} max={100} style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="retention_days" label="Срок неактивности до понижения, дн. (0 — никогда)"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="color" label="Цвет (hex)"><Input placeholder="#f59e0b" /></Form.Item>
          <Form.Item name="perks" label="Привилегии (описание)"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="free_shipping" label="Бесплатная доставка" valuePropName="checked"><Switch /></Form.Item>
          <Form.Item name="is_active" label="Активен" valuePropName="checked"><Switch /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
