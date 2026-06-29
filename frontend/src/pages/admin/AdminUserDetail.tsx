import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Alert, Table, Row, Col, Statistic, Spin,
  Typography, Select, Switch, Button, message, Space, Divider,
} from 'antd'
import { WarningOutlined } from '@ant-design/icons'
import { adminApi } from '@/api'

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

export default function AdminUserDetail() {
  const { id } = useParams()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    adminApi.userDetail(Number(id)).then(setData).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [id])

  const save = async (patch: any) => {
    setSaving(true)
    try {
      await adminApi.updateUser(Number(id), patch)
      message.success('Сохранено')
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка сохранения')
    } finally { setSaving(false) }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (!data) return <Alert type="error" message="Пользователь не найден" />

  const u = data.user
  const s = data.stats

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      <Space style={{ marginBottom: 12 }}>
        <Link to="/admin/users">← К списку пользователей</Link>
        {data.shop_id && <Link to={`/admin/shops`}>· Магазин #{data.shop_id}</Link>}
      </Space>
      <Title level={3} style={{ marginTop: 0 }}>{u.full_name} <Text type="secondary" style={{ fontSize: 15 }}>#{u.id}</Text></Title>

      {data.risk_flags?.length > 0 && (
        <Alert
          type="warning" showIcon icon={<WarningOutlined />}
          style={{ marginBottom: 16 }}
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
              <Descriptions.Item label="Телефон">{u.phone || '—'}</Descriptions.Item>
              <Descriptions.Item label="Реф. код">{u.referral_code || '—'}</Descriptions.Item>
              <Descriptions.Item label="Возраст аккаунта">{s.account_age_days} дн.</Descriptions.Item>
            </Descriptions>
            <Divider style={{ margin: '12px 0' }} />
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text strong>Роль: </Text>
                <Select
                  value={u.role} options={roleOptions} style={{ width: 200 }} disabled={saving}
                  onChange={(role) => save({ role })}
                />
              </div>
              <div>
                <Space>
                  <Text strong>Активен:</Text>
                  <Switch checked={u.is_active} disabled={saving} onChange={(v) => save({ is_active: v })} />
                  <Text strong style={{ marginLeft: 16 }}>Сотрудник (staff):</Text>
                  <Switch checked={u.is_staff} disabled={saving} onChange={(v) => save({ is_staff: v })} />
                </Space>
              </div>
            </Space>
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
    </div>
  )
}
