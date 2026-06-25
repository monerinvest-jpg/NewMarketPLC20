import { useEffect, useState } from 'react'
import {
  Table, Button, Modal, Form, Input, InputNumber, Select,
  DatePicker, Switch, Tag, message, Typography, Popconfirm
} from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { adminApi } from '@/api'
import type { Coupon } from '@/types'
import dayjs from 'dayjs'

const { Title } = Typography
const { RangePicker } = DatePicker

export default function AdminCoupons() {
  const [coupons, setCoupons] = useState<Coupon[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)

  const load = () => {
    setLoading(true)
    adminApi.listCoupons().then(setCoupons).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleSubmit = async (values: any) => {
    setSubmitting(true)
    try {
      const [validFrom, validUntil] = values.dates
      await adminApi.createCoupon({
        code: values.code,
        discount_type: values.discount_type,
        discount_value: values.discount_value,
        valid_from: validFrom.toISOString(),
        valid_until: validUntil.toISOString(),
        max_uses: values.max_uses || 0,
        min_order_amount: values.min_order_amount || 0,
        is_active: true,
      })
      message.success('Купон создан')
      setModalOpen(false)
      form.resetFields()
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id: number) => {
    await adminApi.deleteCoupon(id)
    message.success('Купон удалён')
    load()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Купоны и скидки</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>Создать купон</Button>
      </div>

      <Table
        loading={loading}
        dataSource={coupons}
        rowKey="id"
        columns={[
          { title: 'Код', dataIndex: 'code', render: (v) => <Tag color="orange">{v}</Tag> },
          {
            title: 'Скидка',
            render: (_, c) => c.discount_type === 'percent' ? `${c.discount_value}%` : `${c.discount_value} ₽`,
          },
          { title: 'Действует с', dataIndex: 'valid_from', render: (v) => dayjs(v).format('DD.MM.YYYY') },
          { title: 'До', dataIndex: 'valid_until', render: (v) => dayjs(v).format('DD.MM.YYYY') },
          { title: 'Использован', render: (_, c) => `${c.used_count} / ${c.max_uses || '∞'}` },
          { title: 'Активен', dataIndex: 'is_active', render: (v) => v ? <Tag color="green">Да</Tag> : <Tag>Нет</Tag> },
          {
            title: 'Действия',
            render: (_, c) => (
              <Popconfirm title="Удалить купон?" onConfirm={() => handleDelete(c.id)}>
                <Button danger size="small" icon={<DeleteOutlined />} />
              </Popconfirm>
            ),
          },
        ]}
      />

      <Modal
        title="Новый купон" open={modalOpen}
        onCancel={() => setModalOpen(false)} onOk={() => form.submit()}
        confirmLoading={submitting}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="code" label="Код купона" rules={[{ required: true }]}>
            <Input placeholder="SUMMER2026" style={{ textTransform: 'uppercase' }} />
          </Form.Item>
          <Form.Item name="discount_type" label="Тип скидки" rules={[{ required: true }]} initialValue="percent">
            <Select options={[
              { value: 'percent', label: 'Процент от суммы' },
              { value: 'fixed', label: 'Фиксированная сумма' },
            ]} />
          </Form.Item>
          <Form.Item name="discount_value" label="Размер скидки" rules={[{ required: true }]}>
            <InputNumber min={0.01} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="dates" label="Период действия" rules={[{ required: true }]}>
            <RangePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="max_uses" label="Максимум использований (0 = без лимита)" initialValue={0}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="min_order_amount" label="Минимальная сумма заказа, ₽" initialValue={0}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
