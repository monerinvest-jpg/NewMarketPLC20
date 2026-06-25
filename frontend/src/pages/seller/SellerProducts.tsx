import { useEffect, useState } from 'react'
import {
  Table, Button, Modal, Form, Input, InputNumber, Select,
  Tag, Upload, message, Space, Popconfirm, Typography
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined, DownloadOutlined } from '@ant-design/icons'
import { productsApi, categoriesApi } from '@/api'
import type { Product, Category } from '@/types'
import type { UploadFile } from 'antd/es/upload/interface'

const { Title, Text } = Typography

const statusLabels: Record<string, { label: string; color: string }> = {
  pending: { label: 'На модерации', color: 'orange' },
  active: { label: 'Активен', color: 'green' },
  rejected: { label: 'Отклонён', color: 'red' },
  blocked: { label: 'Блокирован', color: 'volcano' },
}

export default function SellerProducts() {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [form] = Form.useForm()
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<number[]>([])
  const [bulkModal, setBulkModal] = useState<'price' | 'percent' | null>(null)
  const [bulkValue, setBulkValue] = useState<number>(0)

  const flattenCategories = (cats: Category[]): Category[] =>
    cats.flatMap((c) => [c, ...flattenCategories(c.children || [])])

  const loadProducts = () => {
    setLoading(true)
    productsApi.myProducts({ page_size: 50 })
      .then((res) => setProducts(res.items))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadProducts()
    categoriesApi.list().then((cats) => setCategories(flattenCategories(cats)))
  }, [])

  const applyBulkPrice = async () => {
    const { inventoryApi } = await import('@/api')
    try {
      if (bulkModal === 'price') {
        await inventoryApi.bulkPrice(selectedRowKeys, { set_price: bulkValue })
      } else {
        await inventoryApi.bulkPrice(selectedRowKeys, { change_percent: bulkValue })
      }
      message.success('Цены обновлены')
      setBulkModal(null); setSelectedRowKeys([]); loadProducts()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const applyBulkStatus = async (isActive: boolean) => {
    const { inventoryApi } = await import('@/api')
    try {
      await inventoryApi.bulkStatus(selectedRowKeys, isActive)
      message.success(isActive ? 'Товары активированы' : 'Товары скрыты')
      setSelectedRowKeys([]); loadProducts()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const exportCsv = () => {
    const token = localStorage.getItem('access_token')
    fetch('/api/v1/seller/products/export-csv', { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = 'products.csv'; a.click()
        URL.revokeObjectURL(url)
      })
      .catch(() => message.error('Ошибка экспорта'))
  }

  const openCreate = () => {
    setEditingProduct(null)
    form.resetFields()
    setFileList([])
    setModalOpen(true)
  }

  const openEdit = (product: Product) => {
    setEditingProduct(product)
    form.setFieldsValue(product)
    setFileList([])
    setModalOpen(true)
  }

  const handleSubmit = async (values: any) => {
    setSubmitting(true)
    try {
      let product: Product
      if (editingProduct) {
        product = await productsApi.update(editingProduct.id, values)
        message.success('Товар обновлён')
      } else {
        product = await productsApi.create(values)
        message.success('Товар создан и отправлен на модерацию')
      }

      // Upload images
      for (let i = 0; i < fileList.length; i++) {
        const file = fileList[i].originFileObj as File
        if (file) {
          await productsApi.uploadImage(product.id, file, i === 0)
        }
      }

      setModalOpen(false)
      loadProducts()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка сохранения')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id: number) => {
    await productsApi.delete(id)
    message.success('Товар удалён')
    loadProducts()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Мои товары</Title>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={exportCsv}>Экспорт CSV</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>Добавить товар</Button>
        </Space>
      </div>

      {selectedRowKeys.length > 0 && (
        <div style={{ marginBottom: 12, padding: '8px 12px', background: '#fff7e6', borderRadius: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <Text>Выбрано: {selectedRowKeys.length}</Text>
          <Button size="small" onClick={() => setBulkModal('price')}>Установить цену</Button>
          <Button size="small" onClick={() => setBulkModal('percent')}>Изменить цену на %</Button>
          <Button size="small" onClick={() => applyBulkStatus(true)}>Активировать</Button>
          <Button size="small" onClick={() => applyBulkStatus(false)}>Скрыть</Button>
          <Button size="small" type="text" onClick={() => setSelectedRowKeys([])}>Сбросить</Button>
        </div>
      )}

      <Table
        loading={loading}
        dataSource={products}
        rowKey="id"
        rowSelection={{ selectedRowKeys, onChange: (keys) => setSelectedRowKeys(keys as number[]) }}
        columns={[
          {
            title: 'Фото', width: 70,
            render: (_, p) => {
              const img = p.images.find((i) => i.is_main) || p.images[0]
              return img ? <img src={img.url} style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 6 }} /> : '—'
            },
          },
          { title: 'Название', dataIndex: 'title' },
          { title: 'Цена', dataIndex: 'price', render: (v) => `${parseFloat(v).toLocaleString('ru')} ₽` },
          { title: 'Остаток', dataIndex: 'quantity' },
          {
            title: 'Статус', dataIndex: 'status',
            render: (s) => <Tag color={statusLabels[s]?.color}>{statusLabels[s]?.label}</Tag>,
          },
          {
            title: 'Действия', width: 120,
            render: (_, p) => (
              <Space>
                <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(p)} />
                <Popconfirm title="Удалить товар?" onConfirm={() => handleDelete(p.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editingProduct ? 'Редактировать товар' : 'Новый товар'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={submitting}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="title" label="Название" rules={[{ required: true, min: 3 }]}>
            <Input />
          </Form.Item>
          <Form.Item name="category_id" label="Категория" rules={[{ required: true }]}>
            <Select options={categories.map((c) => ({ value: c.id, label: c.name }))} />
          </Form.Item>
          <Form.Item name="description" label="Описание">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Space style={{ width: '100%' }}>
            <Form.Item name="price" label="Цена, ₽" rules={[{ required: true }]} style={{ flex: 1 }}>
              <InputNumber min={0.01} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="compare_at_price" label="Старая цена, ₽" style={{ flex: 1 }}>
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
          </Space>
          <Space style={{ width: '100%' }}>
            <Form.Item name="quantity" label="Остаток" rules={[{ required: true }]} style={{ flex: 1 }}>
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="weight_g" label="Вес, г" initialValue={500} style={{ flex: 1 }}>
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          </Space>
          <Form.Item label="Изображения">
            <Upload
              listType="picture-card"
              fileList={fileList}
              beforeUpload={() => false}
              onChange={({ fileList }) => setFileList(fileList)}
              multiple
            >
              {fileList.length < 5 && <UploadOutlined />}
            </Upload>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={bulkModal === 'price' ? 'Установить цену для выбранных' : 'Изменить цену на процент'}
        open={bulkModal !== null}
        onCancel={() => setBulkModal(null)}
        onOk={applyBulkPrice}
        okText="Применить"
      >
        <Text type="secondary">
          {bulkModal === 'price'
            ? `Новая цена будет установлена для ${selectedRowKeys.length} товаров.`
            : `Например, -10 — снизить на 10%, 15 — повысить на 15%. Затронуто товаров: ${selectedRowKeys.length}.`}
        </Text>
        <InputNumber
          style={{ width: '100%', marginTop: 12 }}
          value={bulkValue}
          onChange={(v) => setBulkValue(v ?? 0)}
          addonAfter={bulkModal === 'percent' ? '%' : '₽'}
        />
      </Modal>
    </div>
  )
}
