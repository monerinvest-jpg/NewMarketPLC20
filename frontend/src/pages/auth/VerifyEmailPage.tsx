import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { Card, Typography, Input, Button, message, Result } from 'antd'
import { MailOutlined } from '@ant-design/icons'
import { authApi } from '@/api'

const { Title, Text } = Typography

export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [email, setEmail] = useState(params.get('email') || '')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [verified, setVerified] = useState(false)
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown(cooldown - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  const submit = async () => {
    if (!email || code.length < 4) { message.warning('Введите email и код'); return }
    setLoading(true)
    try {
      await authApi.verifyEmail(email, code)
      setVerified(true)
      message.success('Email подтверждён!')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Не удалось подтвердить')
    } finally {
      setLoading(false)
    }
  }

  const resend = async () => {
    if (!email) { message.warning('Введите email'); return }
    try {
      await authApi.resendCode(email)
      message.success('Новый код отправлен на email')
      setCooldown(30)
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  if (verified) {
    return (
      <div style={{ maxWidth: 480, margin: '60px auto' }}>
        <Card>
          <Result
            status="success"
            title="Email подтверждён"
            subTitle="Теперь вы можете войти в аккаунт."
            extra={<Button type="primary" onClick={() => navigate('/login')}>Войти</Button>}
          />
        </Card>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 480, margin: '60px auto' }}>
      <Card>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <MailOutlined style={{ fontSize: 48, color: '#b45309' }} />
          <Title level={3} style={{ marginTop: 16 }}>Подтверждение email</Title>
          <Text type="secondary">
            Мы отправили 6-значный код на вашу почту. Введите его ниже.
          </Text>
        </div>

        <Input
          size="large"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={{ marginBottom: 12 }}
          disabled={!!params.get('email')}
        />
        <Input
          size="large"
          placeholder="Код из письма"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          maxLength={6}
          style={{ marginBottom: 16, textAlign: 'center', letterSpacing: 8, fontSize: 20 }}
          onPressEnter={submit}
        />
        <Button type="primary" size="large" block loading={loading} onClick={submit}>
          Подтвердить
        </Button>

        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Button type="link" disabled={cooldown > 0} onClick={resend}>
            {cooldown > 0 ? `Отправить код повторно (${cooldown})` : 'Отправить код повторно'}
          </Button>
        </div>
        <div style={{ textAlign: 'center', marginTop: 8 }}>
          <Link to="/login">Вернуться ко входу</Link>
        </div>
      </Card>
    </div>
  )
}
