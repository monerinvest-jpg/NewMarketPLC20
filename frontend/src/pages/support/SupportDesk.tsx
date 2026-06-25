import { useEffect, useState, useCallback } from 'react'
import {
  Row, Col, Card, Table, Typography, Tag, Select, Input, Button, Space, Statistic,
  Drawer, Descriptions, message, Empty,
} from 'antd'
import { UserOutlined, SendOutlined, ReloadOutlined } from '@ant-design/icons'
import { supportApi } from '@/api'
import { useAuthStore } from '@/store/authStore'
import type { SupportTicket, SupportStats, SupportUserView, SupportTicketStatus } from '@/types'
import dayjs from 'dayjs'

const { Title, Text } = Typography
const { TextArea } = Input

const statusMeta: Record<SupportTicketStatus, { color: string; label: string }> = {
  open: { color: 'blue', label: 'Открыто' },
  in_progress: { color: 'gold', label: 'В работе' },
  pending_user: { color: 'orange', label: 'Ждём клиента' },
  resolved: { color: 'green', label: 'Решено' },
  closed: { color: 'default', label: 'Закрыто' },
}
const priorityMeta: Record<string, { color: string; label: string }> = {
  low: { color: 'default', label: 'Низкий' },
  normal: { color: 'blue', label: 'Обычный' },
  high: { color: 'orange', label: 'Высокий' },
  urgent: { color: 'red', label: 'Срочный' },
}

