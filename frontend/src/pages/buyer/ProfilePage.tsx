import { useState } from 'react'
import { Card, Form, Input, Button, Typography, message, Descriptions, Tag, Divider, List, Modal } from 'antd'
import { useAuthStore } from '@/store/authStore'
import { usersApi } from '@/api'
import { useEffect } from 'react'

const { Title, Text } = Typography

const roleLabels: Record<string, string> = {
  buyer: 'Покупатель', seller: 'Продавец', moderator: 'Модератор', superadmin: 'Супер-администратор',
}

export default function ProfilePage() {
  const { user, fetchMe } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()
  const [balanceHistory, setBalanceHistory] = useState<any[]>([])
  const [phoneModal, setPhoneModal] = useState(false)
  const [phoneCode, setPhoneCode] = useState('')
  const [phoneSending, setPhoneSending] = useState(false)

  useEffect(() => {
    usersApi.getBalanceHistory().then(setBalanceHistory).catch(() => {})
  }, [])

  if (!user) return null

  const startPhoneVerify = async () => {
    try {
      const { authApi } = await import('@/api')
      await authApi.sendPhoneCode()
      setPhoneModal(true)
      message.success('Код отправлен по SMS')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'SMS-подтверждение недоступно')
    }
  }

  const confirmPhone = async () => {
    setPhoneSending(true)
    try {
      const { authApi } = await import('@/api')
      await authApi.verifyPhone(phoneCode)
      await fetchMe()
      message.success('Телефон подтверждён')
      setPhoneModal(false); setPhoneCode('')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Неверный код')
    } finally {
      setPhoneSending(false)
    }
  }

  const onFinish = async (values: any) => {
    setLoading(true)
    try {
      await usersApi.updateProfile({
        full_name: values.full_name,
        phone: values.phone,
        password: values.password || undefined,
      })
      await fetchMe()
      message.success('Профиль обновлён')
      form.setFieldValue('password', '')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 700, margin: '0 auto' }}>
      <Title level={3}>Профиль</Title>

      <Card style={{ marginBottom: 24 }}>
        <Descriptions column={1}>
          <Descriptions.Item label="Email">
            {user.email}{' '}
            {user.email_verified
              ? <Tag color="green">подтверждён</Tag>
              : <Tag color="orange">не подтверждён</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="Телефон">
            {user.phone || '—'}{' '}
            {user.phone && (user.phone_verified
              ? <Tag color="green">подтверждён</Tag>
              : <Button size="small" type="link" onClick={startPhoneVerify}>Подтвердить по SMS</Button>)}
          </Descriptions.Item>
          <Descriptions.Item label="Роль"><Tag color="blue">{roleLabels[user.role]}</Tag></Descriptions.Item>
          <Descriptions.Item label="Реферальный код">
            <Text copyable>{user.referral_code}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="Баланс бонусов">
            <Text strong style={{ color: '#52c41a' }}>{parseFloat(user.bonus_balance).toLocaleString('ru')} ₽</Text>
          </Descriptions.Item>
          {user.role === 'seller' && (
            <Descriptions.Item label="Баланс продавца">
              <Text strong style={{ color: '#b45309' }}>{parseFloat(user.balance).toLocaleString('ru')} ₽</Text>
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Card title="Редактировать профиль" style={{ marginBottom: 24 }}>
        <Form
          form={form} layout="vertical" onFinish={onFinish}
          initialValues={{ full_name: user.full_name, phone: user.phone }}
        >
          <Form.Item name="full_name" label="Имя и фамилия" rules={[{ required: true }]}>
            <Input size="large" />
          </Form.Item>
          <Form.Item name="phone" label="Телефон">
            <Input size="large" />
          </Form.Item>
          <Form.Item name="password" label="Новый пароль (оставьте пустым, чтобы не менять)">
            <Input.Password size="large" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading}>Сохранить</Button>
        </Form>
      </Card>

      {balanceHistory.length > 0 && (
        <Card title="История операций">
          <List
            dataSource={balanceHistory}
            renderItem={(tx: any) => (
              <List.Item>
                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                  <Text>{tx.description}</Text>
                  <Text strong style={{ color: tx.change > 0 ? '#52c41a' : '#ff4d4f' }}>
                    {tx.change > 0 ? '+' : ''}{tx.change} ₽
                  </Text>
                </div>
              </List.Item>
            )}
          />
        </Card>
      )}

      <Modal
        title="Подтверждение телефона"
        open={phoneModal}
        onCancel={() => setPhoneModal(false)}
        onOk={confirmPhone}
        confirmLoading={phoneSending}
        okText="Подтвердить"
      >
        <Text type="secondary">Введите код из SMS, отправленного на {user.phone}.</Text>
        <Input
          style={{ marginTop: 12, textAlign: 'center', letterSpacing: 8, fontSize: 20 }}
          value={phoneCode}
          onChange={(e) => setPhoneCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          maxLength={6}
          placeholder="______"
        />
      </Modal>
    </div>
  )
}
