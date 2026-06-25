import { useEffect, useState } from 'react'
import { Card, Table, Typography, Tag, Input, Select, Space, Spin, Button } from 'antd'
import { adminApi } from '@/api'
import dayjs from 'dayjs'

const { Title } = Typography

interface AuditEntry {
  id: number
  actor_id?: number
  actor_email?: string
  action: string
  entity_type: string
  entity_id?: number
  detail?: string
  created_at: string
}

const entityColors: Record<string, string> = {
  shop: 'blue', product: 'green', payout: 'gold', user: 'purple', order: 'cyan',
}

export default function AdminAuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [entityType, setEntityType] = useState<string | undefined>()
  const [actionFilter, setActionFilter] = useState('')

  const load = () => {
    setLoading(true)
    adminApi.auditLog({ entity_type: entityType, action: actionFilter || undefined, page })
      .then((res) => { setEntries(res.items); setTotal(res.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [page, entityType])

  const exportCsv = () => {
    const token = localStorage.getItem('access_token')
    fetch('/api/v1/admin/audit-log/export', { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = 'audit-log.csv'; a.click()
        URL.revokeObjectURL(url)
      })
      .catch(() => {})
  }

  return (
    <div>
      <Title level={3}>Журнал действий (аудит)</Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          placeholder="Тип объекта" allowClear style={{ width: 160 }}
          value={entityType} onChange={(v) => { setEntityType(v); setPage(1) }}
          options={[
            { value: 'shop', label: 'Магазины' },
            { value: 'product', label: 'Товары' },
            { value: 'payout', label: 'Выплаты' },
            { value: 'user', label: 'Пользователи' },
            { value: 'order', label: 'Заказы' },
          ]}
        />
        <Input.Search
          placeholder="Поиск по действию" value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          onSearch={() => { setPage(1); load() }} style={{ width: 220 }} allowClear
        />
        <Button onClick={exportCsv}>Экспорт CSV</Button>
      </Space>

      <Card>
        <Spin spinning={loading}>
          <Table
            dataSource={entries}
            rowKey="id"
            pagination={{ current: page, total, pageSize: 50, onChange: setPage }}
            columns={[
              { title: 'Время', dataIndex: 'created_at', width: 150, render: (v) => dayjs(v).format('DD.MM.YY HH:mm:ss') },
              { title: 'Кто', dataIndex: 'actor_email', render: (v) => v || <Typography.Text type="secondary">система</Typography.Text> },
              { title: 'Действие', dataIndex: 'action', render: (v) => <Tag>{v}</Tag> },
              {
                title: 'Объект', render: (_, r) => (
                  <Tag color={entityColors[r.entity_type] || 'default'}>
                    {r.entity_type}{r.entity_id ? ` #${r.entity_id}` : ''}
                  </Tag>
                ),
              },
              { title: 'Детали', dataIndex: 'detail', ellipsis: true, render: (v) => v || '—' },
            ]}
          />
        </Spin>
      </Card>
    </div>
  )
}
