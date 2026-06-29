import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Alert, Table, Row, Col, Statistic, Spin,
  Typography, Button, message, Space, Divider, Modal, Form, Input, Select,
  Switch, InputNumber, Checkbox, Tooltip,
} from 'antd'
import { WarningOutlined, EditOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { adminApi } from '@/api'
import { useAuthStore } from '@/store/authStore'

const { Title, Text } = Typography

const money = (v: any) => `${parseFloat(v || 0).toLocaleString('ru')} ₽`
const dt = (v: string) => new Date(v).toLocaleString('ru')

const roleOptions = [
  { value: 'buyer', label: 'Покупатель' },
  { value: 'seller', label: 'Продавец' },
  { value: 'support', label: 'Поддержка' },
  { value: 'moderator', label: 'Модератор' },
  { value: 'superadmin', label: 'Супер-админ' },
]

const balanceFields = [
  { value: 'balance', label: 'Баланс (продажи)' },
  { value: 'bonus_balance', label: 'Бонусы' },
  { value: 'referral_balance', label: 'Реферальный баланс' },
  { value: 'promo_balance', label: 'Промо-баланс' },
]

export default function AdminUserDetail() {
  const { id } = useParams()
  const me = useAuthStore((s) => s.user)
  const isSuperadmin = me?.role === 'superadmin'

  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const [editOpen, setEditOpen] = useState(false)
  const [editForm] = Form.useForm()
  const [saving, setSaving] = useState(false)

  // Permissions
  const [catalog, setCatalog] = useState<any>(null)
  const [perms, setPerms] = useState<string[]>([])
  const [savingPerms, setSavingPerms] = useState(false)

  // Balance adjust
  const [adjField, setAdjField] = useState('balance')
  const [adjAmount, setAdjAmount] = useState<number>(0)
  const [adjReason, setAdjReason] = useState('')

  const load = () => {
    setLoading(true)
    adminApi.userDetail(Number(id)).then(setData).finally(() => setLoading(false))
    if (isSuperadmin) {
      adminApi.permissionsCatalog().then(setCatalog).catch(() => {})
      adminApi.getUserPermissions(Number(id)).then((r) => setPerms(r.permissions || [])).catch(() => {})
    }
  }
  useEffect(() => { load() }, [id])

  const openEdit = () => {
    const u = data.user
    editForm.setFieldsValue({
      full_name: u.full_name, email: u.email, phone: u.phone, role: u.role,
      is_active: u.is_active, is_staff: u.is_staff, is_superuser: u.is_superuser,
      email_verified: u.email_verified, phone_verified: u.phone_verified, new_password: '',
    })
    setEditOpen(true)
  }

  const saveEdit = async () => {
    const v = await editForm.validateFields()
    if (!v.new_password) delete v.new_password
    setSaving(true)
    try {
      await adminApi.updateUser(Number(id), v)
      message.success('Пользователь обновлён')
      setEditOpen(false)
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка сохранения')
    } finally { setSaving(false) }
  }

  const togglePerm = (key: string, on: boolean) =>
    setPerms((p) => on ? Array.from(new Set([...p, key])) : p.filter((k) => k !== key))

  const savePerms = async () => {
    setSavingPerms(true)
    try {
      await adminApi.setUserPermissions(Number(id), perms)
      message.success('Права сохранены')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    } finally { setSavingPerms(false) }
  }

  const doAdjust = async () => {
    if (!adjAmount || !adjReason) { message.error('Укажите сумму и причину'); return }
    try {
      await adminApi.adjustBalance(Number(id), adjField, adjAmount, adjReason)
      message.success('Баланс изменён')
      setAdjAmount(0); setAdjReason('')
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (!data) return <Alert type="error" message="Пользователь не найден" />

  const u = data.user
  const s = data.stats

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      <Space style={{ marginBottom: 12 }}>
        <Link to="/admin/users">← К списку пользователей</Link>
        {data.shop_id && <Link to={`/admin/shops/${data.shop_id}`}>· Магазин #{data.shop_id}</Link>}
      </Space>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <Title level={3} style={{ marginTop: 0 }}>{u.full_name} <Text type="secondary" style={{ fontSize: 15 }}>#{u.id}</Text> <Tag>{u.role}</Tag></Title>
        <Button type="primary" icon={<EditOutlined />} onClick={openEdit}>Редактировать</Button>
      </div>

      {data.risk_flags?.length > 0 && (
        <Alert
          type="warning" showIcon icon={<WarningOutlined />} style={{ marginBottom: 16 }}
          message="Сигналы для проверки выплаты"
          description={<ul style={{ margin: 0, paddingLeft: 18 }}>{data.risk_flags.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul>}
        />
      )}

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Баланс (продажи)" value={parseFloat(u.balance)} precision={2} suffix="₽" /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Реферальный баланс" value={parseFloat(u.referral_balance)} precision={2} suffix="₽" valueStyle={{ color: '#4d7c0f' }} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Бонусы" value={parseFloat(u.bonus_balance)} precision={2} suffix="₽" /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Промо-баланс" value={parseFloat(u.promo_balance)} precision={2} suffix="₽" /></Card></Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card title="Профиль" size="small" style={{ marginBottom: 16 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Email">{u.email} {u.email_verified ? <Tag color="green">подтверждён</Tag> : <Tag color="red">не подтверждён</Tag>}</Descriptions.Item>
              <Descriptions.Item label="Телефон">{u.phone || '—'} {u.phone_verified && <Tag color="green">подтв.</Tag>}</Descriptions.Item>
              <Descriptions.Item label="Активен / Staff / Superuser">{u.is_active ? '✓' : '✗'} / {u.is_staff ? '✓' : '✗'} / {u.is_superuser ? '✓' : '✗'}</Descriptions.Item>
              <Descriptions.Item label="Реф. код">{u.referral_code || '—'}</Descriptions.Item>
              <Descriptions.Item label="Возраст аккаунта">{s.account_age_days} дн.</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="Статистика и реквизиты вывода" size="small" style={{ marginBottom: 16 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Заказов">{s.orders_count} ({money(s.orders_total_spent)})</Descriptions.Item>
              <Descriptions.Item label="Приглашено">{s.referrals_made}</Descriptions.Item>
              <Descriptions.Item label="Реф. доход всего">{money(s.referral_earned_total)}</Descriptions.Item>
              <Descriptions.Item label="Выплачено / в ожидании">{money(s.payouts_paid_total)} / {money(s.payouts_pending_total)}</Descriptions.Item>
            </Descriptions>
            <Divider style={{ margin: '12px 0' }} />
            {data.withdrawal_account ? (
              <Descriptions column={1} size="small" title="Реквизиты">
                <Descriptions.Item label="Статус">{data.withdrawal_account.tax_regime}</Descriptions.Item>
                <Descriptions.Item label="Получатель">{data.withdrawal_account.legal_name}</Descriptions.Item>
                <Descriptions.Item label="ИНН">{data.withdrawal_account.inn}</Descriptions.Item>
                <Descriptions.Item label="Счёт">{data.withdrawal_account.account_details}</Descriptions.Item>
              </Descriptions>
            ) : <Text type="secondary">Реквизиты вывода не заданы</Text>}
          </Card>
        </Col>
      </Row>

      {isSuperadmin && (
        <Card size="small" title="Корректировка баланса" style={{ marginBottom: 16 }}>
          <Space wrap>
            <Select value={adjField} onChange={setAdjField} options={balanceFields} style={{ width: 200 }} />
            <InputNumber value={adjAmount} onChange={(v) => setAdjAmount(Number(v) || 0)} addonAfter="₽" style={{ width: 160 }} placeholder="+/− сумма" />
            <Input value={adjReason} onChange={(e) => setAdjReason(e.target.value)} placeholder="Причина (обязательно)" style={{ width: 280 }} />
            <Button type="primary" onClick={doAdjust}>Применить</Button>
          </Space>
          <div><Text type="secondary" style={{ fontSize: 12 }}>Отрицательная сумма — списание. Действие фиксируется в журнале и в движении баланса.</Text></div>
        </Card>
      )}

      {isSuperadmin && catalog?.groups && (
        <Card
          size="small" title={<span><SafetyCertificateOutlined /> Права доступа</span>}
          style={{ marginBottom: 16 }}
          extra={<Button type="primary" loading={savingPerms} onClick={savePerms}>Сохранить права</Button>}
        >
          <Alert type="info" showIcon style={{ marginBottom: 12 }}
            message="Выданные права определяют, какие разделы появятся в меню админки у этого пользователя." />
          <Row gutter={[16, 16]}>
            {catalog.groups.map((g: any) => (
              <Col xs={24} md={12} key={g.group}>
                <div style={{ fontWeight: 600, marginBottom: 6, color: '#7c4a21' }}>{g.group}</div>
                <Space direction="vertical" style={{ width: '100%' }}>
                  {g.permissions.map((p: any) => (
                    <div key={p.key}>
                      <Checkbox checked={perms.includes(p.key)} onChange={(e) => togglePerm(p.key, e.target.checked)}>
                        {p.description}
                      </Checkbox>
                      {p.menu?.length > 0 && (
                        <Tooltip title={p.menu.map((m: any) => m.label).join(', ')}>
                          <Tag style={{ marginLeft: 6, cursor: 'help' }} color="orange">
                            меню: {p.menu.map((m: any) => m.label).join(' · ')}
                          </Tag>
                        </Tooltip>
                      )}
                    </div>
                  ))}
                </Space>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      <Card title="Заявки на вывод" size="small" style={{ marginBottom: 16 }}>
        <Table
          rowKey="id" size="small" pagination={false} dataSource={data.payouts}
          columns={[
            { title: 'Дата', dataIndex: 'created_at', render: dt },
            { title: 'Сумма', dataIndex: 'amount', render: money },
            { title: 'Источник', dataIndex: 'source', render: (v) => v === 'referral' ? <Tag color="purple">Рефералы</Tag> : <Tag color="blue">Продажи</Tag> },
            { title: 'Статус', dataIndex: 'status' },
          ]}
        />
      </Card>

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card title="Последние заказы" size="small" style={{ marginBottom: 16 }}>
            <Table
              rowKey="id" size="small" pagination={false} dataSource={data.recent_orders}
              columns={[
                { title: '№', dataIndex: 'id', render: (v) => <Link to={`/orders/${v}`}>#{v}</Link> },
                { title: 'Сумма', dataIndex: 'total_price', render: money },
                { title: 'Статус', dataIndex: 'status' },
                { title: 'Дата', dataIndex: 'created_at', render: dt },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="Движение баланса" size="small" style={{ marginBottom: 16 }}>
            <Table
              rowKey={(_, i) => String(i)} size="small" pagination={false} dataSource={data.balance_transactions}
              columns={[
                { title: 'Изменение', dataIndex: 'change', render: (v) => <Text type={parseFloat(v) < 0 ? 'danger' : 'success'}>{money(v)}</Text> },
                { title: 'Тип', dataIndex: 'reference_type' },
                { title: 'Описание', dataIndex: 'description', ellipsis: true },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Действия в системе" size="small">
        <Table
          rowKey={(_, i) => String(i)} size="small" pagination={false} dataSource={data.recent_actions}
          columns={[
            { title: 'Дата', dataIndex: 'created_at', render: dt },
            { title: 'Действие', dataIndex: 'action' },
            { title: 'Объект', render: (_, r: any) => `${r.entity_type} #${r.entity_id ?? ''}` },
            { title: 'Детали', dataIndex: 'detail', ellipsis: true },
          ]}
        />
      </Card>

      <Modal
        title="Редактирование пользователя" open={editOpen} onOk={saveEdit} confirmLoading={saving}
        onCancel={() => setEditOpen(false)} okText="Сохранить" width={560}
      >
        <Form form={editForm} layout="vertical">
          <Row gutter={12}>
            <Col span={12}><Form.Item name="full_name" label="Имя" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="phone" label="Телефон"><Input /></Form.Item></Col>
          </Row>
          <Form.Item name="email" label="Email" rules={[{ required: true, type: 'email' }]}><Input /></Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="role" label="Роль">
                <Select options={roleOptions} disabled={!isSuperadmin} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="new_password" label="Новый пароль (необязательно)">
                <Input.Password placeholder="оставьте пустым, чтобы не менять" />
              </Form.Item>
            </Col>
          </Row>
          <Space size="large" wrap>
            <Form.Item name="is_active" label="Активен" valuePropName="checked"><Switch /></Form.Item>
            <Form.Item name="is_staff" label="Сотрудник" valuePropName="checked"><Switch /></Form.Item>
            <Form.Item name="is_superuser" label="Суперпользователь" valuePropName="checked"><Switch disabled={!isSuperadmin} /></Form.Item>
            <Form.Item name="email_verified" label="Email подтв." valuePropName="checked"><Switch /></Form.Item>
            <Form.Item name="phone_verified" label="Телефон подтв." valuePropName="checked"><Switch /></Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  )
}
