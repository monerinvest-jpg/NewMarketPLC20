import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Form, Input, Button, Card, Typography, message, Result, Alert } from 'antd'
import { authApi } from '@/api'

const { Title } = Typography

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const navigate = useNavigate()

  const onFinish = async (values: { password: string }) => {
    setLoading(true)
    try {
      await authApi.resetPassword(token, values.password)
      setDone(true)
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ссылка недействительна или устарела')
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div style={{ maxWidth: 440, margin: '60px auto' }}>
        <Alert
          type="error" showIcon message="Некорректная ссылка"
          description="В ссылке отсутствует токен восстановления. Запросите восстановление пароля заново."
        />
        <Link to="/forgot-password"><Button type="primary" style={{ marginTop: 16 }}>Запросить заново</Button></Link>
      </div>
    )
  }

  if (done) {
    return (
      <div style={{ maxWidth: 440, margin: '60px auto' }}>
        <Card>
          <Result
            status="success"
            title="Пароль изменён"
            subTitle="Теперь вы можете войти с новым паролем"
            extra={<Button type="primary" onClick={() => navigate('/login')}>Войти</Button>}
          />
        </Card>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 400, margin: '60px auto' }}>
      <Card>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 24 }}>
          Новый пароль
        </Title>
        <Form layout="vertical" onFinish={onFinish} requiredMark={false}>
          <Form.Item name="password" label="Новый пароль" rules={[{ required: true, min: 6 }]}>
            <Input.Password size="large" />
          </Form.Item>
          <Form.Item
            name="confirm" label="Повторите пароль" dependencies={['password']}
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
          <Button type="primary" htmlType="submit" size="large" block loading={loading}>
            Сохранить новый пароль
          </Button>
        </Form>
      </Card>
    </div>
  )
}
