import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Form, Input, Button, Card, Typography, message, Select, Divider } from 'antd'
import { authApi } from '@/api'

const { Title, Text } = Typography

export default function RegisterPage() {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const refCode = searchParams.get('ref') || ''

  const onFinish = async (values: any) => {
    setLoading(true)
    try {
      await authApi.register({
        email: values.email,
        password: values.password,
        full_name: values.full_name,
        phone: values.phone,
        role: values.role,
        referral_code: values.referral_code || undefined,
      })
      message.success('Аккаунт создан! Подтвердите email — мы отправили код на почту.')
      navigate(`/verify-email?email=${encodeURIComponent(values.email)}`)
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка регистрации')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 460, margin: '40px auto' }}>
      <Card>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 24 }}>
          Регистрация
        </Title>
        <Form
          layout="vertical"
          onFinish={onFinish}
          requiredMark={false}
          initialValues={{ role: 'buyer', referral_code: refCode }}
        >
          <Form.Item name="full_name" label="Имя и фамилия" rules={[{ required: true, min: 2 }]}>
            <Input size="large" placeholder="Иван Иванов" />
          </Form.Item>
          <Form.Item name="email" label="Email" rules={[{ required: true, type: 'email' }]}>
            <Input size="large" placeholder="you@example.com" />
          </Form.Item>
          <Form.Item name="phone" label="Телефон">
            <Input size="large" placeholder="+7 900 000 00 00" />
          </Form.Item>
          <Form.Item name="password" label="Пароль" rules={[{ required: true, min: 6 }]}>
            <Input.Password size="large" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="Повторите пароль"
            dependencies={['password']}
            rules={[
              { required: true },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) return Promise.resolve()
                  return Promise.reject('Пароли не совпадают')
                },
              }),
            ]}
          >
            <Input.Password size="large" />
          </Form.Item>
          <Form.Item name="role" label="Тип аккаунта">
            <Select size="large" options={[
              { value: 'buyer', label: '🛒 Покупатель' },
              { value: 'seller', label: '🏪 Продавец' },
            ]} />
          </Form.Item>
          <Form.Item name="referral_code" label="Реферальный код (необязательно)">
            <Input size="large" placeholder="Код пригласившего" />
          </Form.Item>
          <Button type="primary" htmlType="submit" size="large" block loading={loading}>
            Создать аккаунт
          </Button>
        </Form>
        <Divider />
        <Text type="secondary">
          Уже есть аккаунт? <Link to="/login">Войти</Link>
        </Text>
      </Card>
    </div>
  )
}
