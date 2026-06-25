import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Form, Input, Button, Card, Typography, message, Result } from 'antd'
import { authApi } from '@/api'

const { Title, Text } = Typography

export default function ForgotPasswordPage() {
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const onFinish = async (values: { email: string }) => {
    setLoading(true)
    try {
      await authApi.forgotPassword(values.email)
      setSent(true)
    } catch {
      // Backend always returns success regardless of whether the email
      // exists, so a request error here means something else went wrong
      message.error('Не удалось отправить запрос. Попробуйте позже.')
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <div style={{ maxWidth: 440, margin: '60px auto' }}>
        <Card>
          <Result
            status="success"
            title="Проверьте почту"
            subTitle="Если такой email зарегистрирован, на него отправлена ссылка для восстановления пароля. Ссылка действительна 1 час."
            extra={<Link to="/login"><Button type="primary">Вернуться ко входу</Button></Link>}
          />
        </Card>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 400, margin: '60px auto' }}>
      <Card>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 8 }}>
          Восстановление пароля
        </Title>
        <Text type="secondary" style={{ display: 'block', textAlign: 'center', marginBottom: 24 }}>
          Введите email, указанный при регистрации
        </Text>
        <Form layout="vertical" onFinish={onFinish} requiredMark={false}>
          <Form.Item name="email" label="Email" rules={[{ required: true, type: 'email' }]}>
            <Input size="large" placeholder="you@example.com" />
          </Form.Item>
          <Button type="primary" htmlType="submit" size="large" block loading={loading}>
            Отправить ссылку
          </Button>
        </Form>
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Link to="/login">Вернуться ко входу</Link>
        </div>
      </Card>
    </div>
  )
}
