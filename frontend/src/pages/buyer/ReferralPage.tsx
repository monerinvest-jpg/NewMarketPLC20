import { useEffect, useState } from 'react'
import {
  Card, Typography, Statistic, Row, Col, Input, Button, message, Alert, Spin,
  Form, Select, InputNumber, Table, Tag, Divider,
} from 'antd'
import { CopyOutlined, BankOutlined, WalletOutlined } from '@ant-design/icons'
import { usersApi } from '@/api'
import type { ReferralStats } from '@/types'

const { Title, Text, Paragraph } = Typography

const statusMeta: Record<string, { label: string; color: string }> = {
  pending: { label: 'На рассмотрении', color: 'orange' },
  approved: { label: 'Одобрено', color: 'blue' },
  paid: { label: 'Выплачено', color: 'green' },
  rejected: { label: 'Отклонено', color: 'red' },
}

type Withdrawal = { id: number; amount: string; status: string; created_at: string; admin_comment?: string }

export default function ReferralPage() {
  const [stats, setStats] = useState<ReferralStats | null>(null)
  const [referralBalance, setReferralBalance] = useState(0)
  const [hasAccount, setHasAccount] = useState(false)
  const [withdrawals, setWithdrawals] = useState<Withdrawal[]>([])
  const [loading, setLoading] = useState(true)
  const [amount, setAmount] = useState<number>(0)
  const [acctForm] = Form.useForm()

  const loadAll = async () => {
    const [s, acc, w] = await Promise.all([
      usersApi.getReferralStats(),
      usersApi.getWithdrawalAccount(),
      usersApi.listReferralWithdrawals(),
    ])
    setStats(s)
    setReferralBalance(parseFloat(acc.referral_balance))
    setHasAccount(!!acc.account)
    if (acc.account) acctForm.setFieldsValue(acc.account)
    setWithdrawals(w)
  }

  useEffect(() => { loadAll().finally(() => setLoading(false)) }, [])

  const saveAccount = async (v: any) => {
    try {
      await usersApi.setWithdrawalAccount(v)
      message.success('Реквизиты сохранены')
      loadAll()
    } catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
  }

  const withdraw = async () => {
    if (amount <= 0) { message.error('Укажите сумму'); return }
    try {
      await usersApi.requestReferralWithdrawal(amount)
      message.success('Заявка на вывод создана')
      setAmount(0)
      loadAll()
    } catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (!stats) return null

  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      <Title level={3}>Реферальная программа</Title>
      <Paragraph type="secondary">
        Приглашённые привязываются к вам навсегда. Вы получаете процент со <b>всех</b> их покупок и продаж —
        пожизненно. Реферальные деньги можно вывести на счёт или оплатить ими до 100% заказа.
      </Paragraph>

      <Card style={{ marginBottom: 24, background: 'linear-gradient(135deg, #fff7ed, #ffedd5)' }}>
        <Text strong>Ваша реферальная ссылка:</Text>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <Input value={stats.referral_link} readOnly size="large" />
          <Button type="primary" icon={<CopyOutlined />} size="large"
            onClick={() => { navigator.clipboard.writeText(stats.referral_link); message.success('Ссылка скопирована!') }}>
            Скопировать
          </Button>
        </div>
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          Код: <Text strong copyable>{stats.referral_code}</Text>
        </Text>
      </Card>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}><Card><Statistic title="Приглашено" value={stats.total_referred} /></Card></Col>
        <Col span={8}><Card><Statistic title="Реферальный баланс" value={referralBalance} precision={2} suffix="₽" valueStyle={{ color: '#16a34a' }} /></Card></Col>
        <Col span={8}><Card><Statistic title="Бонусные баллы" value={parseFloat(stats.bonus_balance)} suffix="₽" /></Card></Col>
      </Row>

      <Card title={<span><WalletOutlined /> Вывод реферальных средств</span>} style={{ marginBottom: 24 }}>
        <Alert type="info" showIcon style={{ marginBottom: 16 }}
          message="Вывести деньги на счёт можно при наличии налогового статуса: самозанятый, ИП или ООО." />

        <Divider orientation="left" plain><BankOutlined /> Реквизиты для вывода</Divider>
        <Form form={acctForm} layout="vertical" onFinish={saveAccount}>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="tax_regime" label="Налоговый статус" rules={[{ required: true }]}>
                <Select options={[
                  { value: 'self_employed', label: 'Самозанятый' },
                  { value: 'individual', label: 'ИП' },
                  { value: 'company', label: 'ООО' },
                ]} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="inn" label="ИНН" rules={[{ required: true }]}><Input /></Form.Item>
            </Col>
          </Row>
          <Form.Item name="legal_name" label="ФИО / Наименование" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="account_details" label="Реквизиты счёта / карты" rules={[{ required: true }]}>
            <Input.TextArea rows={2} placeholder="Номер счёта, БИК банка или номер карты" />
          </Form.Item>
          <Button htmlType="submit">Сохранить реквизиты</Button>
        </Form>

        <Divider orientation="left" plain>Заявка на вывод</Divider>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <InputNumber min={0} max={referralBalance} value={amount} onChange={(v) => setAmount(Number(v) || 0)}
            addonAfter="₽" style={{ width: 200 }} />
          <Button type="primary" disabled={!hasAccount || amount <= 0 || amount > referralBalance} onClick={withdraw}>
            Вывести
          </Button>
          {!hasAccount && <Text type="warning">Сначала сохраните реквизиты</Text>}
        </div>

        {withdrawals.length > 0 && (
          <Table
            style={{ marginTop: 16 }} size="small" rowKey="id" pagination={false}
            dataSource={withdrawals}
            columns={[
              { title: 'Сумма', dataIndex: 'amount', render: (v) => `${parseFloat(v).toLocaleString('ru')} ₽` },
              { title: 'Статус', dataIndex: 'status', render: (s) => <Tag color={statusMeta[s]?.color}>{statusMeta[s]?.label || s}</Tag> },
              { title: 'Дата', dataIndex: 'created_at', render: (d) => new Date(d).toLocaleDateString('ru') },
              { title: 'Комментарий', dataIndex: 'admin_comment' },
            ]}
          />
        )}
      </Card>

      <Alert
        type="info" showIcon message="Как это работает"
        description={
          <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
            <li>Поделитесь ссылкой — приглашённый закрепляется за вами навсегда</li>
            <li>Друг-покупатель: вы получаете % с <b>каждой</b> его покупки (пожизненно)</li>
            <li>Друг-продавец: вы получаете % с <b>каждой</b> его продажи (пожизненно)</li>
            <li>Реферальными деньгами можно оплатить до 100% любого заказа</li>
            <li>Или вывести их на банковский счёт (с налоговым статусом)</li>
          </ul>
        }
      />
    </div>
  )
}
