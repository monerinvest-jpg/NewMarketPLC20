import { useEffect, useState } from 'react'
import {
  Card, Row, Col, Typography, Button, Tag, message, Spin,
  Alert, Radio, Modal, Statistic, Divider
} from 'antd'
import { CheckCircleOutlined } from '@ant-design/icons'
import { subscriptionApi } from '@/api'
import type { SellerPlan, SellerSubscription } from '@/types'
import { useAuthStore } from '@/store/authStore'
import dayjs from 'dayjs'

const { Title, Text, Paragraph } = Typography

export default function SellerPlanPage() {
  const { user } = useAuthStore()
  const [plans, setPlans] = useState<SellerPlan[]>([])
  const [subscription, setSubscription] = useState<SellerSubscription | null>(null)
  const [enabled, setEnabled] = useState(true)
  const [loading, setLoading] = useState(true)
  const [payModal, setPayModal] = useState<{ open: boolean; plan?: SellerPlan }>({ open: false })
  const [payMethod, setPayMethod] = useState<'balance' | 'yookassa'>('balance')
  const [submitting, setSubmitting] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const status = await subscriptionApi.status()
      setEnabled(status.paid_placement_enabled)
      if (status.paid_placement_enabled) {
        const [p, s] = await Promise.all([subscriptionApi.plans(), subscriptionApi.me()])
        setPlans(p)
        setSubscription(s)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleChoose = (plan: SellerPlan) => {
    const price = parseFloat(plan.monthly_price)
    // Free plan or available trial → subscribe directly without payment dialog
    if (price === 0 || (plan.trial_days > 0 && !subscription?.trial_used)) {
      doSubscribe(plan, true)
    } else {
      setPayMethod('balance')
      setPayModal({ open: true, plan })
    }
  }

  const doSubscribe = async (plan: SellerPlan, payFromBalance: boolean) => {
    setSubmitting(true)
    try {
      const result = await subscriptionApi.subscribe(plan.id, payFromBalance)
      if (result.status === 'needs_payment' && result.confirmation_url) {
        window.location.href = result.confirmation_url
        return
      }
      if (result.status === 'trial') {
        message.success(`Подключён пробный период плана «${plan.name}»`)
      } else {
        message.success(`Тариф «${plan.name}» активирован`)
      }
      setPayModal({ open: false })
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  if (!enabled) {
    return (
      <Alert
        type="info" showIcon
        message="Платное размещение отключено"
        description="Сейчас все продавцы используют единую комиссию платформы. Тарифные планы недоступны."
      />
    )
  }

  return (
    <div>
      <Title level={3}>Тариф и комиссия</Title>
      <Paragraph type="secondary">
        Выберите тариф: бесплатное размещение с повышенной комиссией, либо платный тариф со сниженной комиссией.
      </Paragraph>

      {subscription && (
        <Alert
          type="success" showIcon style={{ marginBottom: 24 }}
          message={`Ваш текущий тариф: ${subscription.plan.name} (${subscription.status === 'trial' ? 'пробный период' : 'активен'})`}
          description={
            <>
              Комиссия: <b>{subscription.plan.commission_percent}%</b>
              {subscription.current_period_end && (
                <> · действует до {dayjs(subscription.current_period_end).format('DD.MM.YYYY')}</>
              )}
              <> · ваш баланс: <b>{parseFloat(user?.balance || '0').toLocaleString('ru')} ₽</b></>
            </>
          }
        />
      )}

      <Row gutter={16}>
        {plans.map((plan) => {
          const isCurrent = subscription?.plan_id === plan.id
          const price = parseFloat(plan.monthly_price)
          return (
            <Col key={plan.id} xs={24} md={8}>
              <Card
                style={{
                  marginBottom: 16,
                  border: isCurrent ? '2px solid #f97316' : undefined,
                  height: '100%',
                }}
              >
                {isCurrent && <Tag color="orange" style={{ marginBottom: 8 }}>Текущий</Tag>}
                <Title level={4} style={{ margin: 0 }}>{plan.name}</Title>
                <div style={{ margin: '12px 0' }}>
                  <Statistic
                    value={price}
                    suffix="₽/мес"
                    valueStyle={{ color: price === 0 ? '#52c41a' : '#f97316' }}
                  />
                </div>
                <div style={{ marginBottom: 12 }}>
                  <Tag color="blue" style={{ fontSize: 14 }}>Комиссия {plan.commission_percent}%</Tag>
                  {plan.trial_days > 0 && (
                    <Tag color="green">{plan.trial_days} дн. бесплатно</Tag>
                  )}
                </div>
                <Paragraph type="secondary" style={{ minHeight: 44 }}>{plan.description}</Paragraph>
                <Button
                  type={isCurrent ? 'default' : 'primary'}
                  block
                  disabled={isCurrent}
                  onClick={() => handleChoose(plan)}
                >
                  {isCurrent ? 'Активен' : price === 0 ? 'Перейти бесплатно' : 'Выбрать'}
                </Button>
              </Card>
            </Col>
          )
        })}
      </Row>

      <Modal
        title={`Оплата тарифа «${payModal.plan?.name}»`}
        open={payModal.open}
        onCancel={() => setPayModal({ open: false })}
        onOk={() => payModal.plan && doSubscribe(payModal.plan, payMethod === 'balance')}
        confirmLoading={submitting}
        okText="Оплатить"
      >
        <p>
          Стоимость: <b>{parseFloat(payModal.plan?.monthly_price || '0').toLocaleString('ru')} ₽ / месяц</b>
        </p>
        <Divider />
        <Text strong>Способ оплаты:</Text>
        <Radio.Group
          value={payMethod}
          onChange={(e) => setPayMethod(e.target.value)}
          style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}
        >
          <Radio value="balance">
            С баланса магазина (доступно: {parseFloat(user?.balance || '0').toLocaleString('ru')} ₽)
          </Radio>
          <Radio value="yookassa">Картой через ЮKassa</Radio>
        </Radio.Group>
      </Modal>
    </div>
  )
}
