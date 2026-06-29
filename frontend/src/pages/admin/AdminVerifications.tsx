import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Typography, Table, Tag, Button, Select, Space, message, Modal, Input } from 'antd'
import { adminApi } from '@/api'

const { Title } = Typography

const statusMeta: Record<string, { label: string; color: string }> = {
  pending: { label: 'На проверке', color: 'orange' },
  verified: { label: 'Подтверждён', color: 'green' },
  rejected: { label: 'Отклонён', color: 'red' },
  none: { label: '—', color: 'default' },
}

export default function AdminVerifications() {
  const [rows, setRows] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('pending')
  const [reject, setReject] = useState<{ open: boolean; shopId?: number }>({ open: false })
  const [reason, setReason] = useState('')

  const load = () => {
    setLoading(true)
    adminApi.listVerifications(status).then(setRows).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [status])

  const approve = async (shopId: number) => {
    try { await adminApi.reviewVerification(shopId, true); message.success('Подтверждено'); load() }
    catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
  }
  const doReject = async () => {
    if (!reject.shopId) return
    try {
      await adminApi.reviewVerification(reject.shopId, false, reason)
      message.success('Отклонено'); setReject({ open: false }); setReason(''); load()
    } catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
  }

  return (
    <div>
      <Title level={3}>Верификация продавцов (KYC)</Title>
      <Select
        value={status} onChange={setStatus} style={{ width: 200, marginBottom: 16 }}
        options={Object.entries(statusMeta).filter(([k]) => k !== 'none').map(([k, v]) => ({ value: k, label: v.label }))}
      />
      <Table
        loading={loading} rowKey="shop_id" dataSource={rows} pagination={false}
        columns={[
          { title: 'Магазин', render: (_, r) => <Link to={`/admin/shops/${r.shop_id}`}>{r.shop_name} #{r.shop_id}</Link> },
          { title: 'Статус', dataIndex: 'status', render: (s) => <Tag color={statusMeta[s]?.color}>{statusMeta[s]?.label}</Tag> },
          { title: 'Документы', dataIndex: 'documents', render: (d: string[]) => `${d?.length || 0} файл(ов)` },
          { title: 'Заметка', dataIndex: 'note', ellipsis: true },
          { title: 'Подана', dataIndex: 'submitted_at', render: (v) => new Date(v).toLocaleString('ru') },
          {
            title: 'Действия', render: (_, r) => r.status === 'pending' ? (
              <Space>
                <Button size="small" type="primary" onClick={() => approve(r.shop_id)}>Подтвердить</Button>
                <Button size="small" danger onClick={() => setReject({ open: true, shopId: r.shop_id })}>Отклонить</Button>
              </Space>
            ) : (r.reason || '—'),
          },
        ]}
      />
      <Modal title="Отклонить верификацию" open={reject.open} onOk={doReject} onCancel={() => setReject({ open: false })} okText="Отклонить">
        <Input.TextArea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Причина отклонения (обязательно)" />
      </Modal>
    </div>
  )
}
