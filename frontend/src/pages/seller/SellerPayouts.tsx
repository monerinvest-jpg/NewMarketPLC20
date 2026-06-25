import { useEffect, useState } from 'react'
import { Card, Table, Button, Modal, Form, InputNumber, Input, Tag, message, Typography, Statistic, Alert } from 'antd'
import { sellerToolsApi } from '@/api'
import type { PayoutRequest } from '@/types'
import { useAuthStore } from '@/store/authStore'
import dayjs from 'dayjs'

const { Title } = Typography

const statusLabels: Record<string, { label: string; color: string }> = {
  pending: { label: 'На рассмотрении', color: 'orange' },
  approved: { label: 'Одобрен', color: 'blue' },
  rejected: { label: 'Отклонён', color: 'red' },
  paid: { label: 'Выплачен', color: 'green' },
}

export default function SellerPayouts() {
  const { user } = useAuthStore()
  const [payouts, setPayouts] = useState<PayoutRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const load = () => {
    setLoading(true)
    sellerToolsApi.listPayouts().then(setPayouts).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleSubmit = async (values: any) => {
    try {
      await sellerToolsApi.requestPayout(values.amount, values.payout_details)
      message.success('Запрос на вывод отправлен')
      setModalOpen(false)
      form.resetFields()
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const balance = parseFloat(user?.balance || '0')

  return (
    <div>
      <Title level={3}>Вывод средств</Title>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Statistic title="Доступно к выводу" value={balance} suffix="₽" valueStyle={{ color: '#f97316' }} />
          <Button type="primary" disabled={balance <= 0} onClick={() => setModalOpen(true)}>Запросить вывод</Button>
        </div>
      </Card>

      <Alert
        style={{ marginBottom: 16 }} type="info" showIcon
        message="Средства списываются с баланса только после того, как администратор отметит выплату как «Выплачен»."
      />

      <Card>
        <Table
          loading={loading}
          dataSource={payouts}
          rowKey="id"
          pagination={false}
          columns={[
            { title: '№', dataIndex: 'id', width: 60 },
            { title: 'Дата', dataIndex: 'created_at', render: (v) => dayjs(v).format('DD.MM.YYYY HH:mm') },
            { title: 'Сумма', dataIndex: 'amount', render: (v) => `${parseFloat(v).toLocaleString('ru')} ₽` },
            { title: 'Реквизиты', dataIndex: 'payout_details' },
            { title: 'Статус', dataIndex: 'status', render: (v) => <Tag color={statusLabels[v]?.color}>{statusLabels[v]?.label}</Tag> },
            { title: 'Комментарий', dataIndex: 'admin_comment', render: (v) => v || '—' },
          ]}
        />
      </Card>

      <Modal title="Запрос на вывод средств" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="amount" label={`Сумма (доступно: ${balance.toLocaleString('ru')} ₽)`} rules={[{ required: true }]}>
            <InputNumber min={1} max={balance} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="payout_details" label="Реквизиты для вывода" rules={[{ required: true }]}>
            <Input.TextArea rows={2} placeholder="Номер карты / счёта / телефон СБП" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
