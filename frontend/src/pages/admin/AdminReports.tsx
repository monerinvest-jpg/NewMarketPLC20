import { useEffect, useState } from 'react'
import { Table, Tag, Select, Button, Modal, Input, message, Typography } from 'antd'
import { adminApi } from '@/api'
import type { Report } from '@/types'
import dayjs from 'dayjs'

const { Title } = Typography

const statusLabels: Record<string, { label: string; color: string }> = {
  open: { label: 'Открыта', color: 'red' },
  in_review: { label: 'На рассмотрении', color: 'orange' },
  resolved: { label: 'Решена', color: 'green' },
  dismissed: { label: 'Отклонена', color: 'default' },
}

const targetLabels: Record<string, string> = {
  product: 'Товар', shop: 'Магазин', user: 'Пользователь',
}

export default function AdminReports() {
  const [reports, setReports] = useState<Report[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string | undefined>('open')
  const [resolveModal, setResolveModal] = useState<{ open: boolean; report?: Report }>({ open: false })
  const [resolution, setResolution] = useState('')

  const load = () => {
    setLoading(true)
    adminApi.listReports({ page, status: statusFilter })
      .then((res) => { setReports(res.items); setTotal(res.total) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page, statusFilter])

  const openResolve = (report: Report) => {
    setResolveModal({ open: true, report })
    setResolution('')
  }

  const handleResolve = async (status: string) => {
    if (resolveModal.report) {
      await adminApi.updateReport(resolveModal.report.id, { status, resolution })
      message.success('Жалоба обновлена')
      setResolveModal({ open: false })
      load()
    }
  }

  return (
    <div>
      <Title level={3}>Жалобы</Title>
      <Select
        value={statusFilter} style={{ width: 200, marginBottom: 16 }}
        onChange={setStatusFilter} allowClear placeholder="Все статусы"
        options={Object.entries(statusLabels).map(([k, v]) => ({ value: k, label: v.label }))}
      />

      <Table
        loading={loading}
        dataSource={reports}
        rowKey="id"
        pagination={{ current: page, total, pageSize: 20, onChange: setPage, showSizeChanger: false }}
        columns={[
          { title: '№', dataIndex: 'id', width: 60 },
          { title: 'Дата', dataIndex: 'created_at', render: (v) => dayjs(v).format('DD.MM.YYYY') },
          { title: 'Цель', dataIndex: 'target_type', render: (t) => targetLabels[t] },
          { title: 'ID цели', dataIndex: 'target_id' },
          { title: 'Причина', dataIndex: 'reason', ellipsis: true },
          {
            title: 'Статус', dataIndex: 'status',
            render: (s) => <Tag color={statusLabels[s]?.color}>{statusLabels[s]?.label}</Tag>,
          },
          {
            title: 'Действия',
            render: (_, report) => (
              report.status === 'open' || report.status === 'in_review' ? (
                <Button size="small" onClick={() => openResolve(report)}>Рассмотреть</Button>
              ) : null
            ),
          },
        ]}
      />

      <Modal
        title={`Жалоба #${resolveModal.report?.id}`}
        open={resolveModal.open}
        onCancel={() => setResolveModal({ open: false })}
        footer={[
          <Button key="dismiss" onClick={() => handleResolve('dismissed')}>Отклонить жалобу</Button>,
          <Button key="resolve" type="primary" onClick={() => handleResolve('resolved')}>Решить</Button>,
        ]}
      >
        <p><strong>Причина:</strong> {resolveModal.report?.reason}</p>
        <Input.TextArea
          rows={3} placeholder="Комментарий модератора / принятые меры"
          value={resolution}
          onChange={(e) => setResolution(e.target.value)}
        />
      </Modal>
    </div>
  )
}