export default function SupportDesk() {
  const { user } = useAuthStore()
  const isLead = user?.role === 'moderator' || user?.role === 'superadmin'
  const [stats, setStats] = useState<SupportStats | null>(null)
  const [tickets, setTickets] = useState<SupportTicket[]>([])
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [assigned, setAssigned] = useState<string | undefined>()
  const [onlyOverdue, setOnlyOverdue] = useState(false)
  const [active, setActive] = useState<SupportTicket | null>(null)
  const [reply, setReply] = useState('')
  const [userView, setUserView] = useState<SupportUserView | null>(null)

  const loadStats = useCallback(() => { supportApi.staffStats().then(setStats).catch(() => {}) }, [])
  const loadList = useCallback(() => {
    supportApi.staffTickets({ status: statusFilter, assigned, overdue: onlyOverdue || undefined })
      .then((r) => setTickets(r.items)).catch(() => {})
  }, [statusFilter, assigned, onlyOverdue])

  const openTicket = (id: number) => supportApi.staffGetTicket(id).then(setActive).catch(() => {})

  useEffect(() => { loadStats() }, [loadStats])
  useEffect(() => { loadList() }, [loadList])

  const refresh = () => { loadList(); loadStats(); if (active) openTicket(active.id) }

  const runSweep = async () => {
    const r = await supportApi.staffSlaSweep()
    message.success(`SLA: эскалаций ${r.escalated}, авто-назначено ${r.auto_assigned}`)
    refresh()
  }

  const sendReply = async () => {
    if (!active || !reply.trim()) return
    await supportApi.staffReply(active.id, reply.trim())
    setReply('')
    refresh()
  }
  const update = async (data: { status?: string; priority?: string }) => {
    if (!active) return
    await supportApi.staffUpdate(active.id, data)
    refresh()
    message.success('Обновлено')
  }
  const assignMe = async () => {
    if (!active) return
    await supportApi.staffAssignMe(active.id)
    refresh()
  }
  const viewUser = (userId: number) => supportApi.staffUserView(userId).then(setUserView).catch(() => message.error('Нет доступа'))

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Стол поддержки</Title>
        <Space>
          {isLead && <Button onClick={runSweep}>SLA-проверка</Button>}
          <Button icon={<ReloadOutlined />} onClick={refresh}>Обновить</Button>
        </Space>
      </div>

      {stats && (
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col xs={8} md={4}><Card size="small"><Statistic title="Открыто" value={stats.open} valueStyle={{ color: '#1677ff' }} /></Card></Col>
          <Col xs={8} md={4}><Card size="small"><Statistic title="В работе" value={stats.in_progress} valueStyle={{ color: '#d48806' }} /></Card></Col>
          <Col xs={8} md={4}><Card size="small"><Statistic title="Не назначено" value={stats.unassigned} valueStyle={{ color: '#cf1322' }} /></Card></Col>
          <Col xs={8} md={4}><Card size="small"><Statistic title="Просрочено (SLA)" value={stats.overdue} valueStyle={{ color: stats.overdue > 0 ? '#cf1322' : undefined }} /></Card></Col>
          <Col xs={8} md={4}><Card size="small"><Statistic title="Решено сегодня" value={stats.resolved_today} valueStyle={{ color: '#3f8600' }} /></Card></Col>
          <Col xs={16} md={4}>
            <Card size="small">
              <Statistic title="Ср. время 1-го ответа" value={stats.avg_first_response_minutes ?? '—'} suffix={stats.avg_first_response_minutes != null ? 'мин' : ''} />
            </Card>
          </Col>
        </Row>
      )}

      <Space style={{ marginBottom: 16 }} wrap>
        <Select placeholder="Статус" allowClear style={{ width: 160 }} value={statusFilter}
          onChange={setStatusFilter}
          options={Object.entries(statusMeta).map(([v, m]) => ({ value: v, label: m.label }))} />
        <Select placeholder="Назначение" allowClear style={{ width: 180 }} value={assigned}
          onChange={setAssigned}
          options={[{ value: 'me', label: 'Мои' }, { value: 'unassigned', label: 'Не назначенные' }]} />
        <Button type={onlyOverdue ? 'primary' : 'default'} danger={onlyOverdue} onClick={() => setOnlyOverdue((v) => !v)}>
          Только просроченные
        </Button>
      </Space>

      <Row gutter={16}>
        <Col xs={24} lg={13}>
          <Card styles={{ body: { padding: 0 } }}>
            <Table<SupportTicket>
              dataSource={tickets} rowKey="id" size="small"
              pagination={{ pageSize: 10 }}
              onRow={(r) => ({ onClick: () => openTicket(r.id), style: { cursor: 'pointer' } })}
              columns={[
                { title: '№', dataIndex: 'id', width: 60 },
                { title: 'Тема', dataIndex: 'subject', ellipsis: true, render: (v, r) => (
                  <span>{r.is_overdue && <Tag color="red" style={{ marginRight: 6 }}>SLA</Tag>}{v}</span>
                ) },
                { title: 'Статус', dataIndex: 'status', width: 110, render: (v: SupportTicketStatus) => <Tag color={statusMeta[v]?.color}>{statusMeta[v]?.label}</Tag> },
                { title: 'Приоритет', dataIndex: 'priority', width: 100, render: (v) => <Tag color={priorityMeta[v]?.color}>{priorityMeta[v]?.label}</Tag> },
                { title: 'Обновлён', dataIndex: 'last_message_at', width: 120, render: (v) => dayjs(v).format('DD.MM HH:mm') },
              ]}
            />
          </Card>
        </Col>

        <Col xs={24} lg={11}>
          {!active ? (
            <Card><Empty description="Выберите обращение" /></Card>
          ) : (
            <Card
              title={<Space wrap><span>#{active.id} {active.subject}</span></Space>}
              extra={
                <Button size="small" icon={<UserOutlined />} onClick={() => viewUser(active.user_id)}>
                  {active.user?.full_name || 'Клиент'}
                </Button>
              }
            >
              <Space style={{ marginBottom: 12 }} wrap>
                <Select size="small" value={active.status} style={{ width: 140 }}
                  onChange={(v) => update({ status: v })}
                  options={Object.entries(statusMeta).map(([v, m]) => ({ value: v, label: m.label }))} />
                <Select size="small" value={active.priority} style={{ width: 130 }}
                  onChange={(v) => update({ priority: v })}
                  options={Object.entries(priorityMeta).map(([v, m]) => ({ value: v, label: m.label }))} />
                {active.assigned_to_id == null && <Button size="small" onClick={assignMe}>Взять себе</Button>}
                {active.assigned_to && <Tag>Агент: {active.assigned_to.full_name}</Tag>}
              </Space>

              <div style={{ maxHeight: 360, overflowY: 'auto', marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {active.messages?.map((m) => (
                  <div key={m.id} style={{ alignSelf: m.is_staff ? 'flex-end' : 'flex-start', maxWidth: '80%' }}>
                    <div style={{ padding: '8px 12px', borderRadius: 12, background: m.is_staff ? '#f97316' : '#f1f5f9', color: m.is_staff ? '#fff' : '#0f172a' }}>
                      {m.text}
                    </div>
                    <Text type="secondary" style={{ fontSize: 11 }}>{m.is_staff ? 'Поддержка' : 'Клиент'} · {dayjs(m.created_at).format('DD.MM HH:mm')}</Text>
                  </div>
                ))}
              </div>
              {active.status !== 'closed' && (
                <div style={{ display: 'flex', gap: 8 }}>
                  <TextArea rows={2} value={reply} onChange={(e) => setReply(e.target.value)}
                    placeholder="Ответ клиенту…" onPressEnter={(e) => { e.preventDefault(); sendReply() }} />
                  <Button type="primary" icon={<SendOutlined />} onClick={sendReply} />
                </div>
              )}
            </Card>
          )}
        </Col>
      </Row>

      <Drawer title="Карточка клиента" open={!!userView} onClose={() => setUserView(null)} width={420}>
        {userView && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="Имя">{userView.full_name}</Descriptions.Item>
            <Descriptions.Item label="Email">{userView.email}</Descriptions.Item>
            <Descriptions.Item label="Телефон">{userView.phone || '—'}</Descriptions.Item>
            <Descriptions.Item label="Роль">{userView.role}</Descriptions.Item>
            <Descriptions.Item label="Активен">{userView.is_active ? 'Да' : 'Нет'}</Descriptions.Item>
            <Descriptions.Item label="Баланс">{Number(userView.balance).toLocaleString('ru')} ₽</Descriptions.Item>
            <Descriptions.Item label="Бонусы">{Number(userView.bonus_balance).toLocaleString('ru')}</Descriptions.Item>
            <Descriptions.Item label="Заказов">{userView.orders_count}</Descriptions.Item>
            <Descriptions.Item label="Обращений">{userView.tickets_count}</Descriptions.Item>
            <Descriptions.Item label="Продавец">{userView.is_seller ? `Да — ${userView.shop_name}` : 'Нет'}</Descriptions.Item>
            <Descriptions.Item label="Регистрация">{dayjs(userView.created_at).format('DD.MM.YYYY')}</Descriptions.Item>
          </Descriptions>
        )}
        {userView && !isLead && (
          <Text type="secondary" style={{ display: 'block', marginTop: 12, fontSize: 12 }}>
            Просмотр только для чтения. Редактирование доступно администратору.
          </Text>
        )}
      </Drawer>
    </div>
  )
}
