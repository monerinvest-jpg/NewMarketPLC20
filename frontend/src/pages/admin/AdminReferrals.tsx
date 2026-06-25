import { useEffect, useState } from 'react'
import { Table, Tag, Typography, Button, Modal, Form, InputNumber, Switch, message } from 'antd'
import { adminApi } from '@/api'
import type { Referral } from '@/types'
import dayjs from 'dayjs'

const { Title } = Typography

export default function AdminReferrals() {
  const [referrals, setReferrals] = useState<Referral[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [bonusModal, setBonusModal] = useState(false)
  const [form] = Form.useForm()

  const load = () => {
    setLoading(true)
    adminApi.listReferrals({ page }).then((res) => {
      setReferrals(res.items); setTotal(res.total)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page])

  const handleManualBonus = async (values: { user_id: number; amount: number; is_cash: boolean }) => {
    try {
      await adminApi.manualBonus(values.user_id, values.amount, values.is_cash)
      message.success('Бонус начислен')
      setBonusModal(false)
      form.resetFields()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Реферальная программа</Title>
        <Button type="primary" onClick={() => setBonusModal(true)}>Ручное начисление</Button>
      </div>

      <Table
        loading={loading}
        dataSource={referrals}
        rowKey="id"
        pagination={{ current: page, total, pageSize: 20, onChange: setPage, showSizeChanger: false }}
        columns={[
          { title: '№', dataIndex: 'id', width: 60 },
          { title: 'Дата', dataIndex: 'created_at', render: (v) => dayjs(v).format('DD.MM.YYYY') },
          { title: 'Пригласивший ID', dataIndex: 'referrer_id' },
          { title: 'Приглашённый ID', dataIndex: 'referred_user_id' },
          { title: 'Тип', dataIndex: 'type', render: (t) => <Tag color={t === 'buyer' ? 'blue' : 'purple'}>{t === 'buyer' ? 'Покупатель' : 'Продавец'}</Tag> },
          {
            title: 'Награда выплачена', dataIndex: 'reward_paid',
            render: (v) => v ? <Tag color="green">Да</Tag> : <Tag color="orange">Ожидание</Tag>,
          },
        ]}
      />

      <Modal
        title="Ручное начисление бонуса" open={bonusModal}
        onCancel={() => setBonusModal(false)} onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleManualBonus}>
          <Form.Item name="user_id" label="ID пользователя" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="amount" label="Сумма, ₽" rules={[{ required: true }]}>
            <InputNumber min={0.01} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_cash" label="Денежный баланс (для продавца)" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
