import { useEffect, useState } from 'react'
import { Card, Table, Tag, Typography, Empty, Spin } from 'antd'
import { returnsApi } from '@/api'
import type { ReturnRequest } from '@/types'
import dayjs from 'dayjs'

const { Title } = Typography

const statusLabels: Record<string, { label: string; color: string }> = {
  requested: { label: 'Заявка подана', color: 'orange' },
  approved: { label: 'Одобрена', color: 'blue' },
  rejected: { label: 'Отклонена', color: 'red' },
  in_transit: { label: 'В пути обратно', color: 'cyan' },
  refunded: { label: 'Возврат выполнен', color: 'green' },
}

export default function ReturnsPage() {
  const [returns, setReturns] = useState<ReturnRequest[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    returnsApi.my().then(setReturns).finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div>
      <Title level={3}>Мои возвраты</Title>
      <Card>
        {returns.length === 0 ? (
          <Empty description="У вас пока нет заявок на возврат" />
        ) : (
          <Table
            dataSource={returns}
            rowKey="id"
            pagination={false}
            columns={[
              { title: '№', dataIndex: 'id', width: 60 },
              { title: 'Дата', dataIndex: 'created_at', render: (v) => dayjs(v).format('DD.MM.YYYY') },
              { title: 'Кол-во', dataIndex: 'quantity', width: 80 },
              { title: 'Причина', dataIndex: 'reason' },
              { title: 'Сумма возврата', dataIndex: 'refund_amount', render: (v) => `${parseFloat(v).toLocaleString('ru')} ₽` },
              { title: 'Статус', dataIndex: 'status', render: (v) => <Tag color={statusLabels[v]?.color}>{statusLabels[v]?.label}</Tag> },
              { title: 'Комментарий', dataIndex: 'resolution_comment', render: (v) => v || '—' },
            ]}
          />
        )}
      </Card>
    </div>
  )
}
