import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, Card, Typography, message, Divider, Alert } from 'antd'
import { ShopOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/store/authStore'
import { mainOrigin } from '@/lib/sellerHost'

const { Title, Text } = Typography

const SELLER_ROLES = ['seller', 'superadmin']

// Login screen for the seller cabinet (seller.<domain>). Same credentials as
// the main site, but a buyer/staff account that is not a seller is rejected
// here so the cabinet stays seller-only.
export default function SellerLoginPage() {
  const [loading, setLoading] = useState(false)
  const [denied, setDenied] = useState(false)
  const { login, logout } = useAuthStore()
  const navigate = useNavigate()

  const onFinish = async (values: { email: string; password: string }) => {
    setLoading(true)
    setDenied(false)
    try {
      await login(values.email, values.password)
      const role = useAuthStore.getState().user?.role
      if (!role || !SELLER_ROLES.includes(role)) {
        logout()
        setDenied(true)
        return
      }
      message.success('Добро пожаловать в кабинет продавца!')
      navigate('/')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Неверный email или пароль')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <Card style={{ width: 400, maxWidth: '100%' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 34 }}>🪵</div>
          <Title level={3} style={{ margin: '8px 0 0' }}>
            <ShopOutlined /> Кабинет продавца
          </Title>
          <Text type="secondary">Вход для продавцов маркетплейса</Text>
        </div>

        {denied && (
          <Alert
            type="warning" showIcon style={{ marginBottom: 16 }}
            message="Это не аккаунт продавца"
            description="Войти в кабинет продавца можно только под учётной записью продавца. Откройте магазин на витрине, чтобы стать продавцом."
          />
        )}

        <Form layout="vertical" onFinish={onFinish} requiredMark={false}>
          <Form.Item name="email" label="Email" rules={[{ required: true, type: 'email' }]}>
            <Input size="large" placeholder="you@example.com" />
          </Form.Item>
          <Form.Item name="password" label="Пароль" rules={[{ required: true }]}>
            <Input.Password size="large" placeholder="••••••••" />
          </Form.Item>
          <div style={{ textAlign: 'right', marginBottom: 16 }}>
            <a href={mainOrigin() + '/forgot-password'}>Забыли пароль?</a>
          </div>
          <Button type="primary" htmlType="submit" size="large" block loading={loading}>
            Войти как продавец
          </Button>
        </Form>
        <Divider />
        <Text type="secondary">
          Ещё не продаёте у нас? <a href={mainOrigin() + '/'}>Открыть магазин на витрине</a>
        </Text>
      </Card>
    </div>
  )
}
