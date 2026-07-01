import { useEffect, useState } from 'react'
import { Card, Table, Typography, Button, Modal, Form, Select, InputNumber, DatePicker, message, Tag, Popconfirm, Empty, Spin } from 'antd'
import { PlusOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { inventoryApi, productsApi } from '@/api'
import type { FlashSale, Product } from '@/types'
import dayjs from 'dayjs'

const { Title, Text } = Typography

export default function SellerFlashSales() {
  const [sales, setSales] = useState<FlashSale[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const [s, prods] = await Promise.all([
        inventoryApi.listFlashSales(),
        productsApi.myProducts({ page_size: 100 }),
      ])
      setSales(s)
      setProducts((prods as any).items || [])
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [])

  const handleCreate = async (values: any) => {
    try {
      await inventoryApi.createFlashSale({
        product_id: values.product_id,
        discount_percent: values.discount_percent,
        starts_at: values.range[0].toISOString(),
        ends_at: values.range[1].toISOString(),
      })
      message.success('Акция создана')
      setModalOpen(false); form.resetFields()
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const handleDelete = async (id: number) => {
    await inventoryApi.deleteFlashSale(id)
    message.success('Акция удалена')
    load()
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}><ThunderboltOutlined /> Акции и распродажи</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>Создать акцию</Button>
      </div>

      <Card>
        {sales.length === 0 ? (
          <Empty description="У вас пока нет акций. Создайте распродажу по расписанию." />
        ) : (
          <Table
            dataSource={sales}
            rowKey="id"
            pagination={false}
            columns={[
              { title: 'Товар', dataIndex: 'product_title', ellipsis: true },
              { title: 'Скидка', dataIndex: 'discount_percent', width: 90, render: (v) => `−${parseFloat(v)}%` },
              {
                title: 'Цена', width: 180,
                render: (_, s) => (
                  <span>
                    <Text delete type="secondary">{s.base_price ? parseFloat(s.base_price).toLocaleString('ru') : '—'} ₽</Text>{' '}
                    <Text strong style={{ color: '#b45309' }}>{s.effective_price ? parseFloat(s.effective_price).toLocaleString('ru') : '—'} ₽</Text>
                  </span>
                ),
              },
              { title: 'Начало', dataIndex: 'starts_at', render: (v) => dayjs(v).format('DD.MM.YY HH:mm') },
              { title: 'Конец', dataIndex: 'ends_at', render: (v) => dayjs(v).format('DD.MM.YY HH:mm') },
              {
                title: 'Статус', width: 110,
                render: (_, s) => s.is_running
                  ? <Tag color="green">Идёт</Tag>
                  : dayjs(s.starts_at).isAfter(dayjs()) ? <Tag color="blue">Запланирована</Tag> : <Tag>Завершена</Tag>,
              },
              {
                title: '', width: 80,
                render: (_, s) => (
                  <Popconfirm title="Удалить акцию?" onConfirm={() => handleDelete(s.id)}>
                    <Button type="link" danger size="small">Удалить</Button>
                  </Popconfirm>
                ),
              },
            ]}
          />
        )}
      </Card>

      <Modal title="Новая акция" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()} okText="Создать">
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="product_id" label="Товар" rules={[{ required: true }]}>
            <Select
              showSearch optionFilterProp="label"
              placeholder="Выберите товар"
              options={products.map((p) => ({ value: p.id, label: p.title }))}
            />
          </Form.Item>
          <Form.Item name="discount_percent" label="Скидка, %" rules={[{ required: true }]}>
            <InputNumber min={1} max={99} style={{ width: '100%' }} placeholder="20" />
          </Form.Item>
          <Form.Item name="range" label="Период действия" rules={[{ required: true }]}>
            <DatePicker.RangePicker showTime style={{ width: '100%' }} format="DD.MM.YYYY HH:mm" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
