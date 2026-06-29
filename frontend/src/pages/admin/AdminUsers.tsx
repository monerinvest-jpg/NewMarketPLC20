import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Table, Input, Select, Switch, Tag, Typography, message, Space, Button } from 'antd'
import { adminApi } from '@/api'
import type { User } from '@/types'

const { Title } = Typography

const roleLabels: Record<string, string> = {
  buyer: 'Покупатель', seller: 'Продавец', support: 'Поддержка', moderator: 'Модератор', superadmin: 'Супер-админ',
}

export default function AdminUsers() {
  const [users, setUsers] = useState<User[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [roleFilter, setRoleFilter] = useState<string | undefined>()

  const load = () => {
    setLoading(true)
    adminApi.listUsers({ page, q: q || undefined, role: roleFilter })
      .then((res) => { setUsers(res.items); setTotal(res.total) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page, roleFilter])

  const handleToggleActive = async (user: User) => {
    try {
      const updated = await adminApi.updateUser(user.id, { is_active: !user.is_active })
      setUsers(users.map((u) => (u.id === user.id ? updated : u)))
      message.success(updated.is_active ? 'Пользователь активирован' : 'Пользователь заблокирован')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  return (
    <div>
      <Title level={3}>Пользователи</Title>
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="Поиск по email или имени"
          onSearch={(v) => { setQ(v); setPage(1); load() }}
          style={{ width: 280 }}
        />
        <Select
          placeholder="Все роли" allowClear style={{ width: 180 }}
          value={roleFilter}
          onChange={setRoleFilter}
          options={[
            { value: 'buyer', label: 'Покупатель' },
            { value: 'seller', label: 'Продавец' },
            { value: 'support', label: 'Поддержка' },
            { value: 'moderator', label: 'Модератор' },
            { value: 'superadmin', label: 'Супер-админ' },
          ]}
        />
      </Space>

      <Table
        loading={loading}
        dataSource={users}
        rowKey="id"
        pagination={{ current: page, total, pageSize: 20, onChange: setPage, showSizeChanger: false }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: 'Имя', dataIndex: 'full_name' },
          { title: 'Email', dataIndex: 'email' },
          { title: 'Роль', dataIndex: 'role', render: (r) => <Tag color="blue">{roleLabels[r]}</Tag> },
          { title: 'Баланс', dataIndex: 'balance', render: (v) => `${parseFloat(v).toLocaleString('ru')} ₽` },
          { title: 'Бонусы', dataIndex: 'bonus_balance', render: (v) => `${parseFloat(v).toLocaleString('ru')} ₽` },
          {
            title: 'Активен', dataIndex: 'is_active',
            render: (active, user) => (
              <Switch checked={active} onChange={() => handleToggleActive(user)} />
            ),
          },
          {
            title: '', width: 110,
            render: (_, user) => <Link to={`/admin/users/${user.id}`}><Button size="small">Профиль</Button></Link>,
          },
        ]}
      />
    </div>
  )
}
