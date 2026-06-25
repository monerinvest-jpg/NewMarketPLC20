import { useEffect, useState } from 'react'
import {
  Card, Typography, Form, Input, Switch, Button, message, Row, Col, Statistic,
  Tabs, Table, Tag, Alert, Spin, Divider, Space, Tooltip, Empty
} from 'antd'
import { ReloadOutlined, SendOutlined, MessageOutlined } from '@ant-design/icons'
import { adminApi } from '@/api'
import dayjs from 'dayjs'

const { Title, Text } = Typography

const purposeLabels: Record<string, string> = {
  phone_verification: 'Подтверждение телефона',
  order_status: 'Статус заказа',
  test: 'Тест',
  manual: 'Вручную',
}

export default function AdminSms() {
  const [status, setStatus] = useState<any>(null)
  const [stats, setStats] = useState<any>(null)
  const [log, setLog] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [savingSettings, setSavingSettings] = useState(false)
  const [balanceLoading, setBalanceLoading] = useState(false)
  const [testPhone, setTestPhone] = useState('')
  const [testText, setTestText] = useState('')
  const [testing, setTesting] = useState(false)
  const [logPage, setLogPage] = useState(1)
  const [form] = Form.useForm()

  const loadStatus = async () => {
    const s = await adminApi.smsStatus()
    setStatus(s)
    form.setFieldsValue({
      sms_enabled: s.enabled,
      smsc_login: s.login,
      smsc_sender: s.sender,
      smsc_use_apikey: s.use_apikey,
      sms_notify_order_status: s.notify_order_status,
      sms_notify_phone_verification: s.notify_phone_verification,
      smsc_password: s.has_password ? '********' : '',
    })
  }

  const load = async () => {
    setLoading(true)
    try {
      await Promise.all([
        loadStatus(),
        adminApi.smsStats(30).then(setStats).catch(() => {}),
      ])
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [])

  useEffect(() => {
    adminApi.smsLog({ page: logPage }).then(setLog).catch(() => {})
  }, [logPage])

  const saveSettings = async (values: any) => {
    setSavingSettings(true)
    try {
      await adminApi.smsUpdateSettings(values)
      message.success('Настройки SMS сохранены')
      await loadStatus()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    } finally {
      setSavingSettings(false)
    }
  }

  const refreshBalance = async () => {
    setBalanceLoading(true)
    try {
      const b = await adminApi.smsBalance()
      setStatus((s: any) => ({ ...s, balance: b }))
      if (!b.ok) message.warning(b.error || 'Не удалось получить баланс')
    } finally {
      setBalanceLoading(false)
    }
  }

  const sendTest = async () => {
    if (!testPhone) { message.warning('Введите номер'); return }
    setTesting(true)
    try {
      const r = await adminApi.smsTest(testPhone, testText || undefined)
      if (r.ok) {
        message.success(`Отправлено! ID: ${r.smsc_id}, стоимость: ${r.cost ?? '—'}, баланс: ${r.balance ?? '—'}`)
      } else {
        message.error(r.error || 'Не удалось отправить')
      }
      adminApi.smsLog({ page: 1 }).then(setLog).catch(() => {})
    } finally {
      setTesting(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  const balance = status?.balance

  return (
    <div>
      <Title level={3}><MessageOutlined /> SMS (SMSC.ru)</Title>
      <Text type="secondary">Интеграция SMS-рассылок. По умолчанию выключено — включайте после ввода учётных данных.</Text>

      {!status?.enabled && (
        <Alert type="warning" showIcon style={{ marginTop: 12, marginBottom: 12 }}
          message="SMS-функции выключены" description="Пока выключено, коды подтверждения по телефону и SMS-уведомления не отправляются." />
      )}

      {/* Balance + stats cards */}
      <Row gutter={16} style={{ margin: '16px 0' }}>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="Баланс SMSC"
              value={balance?.ok ? balance.balance : undefined}
              suffix={balance?.ok ? (balance.currency || 'RUB') : ''}
              valueStyle={{ color: balance?.ok ? '#237804' : '#999' }}
              formatter={balance?.ok ? undefined : () => '—'}
            />
            <Button size="small" icon={<ReloadOutlined />} loading={balanceLoading} onClick={refreshBalance} style={{ marginTop: 8 }}>
              Обновить
            </Button>
          </Card>
        </Col>
        <Col xs={24} sm={6}><Card><Statistic title="Отправлено (30 дн)" value={stats?.sent ?? 0} /></Card></Col>
        <Col xs={24} sm={6}><Card><Statistic title="Успешность" value={stats?.success_rate ?? 0} suffix="%" /></Card></Col>
        <Col xs={24} sm={6}><Card><Statistic title="Расход (30 дн)" value={stats?.total_cost ?? 0} suffix="₽" /></Card></Col>
      </Row>

      <Tabs
        defaultActiveKey="settings"
        items={[
          {
            key: 'settings', label: 'Настройки',
            children: (
              <Card>
                <Form form={form} layout="vertical" onFinish={saveSettings}>
                  <Form.Item name="sms_enabled" label="SMS включены" valuePropName="checked" extra="Главный выключатель всех SMS-функций">
                    <Switch checkedChildren="ВКЛ" unCheckedChildren="ВЫКЛ" />
                  </Form.Item>
                  <Divider />
                  <Form.Item name="smsc_use_apikey" label="Использовать API-ключ вместо логина/пароля" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                  <Row gutter={16}>
                    <Col xs={24} sm={12}>
                      <Form.Item name="smsc_login" label="Логин SMSC">
                        <Input placeholder="Логин аккаунта" autoComplete="off" />
                      </Form.Item>
                    </Col>
                    <Col xs={24} sm={12}>
                      <Form.Item name="smsc_password" label="Пароль / API-ключ" extra="Оставьте ******** без изменений, чтобы не менять">
                        <Input.Password placeholder="Пароль или apikey" autoComplete="new-password" />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Form.Item name="smsc_sender" label="Имя отправителя (Sender ID)" extra="Должно быть зарегистрировано в SMSC.ru">
                    <Input placeholder="Напр. MyShop" />
                  </Form.Item>
                  <Divider>Какие SMS отправлять</Divider>
                  <Form.Item name="sms_notify_phone_verification" label="Коды подтверждения телефона" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                  <Form.Item name="sms_notify_order_status" label="Уведомления о статусе заказа" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={savingSettings}>Сохранить настройки</Button>
                </Form>
              </Card>
            ),
          },
          {
            key: 'test', label: 'Тест отправки',
            children: (
              <Card>
                <Alert type="info" showIcon style={{ marginBottom: 16 }}
                  message="Тест работает даже при выключенных SMS — чтобы проверить учётные данные." />
                <Space direction="vertical" style={{ width: '100%', maxWidth: 480 }}>
                  <Input placeholder="Номер телефона (79991234567)" value={testPhone} onChange={(e) => setTestPhone(e.target.value)} />
                  <Input.TextArea rows={2} placeholder="Текст (по умолчанию — тестовое сообщение)" value={testText} onChange={(e) => setTestText(e.target.value)} />
                  <Button type="primary" icon={<SendOutlined />} loading={testing} onClick={sendTest}>Отправить тест</Button>
                </Space>
              </Card>
            ),
          },
          {
            key: 'stats', label: 'Статистика',
            children: (
              <Card>
                {!stats ? <Empty /> : (
                  <>
                    <Row gutter={16} style={{ marginBottom: 16 }}>
                      <Col xs={12} sm={6}><Statistic title="Всего" value={stats.total} /></Col>
                      <Col xs={12} sm={6}><Statistic title="Доставлено" value={stats.sent} valueStyle={{ color: '#237804' }} /></Col>
                      <Col xs={12} sm={6}><Statistic title="Ошибок" value={stats.failed} valueStyle={{ color: '#cf1322' }} /></Col>
                      <Col xs={12} sm={6}><Statistic title="Сегментов" value={stats.total_segments} /></Col>
                    </Row>
                    <Table
                      title={() => 'По типам сообщений'}
                      dataSource={Object.entries(stats.by_purpose || {}).map(([k, v]: any) => ({ key: k, purpose: k, ...v }))}
                      rowKey="key"
                      pagination={false}
                      columns={[
                        { title: 'Тип', dataIndex: 'purpose', render: (v) => purposeLabels[v] || v },
                        { title: 'Отправлено', dataIndex: 'sent' },
                        { title: 'Ошибок', dataIndex: 'failed' },
                        { title: 'Расход', dataIndex: 'cost', render: (v) => `${(v || 0).toFixed(2)} ₽` },
                      ]}
                    />
                  </>
                )}
              </Card>
            ),
          },
          {
            key: 'log', label: 'Журнал',
            children: (
              <Card>
                <Table
                  dataSource={log?.items || []}
                  rowKey="id"
                  pagination={{ current: logPage, total: log?.total || 0, pageSize: 50, onChange: setLogPage }}
                  columns={[
                    { title: 'Время', dataIndex: 'created_at', render: (v) => dayjs(v).format('DD.MM.YY HH:mm') },
                    { title: 'Телефон', dataIndex: 'phone' },
                    { title: 'Тип', dataIndex: 'purpose', render: (v) => purposeLabels[v] || v },
                    {
                      title: 'Статус', dataIndex: 'status',
                      render: (v) => v === 'sent' ? <Tag color="green">Отправлено</Tag> : <Tag color="red">Ошибка</Tag>,
                    },
                    { title: 'Стоимость', dataIndex: 'cost', render: (v) => v != null ? `${v} ₽` : '—' },
                    {
                      title: 'Детали', render: (_: any, r: any) => r.error
                        ? <Tooltip title={r.error}><Text type="danger" ellipsis style={{ maxWidth: 200 }}>{r.error}</Text></Tooltip>
                        : <Text type="secondary" ellipsis style={{ maxWidth: 200 }}>{r.text_preview}</Text>,
                    },
                  ]}
                />
              </Card>
            ),
          },
        ]}
      />
    </div>
  )
}
