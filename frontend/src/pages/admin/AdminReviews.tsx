import { useEffect, useState } from 'react'
import { Table, Tag, Select, Button, Modal, Input, message, Typography, Rate, Popconfirm } from 'antd'
import { adminApi } from '@/api'
import type { Review } from '@/types'
import dayjs from 'dayjs'

const { Title, Paragraph } = Typography

const statusLabels: Record<string, { label: string; color: string }> = {
  pending: { label: 'На модерации', color: 'orange' },
  approved: { label: 'Одобрен', color: 'green' },
  rejected: { label: 'Отклонён', color: 'red' },
}

export default function AdminReviews() {
  const [reviews, setReviews] = useState<Review[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string | undefined>('pending')
  const [rejectModal, setRejectModal] = useState<{ open: boolean; reviewId?: number }>({ open: false })
  const [rejectReason, setRejectReason] = useState('')

  const load = () => {
    setLoading(true)
    adminApi.listReviews({ page, status: statusFilter })
      .then((res) => { setReviews(res.items); setTotal(res.total) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page, statusFilter])

  const handleApprove = async (id: number) => {
    await adminApi.moderateReview(id, { status: 'approved' })
    message.success('Отзыв одобрен')
    load()
  }

  const handleReject = (id: number) => {
    setRejectModal({ open: true, reviewId: id })
    setRejectReason('')
  }

  const confirmReject = async () => {
    if (!rejectReason.trim()) { message.warning('Укажите причину отклонения'); return }
    if (rejectModal.reviewId) {
      await adminApi.moderateReview(rejectModal.reviewId, { status: 'rejected', moderation_reason: rejectReason })
      message.success('Отзыв отклонён')
      setRejectModal({ open: false })
      load()
    }
  }

  const handleDelete = async (id: number) => {
    await adminApi.deleteReview(id)
    message.success('Отзыв удалён')
    load()
  }

  return (
    <div>
      <Title level={3}>Отзывы (модерация)</Title>

      <Select
        value={statusFilter} style={{ width: 200, marginBottom: 16 }}
        onChange={setStatusFilter} allowClear placeholder="Все статусы"
        options={[
          { value: 'pending', label: 'На модерации' },
          { value: 'approved', label: 'Одобренные' },
          { value: 'rejected', label: 'Отклонённые' },
        ]}
      />

      <Table
        loading={loading}
        dataSource={reviews}
        rowKey="id"
        pagination={{ current: page, total, pageSize: 20, onChange: setPage, showSizeChanger: false }}
        columns={[
          { title: '№', dataIndex: 'id', width: 60 },
          { title: 'Дата', dataIndex: 'created_at', render: (v) => dayjs(v).format('DD.MM.YYYY') },
          { title: 'Автор', render: (_, r) => r.user.full_name },
          { title: 'Товар ID', dataIndex: 'product_id' },
          { title: 'Оценка', dataIndex: 'rating', render: (v) => <Rate disabled value={v} style={{ fontSize: 12 }} /> },
          { title: 'Текст', dataIndex: 'text', render: (v) => <Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 0, maxWidth: 240 }}>{v || '—'}</Paragraph> },
          { title: 'Лайки', dataIndex: 'helpful_count' },
          {
            title: 'Статус', dataIndex: 'status',
            render: (s) => <Tag color={statusLabels[s]?.color}>{statusLabels[s]?.label}</Tag>,
          },
          {
            title: 'Действия',
            render: (_, r) => (
              <>
                {r.status === 'pending' && (
                  <>
                    <Button size="small" type="primary" onClick={() => handleApprove(r.id)} style={{ marginRight: 8 }}>
                      Одобрить
                    </Button>
                    <Button size="small" danger onClick={() => handleReject(r.id)} style={{ marginRight: 8 }}>
                      Отклонить
                    </Button>
                  </>
                )}
                <Popconfirm title="Удалить отзыв навсегда?" onConfirm={() => handleDelete(r.id)}>
                  <Button size="small" type="text" danger>Удалить</Button>
                </Popconfirm>
              </>
            ),
          },
        ]}
      />

      <Modal
        title="Причина отклонения отзыва" open={rejectModal.open}
        onCancel={() => setRejectModal({ open: false })} onOk={confirmReject}
      >
        <Input.TextArea
          rows={3} value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
          placeholder="Например: содержит нецензурную лексику"
        />
      </Modal>
    </div>
  )
}
