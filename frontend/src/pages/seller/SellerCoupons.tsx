import { useEffect, useState } from 'react'
import { Card, Table, Button, Modal, Form, Input, InputNumber, Select, DatePicker, Tag, message, Typography, Popconfirm } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { sellerToolsApi } from '@/api'
import type { SellerCoupon } from '@/types'
import dayjs from 'dayjs'

const { Title } = Typography

export default function SellerCoupons() {
  const [coupons, setCoupons] = useState<SellerCoupon[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const load = () => {
    setLoading(true)
    sellerToolsApi.listCoupons().then(setCoupons).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleSubmit = async (values: any) => {
    try {
      await sellerToolsApi.createCoupon({
        ...values,
        expires_at: values.expires_at ? values.expires_at.toISOString() : undefined,
      })
      message.success('Промокод создан')
      setModalOpen(false)
      form.resetFields()
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const handleDelete = async (id: number) => {
    await sellerToolsApi.deleteCoupon(id)
    message.success('Удалено')
    load()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Мои промокоды</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>Создать промокод</Button>
      </div>

      <Card>
        <Table
          loading={loading}
          dataSource={coupons}
          rowKey="id"
          pagination={false}
          columns={[
            { title: 'Код', dataIndex: 'code', render: (v) => <Tag color="orange">{v}</Tag> },
            {
              title: 'Скидка', render: (_, c) =>
                c.discount_type === 'percent' ? `${c.discount_value}%` : `${c.discount_value} ₽`,
            },
            { title: 'Мин. заказ', dataIndex: 'min_order_amount', render: (v) => `${parseFloat(v).toLocaleString('ru')} ₽` },
            { title: 'Использован', render: (_, c) => `${c.used_count}${c.usage_limit ? ` / ${c.usage_limit}` : ''}` },
            { title: 'Активен', dataIndex: 'is_active', render: (v) => v ? <Tag color="green">Да</Tag> : <Tag>Нет</Tag> },
            { title: 'Истекает', dataIndex: 'expires_at', render: (v) => v ? dayjs(v).format('DD.MM.YYYY') : '—' },
            {
              title: '', render: (_, c) => (
                <Popconfirm title="Удалить?" onConfirm={() => handleDelete(c.id)}>
                  <Button size="small" danger>Удалить</Button>
                </Popconfirm>
              ),
            },
          ]}
        />
      </Card>

      <Modal title="Новый промокод" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={handleSubmit} initialValues={{ discount_type: 'percent', discount_value: 10, min_order_amount: 0 }}>
          <Form.Item name="code" label="Код промокода" rules={[{ required: true }]}>
            <Input placeholder="SALE10" />
          </Form.Item>
          <Form.Item name="discount_type" label="Тип скидки">
            <Select options={[{ value: 'percent', label: 'Процент' }, { value: 'fixed', label: 'Фиксированная сумма' }]} />
          </Form.Item>
          <Form.Item name="discount_value" label="Размер скидки" rules={[{ required: true }]}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="min_order_amount" label="Минимальная сумма заказа">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="usage_limit" label="Лимит использований (пусто = без лимита)">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="expires_at" label="Действует до">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
