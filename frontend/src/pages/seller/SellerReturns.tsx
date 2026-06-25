import { useEffect, useState } from 'react'
import { Card, Table, Tag, Typography, Button, Space, Modal, Input, InputNumber, message, Spin } from 'antd'
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

export default function SellerReturns() {
  const [returns, setReturns] = useState<ReturnRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState<{ open: boolean; ret?: ReturnRequest; action?: string }>({ open: false })
  const [comment, setComment] = useState('')
  const [refundAmount, setRefundAmount] = useState<number | undefined>()

  const load = () => {
    setLoading(true)
    returnsApi.seller().then(setReturns).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const handleProcess = async () => {
    if (!modal.ret || !modal.action) return
    try {
      await returnsApi.process(modal.ret.id, modal.action, comment, refundAmount)
      message.success('Готово')
      setModal({ open: false }); setComment(''); setRefundAmount(undefined)
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div>
      <Title level={3}>Возвраты по моим товарам</Title>
      <Card>
        <Table
          dataSource={returns}
          rowKey="id"
          columns={[
            { title: '№', dataIndex: 'id', width: 60 },
            { title: 'Дата', dataIndex: 'created_at', render: (v) => dayjs(v).format('DD.MM.YYYY') },
            { title: 'Кол-во', dataIndex: 'quantity', width: 70 },
            { title: 'Причина', dataIndex: 'reason' },
            { title: 'Статус', dataIndex: 'status', render: (v) => <Tag color={statusLabels[v]?.color}>{statusLabels[v]?.label}</Tag> },
            {
              title: 'Действия', render: (_, r) => (
                ['requested', 'approved', 'in_transit'].includes(r.status) ? (
                  <Space wrap>
                    {r.status === 'requested' && (
                      <>
                        <Button size="small" type="primary" onClick={() => setModal({ open: true, ret: r, action: 'approved' })}>Одобрить</Button>
                        <Button size="small" danger onClick={() => setModal({ open: true, ret: r, action: 'rejected' })}>Отклонить</Button>
                      </>
                    )}
                    <Button size="small" style={{ background: '#52c41a', color: '#fff' }} onClick={() => setModal({ open: true, ret: r, action: 'refunded' })}>Вернуть деньги</Button>
                  </Space>
                ) : '—'
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="Обработка возврата" open={modal.open}
        onCancel={() => setModal({ open: false })} onOk={handleProcess}
      >
        <Input.TextArea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Комментарий покупателю" style={{ marginBottom: 12 }} />
        {modal.action === 'refunded' && (
          <InputNumber
            style={{ width: '100%' }} min={0} value={refundAmount} onChange={(v) => setRefundAmount(v ?? undefined)}
            placeholder="Сумма возврата (пусто = по цене × кол-во)"
          />
        )}
      </Modal>
    </div>
  )
}
