import { useEffect, useState } from 'react'
import {
  Table, Tag, Select, Button, Modal, Input, message,
  Space, Typography, Image
} from 'antd'
import { CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { adminApi } from '@/api'
import type { Product } from '@/types'

const { Title } = Typography

const statusLabels: Record<string, { label: string; color: string }> = {
  pending: { label: 'На модерации', color: 'orange' },
  active: { label: 'Активен', color: 'green' },
  rejected: { label: 'Отклонён', color: 'red' },
  blocked: { label: 'Блокирован', color: 'volcano' },
}

export default function AdminProducts() {
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string | undefined>('pending')
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [rejectModal, setRejectModal] = useState<{ open: boolean; productId?: number }>({ open: false })
  const [rejectReason, setRejectReason] = useState('')

  const load = () => {
    setLoading(true)
    adminApi.listProducts({ page, status: statusFilter })
      .then((res) => { setProducts(res.items); setTotal(res.total) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page, statusFilter])

  const handleApprove = async (id: number) => {
    await adminApi.moderateProduct(id, { status: 'active' })
    message.success('Товар одобрен')
    load()
  }

  const handleReject = (id: number) => {
    setRejectModal({ open: true, productId: id })
    setRejectReason('')
  }

  const confirmReject = async () => {
    if (!rejectReason.trim()) { message.warning('Укажите причину отклонения'); return }
    if (rejectModal.productId) {
      await adminApi.moderateProduct(rejectModal.productId, { status: 'rejected', moderation_reason: rejectReason })
      message.success('Товар отклонён')
      setRejectModal({ open: false })
      load()
    }
  }

  const handleBulkApprove = async () => {
    await adminApi.bulkModerate(selectedRowKeys as number[], 'active')
    message.success(`Одобрено товаров: ${selectedRowKeys.length}`)
    setSelectedRowKeys([])
    load()
  }

  return (
    <div>
      <Title level={3}>Товары (модерация)</Title>

      <Space style={{ marginBottom: 16 }}>
        <Select
          value={statusFilter} style={{ width: 200 }}
          onChange={setStatusFilter}
          options={[
            { value: 'pending', label: 'На модерации' },
            { value: 'active', label: 'Активные' },
            { value: 'rejected', label: 'Отклонённые' },
            { value: 'blocked', label: 'Блокированные' },
          ]}
        />
        {selectedRowKeys.length > 0 && (
          <Button type="primary" onClick={handleBulkApprove}>
            Одобрить выбранные ({selectedRowKeys.length})
          </Button>
        )}
      </Space>

      <Table
        loading={loading}
        dataSource={products}
        rowKey="id"
        rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys }}
        pagination={{ current: page, total, pageSize: 20, onChange: setPage, showSizeChanger: false }}
        columns={[
          {
            title: 'Фото', width: 70,
            render: (_, p) => {
              const img = p.images.find((i) => i.is_main) || p.images[0]
              return img ? <Image src={img.url} width={48} height={48} style={{ objectFit: 'cover', borderRadius: 6 }} /> : '—'
            },
          },
          { title: 'Название', dataIndex: 'title' },
          { title: 'Цена', dataIndex: 'price', render: (v) => `${parseFloat(v).toLocaleString('ru')} ₽` },
          { title: 'Магазин ID', dataIndex: 'shop_id' },
          {
            title: 'Статус', dataIndex: 'status',
            render: (s) => <Tag color={statusLabels[s]?.color}>{statusLabels[s]?.label}</Tag>,
          },
          {
            title: 'Действия',
            render: (_, p) => (
              p.status === 'pending' && (
                <Space>
                  <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => handleApprove(p.id)} />
                  <Button size="small" danger icon={<CloseOutlined />} onClick={() => handleReject(p.id)} />
                </Space>
              )
            ),
          },
        ]}
      />

      <Modal
        title="Причина отклонения" open={rejectModal.open}
        onCancel={() => setRejectModal({ open: false })} onOk={confirmReject}
      >
        <Input.TextArea
          rows={3} value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
          placeholder="Например: товар нарушает правила платформы"
        />
      </Modal>
    </div>
  )
}
