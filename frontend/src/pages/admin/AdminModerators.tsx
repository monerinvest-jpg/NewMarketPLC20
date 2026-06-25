import { useEffect, useState } from 'react'
import { Table, Button, Input, message, Typography, Popconfirm, Space, Modal, Checkbox, Tag } from 'antd'
import { adminApi } from '@/api'
import type { User } from '@/types'

const { Title } = Typography

export default function AdminModerators() {
  const [moderators, setModerators] = useState<User[]>([])
  const [agents, setAgents] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [searchResults, setSearchResults] = useState<User[]>([])
  const [searching, setSearching] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      adminApi.listModerators(),
      adminApi.listUsers({ role: 'support', page: 1 }),
    ]).then(([mods, sup]) => {
      setModerators(mods)
      setAgents(sup.items)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleSearch = async (q: string) => {
    if (!q.trim()) { setSearchResults([]); return }
    setSearching(true)
    try {
      const res = await adminApi.listUsers({ q, page: 1 })
      setSearchResults(res.items.filter((u) => !['moderator', 'superadmin', 'support'].includes(u.role)))
    } finally {
      setSearching(false)
    }
  }

  const assignModerator = async (userId: number) => {
    await adminApi.assignModerator(userId)
    message.success('Назначен модератором')
    setSearchResults(searchResults.filter((u) => u.id !== userId))
    load()
  }

  const assignSupport = async (userId: number) => {
    await adminApi.updateUser(userId, { role: 'support', is_staff: true })
    message.success('Назначен агентом поддержки')
    setSearchResults(searchResults.filter((u) => u.id !== userId))
    load()
  }

  const removeModerator = async (userId: number) => {
    await adminApi.removeModerator(userId)
    message.success('Права модератора отозваны')
    load()
  }

  const removeStaff = async (userId: number) => {
    await adminApi.updateUser(userId, { role: 'buyer', is_staff: false })
    message.success('Роль снята')
    load()
  }

  const [permModal, setPermModal] = useState<{ open: boolean; user?: User }>({ open: false })
  const [catalog, setCatalog] = useState<{ key: string; description: string }[]>([])
  const [selectedPerms, setSelectedPerms] = useState<string[]>([])

  const openPermissions = async (user: User) => {
    const [cat, current] = await Promise.all([
      adminApi.permissionsCatalog(),
      adminApi.getUserPermissions(user.id),
    ])
    setCatalog(cat)
    setSelectedPerms(current.permissions || [])
    setPermModal({ open: true, user })
  }

  const savePermissions = async () => {
    if (!permModal.user) return
    await adminApi.setUserPermissions(permModal.user.id, selectedPerms)
    message.success('Права обновлены')
    setPermModal({ open: false })
  }

  const staffActions = (m: User, onRemove: (id: number) => void, removeTitle: string) => (
    <Space>
      <Button size="small" onClick={() => openPermissions(m)}>Права</Button>
      <Popconfirm title={removeTitle} onConfirm={() => onRemove(m.id)}>
        <Button danger size="small">Снять</Button>
      </Popconfirm>
    </Space>
  )

  return (
    <div>
      <Title level={3}>Персонал: модерация и поддержка</Title>

      <div style={{ marginBottom: 24 }}>
        <Title level={5}>Назначить сотрудника</Title>
        <Input.Search
          placeholder="Поиск пользователя по email или имени"
          onSearch={handleSearch}
          loading={searching}
          style={{ width: 360 }}
        />
        {searchResults.length > 0 && (
          <Table
            style={{ marginTop: 12 }}
            dataSource={searchResults}
            rowKey="id"
            pagination={false}
            size="small"
            columns={[
              { title: 'Имя', dataIndex: 'full_name' },
              { title: 'Email', dataIndex: 'email' },
              { title: 'Роль', dataIndex: 'role' },
              {
                title: '', render: (_, u) => (
                  <Space>
                    <Button size="small" type="primary" onClick={() => assignModerator(u.id)}>Модератор</Button>
                    <Button size="small" onClick={() => assignSupport(u.id)}>Поддержка</Button>
                  </Space>
                ),
              },
            ]}
          />
        )}
      </div>

      <Title level={5}>Модераторы <Tag>{moderators.length}</Tag></Title>
      <Title level={5} type="secondary" style={{ fontWeight: 400, fontSize: 13, marginTop: 0 }}>
        Модераторы руководят поддержкой: назначают обращения, видят статистику, просматривают данные.
      </Title>
      <Table
        loading={loading}
        dataSource={moderators}
        rowKey="id"
        pagination={false}
        columns={[
          { title: 'Имя', dataIndex: 'full_name' },
          { title: 'Email', dataIndex: 'email' },
          { title: 'Действия', render: (_, m) => staffActions(m, removeModerator, 'Отозвать права модератора?') },
        ]}
      />

      <Title level={5} style={{ marginTop: 32 }}>Агенты поддержки <Tag>{agents.length}</Tag></Title>
      <Table
        loading={loading}
        dataSource={agents}
        rowKey="id"
        pagination={false}
        columns={[
          { title: 'Имя', dataIndex: 'full_name' },
          { title: 'Email', dataIndex: 'email' },
          { title: 'Действия', render: (_, m) => staffActions(m, removeStaff, 'Снять роль агента поддержки?') },
        ]}
      />

      <Modal
        title={`Права: ${permModal.user?.email || ''}`}
        open={permModal.open}
        onCancel={() => setPermModal({ open: false })}
        onOk={savePermissions}
        okText="Сохранить"
      >
        <Typography.Text type="secondary">
          Отметьте, какие действия разрешены этому сотруднику сверх базовой роли.
        </Typography.Text>
        <Checkbox.Group
          style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}
          value={selectedPerms}
          onChange={(v) => setSelectedPerms(v as string[])}
        >
          {catalog.map((p) => (
            <Checkbox key={p.key} value={p.key}>{p.description} <Typography.Text code style={{ fontSize: 11 }}>{p.key}</Typography.Text></Checkbox>
          ))}
        </Checkbox.Group>
      </Modal>
    </div>
  )
}
