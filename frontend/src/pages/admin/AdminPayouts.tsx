import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Table, Button, Tag, Select, Modal, Input, message, Typography, Space } from 'antd'
import { adminApi } from '@/api'
import type { PayoutRequest } from '@/types'
import dayjs from 'dayjs'

const { Title } = Typography

const statusLabels: Record<string, { label: string; color: string }> = {
  pending: { label: 'На рассмотрении', color: 'orange' },
  approved: { label: 'Одобрен', color: 'blue' },
  rejected: { label: 'Отклонён', color: 'red' },
  paid: { label: 'Выплачен', color: 'green' },
}

export default function AdminPayouts() {
  const [payouts, setPayouts] = useState<PayoutRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string | undefined>('pending')
  const [modal, setModal] = useState<{ open: boolean; id?: number; action?: string }>({ open: false })
  const [comment, setComment] = useState('')

  const load = () => {
    setLoading(true)
    adminApi.listPayouts(statusFilter).then(setPayouts).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [statusFilter])

  const handleProcess = async () => {
    if (modal.id && modal.action) {
      try {
        await adminApi.processPayout(modal.id, modal.action, comment)
        message.success('Готово')
        setModal({ open: false })
        setComment('')
        load()
      } catch (e: any) {
        message.error(e.response?.data?.detail || 'Ошибка')
      }
    }
  }

  return (
    <div>
      <Title level={3}>Запросы на вывод средств</Title>

      <Select
        value={statusFilter} style={{ width: 200, marginBottom: 16 }} allowClear
        placeholder="Все статусы" onChange={setStatusFilter}
        options={Object.entries(statusLabels).map(([k, v]) => ({ value: k, label: v.label }))}
      />

      <Table
        loading={loading}
        dataSource={payouts}
        rowKey="id"
        columns={[
          { title: '№', dataIndex: 'id', width: 60 },
          { title: 'Дата', dataIndex: 'created_at', render: (v) => dayjs(v).format('DD.MM.YYYY HH:mm') },
          {
            title: 'Пользователь',
            render: (_, p: any) => (
              <Space direction="vertical" size={0}>
                <Link to={`/admin/users/${p.user_id}`}>{p.user_name || `#${p.user_id}`}</Link>
                <span style={{ fontSize: 12, color: '#888' }}>
                  {p.user_email}{' '}
                  {p.user_email_verified === false && <Tag color="red" style={{ marginLeft: 4 }}>email не подтверждён</Tag>}
                </span>
              </Space>
            ),
          },
          {
            title: 'Источник', dataIndex: 'source', width: 110,
            render: (v) => v === 'referral'
              ? <Tag color="purple">Рефералы</Tag>
              : <Tag color="blue">Продажи</Tag>,
          },
          { title: 'Сумма', dataIndex: 'amount', render: (v) => `${parseFloat(v).toLocaleString('ru')} ₽` },
          { title: 'Реквизиты', dataIndex: 'payout_details' },
          { title: 'Статус', dataIndex: 'status', render: (v) => <Tag color={statusLabels[v]?.color}>{statusLabels[v]?.label}</Tag> },
          {
            title: 'Действия', render: (_, p) => p.status === 'pending' || p.status === 'approved' ? (
              <Space>
                {p.status === 'pending' && (
                  <Button size="small" type="primary" onClick={() => setModal({ open: true, id: p.id, action: 'approved' })}>Одобрить</Button>
                )}
                <Button size="small" style={{ background: '#52c41a', color: '#fff' }} onClick={() => setModal({ open: true, id: p.id, action: 'paid' })}>Выплачено</Button>
                <Button size="small" danger onClick={() => setModal({ open: true, id: p.id, action: 'rejected' })}>Отклонить</Button>
              </Space>
            ) : '—',
          },
        ]}
      />

      <Modal
        title="Комментарий (необязательно)" open={modal.open}
        onCancel={() => setModal({ open: false })} onOk={handleProcess}
      >
        <Input.TextArea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Комментарий для продавца" />
      </Modal>
    </div>
  )
}
