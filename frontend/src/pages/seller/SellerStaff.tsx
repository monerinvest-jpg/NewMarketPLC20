import { useEffect, useState } from 'react'
import {
  Typography, Card, Table, Button, Modal, Form, Input, Select, Checkbox,
  Row, Col, Tag, Tooltip, message, Space, Popconfirm, Alert,
} from 'antd'
import { UserAddOutlined } from '@ant-design/icons'
import { shopsApi } from '@/api'

const { Title, Paragraph, Text } = Typography

export default function SellerStaff() {
  const [members, setMembers] = useState<any[]>([])
  const [catalog, setCatalog] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<any | null>(null)
  const [form] = Form.useForm()
  const [perms, setPerms] = useState<string[]>([])

  const load = () => {
    setLoading(true)
    Promise.all([shopsApi.members(), shopsApi.staffCatalog()])
      .then(([m, c]) => { setMembers(m); setCatalog(c) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const openAdd = () => {
    setEditing(null); setPerms([])
    form.resetFields(); form.setFieldsValue({ role: 'staff' })
    setOpen(true)
  }
  const openEdit = (m: any) => {
    setEditing(m); setPerms(m.permissions || [])
    form.setFieldsValue({ email: m.email, role: m.role })
    setOpen(true)
  }

  const togglePerm = (key: string, on: boolean) =>
    setPerms((p) => on ? Array.from(new Set([...p, key])) : p.filter((k) => k !== key))

  const save = async () => {
    const v = await form.validateFields()
    try {
      if (editing) {
        await shopsApi.updateMember(editing.user_id, { role: v.role, permissions: perms })
      } else {
        await shopsApi.addMember(v.email, v.role, perms)
      }
      message.success('Сохранено')
      setOpen(false); load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const remove = async (m: any) => {
    try { await shopsApi.removeMember(m.user_id); message.success('Удалён'); load() }
    catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
  }

  const roleLabel = (r: string) => r === 'manager' ? 'Менеджер' : r === 'owner' ? 'Владелец' : 'Сотрудник'
  const isManager = Form.useWatch('role', form) === 'manager'

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <Title level={3} style={{ marginTop: 0 }}>Сотрудники магазина</Title>
        <Button type="primary" icon={<UserAddOutlined />} onClick={openAdd}>Добавить сотрудника</Button>
      </div>
      <Paragraph type="secondary">
        Добавляйте сотрудников и выдавайте им права на отдельные разделы. Менеджер получает полный доступ;
        сотрудник — только отмеченные разделы. Права определяют, какие разделы появятся у него в кабинете.
      </Paragraph>

      <Card size="small">
        <Table
          loading={loading} rowKey="user_id" dataSource={members} pagination={false}
          columns={[
            { title: 'Сотрудник', render: (_, m) => <Space direction="vertical" size={0}><b>{m.full_name}</b><Text type="secondary" style={{ fontSize: 12 }}>{m.email}</Text></Space> },
            { title: 'Роль', dataIndex: 'role', render: (r) => <Tag color={r === 'manager' ? 'gold' : 'blue'}>{roleLabel(r)}</Tag> },
            { title: 'Права', render: (_, m) => m.role === 'manager' ? <Tag color="gold">все</Tag> : (m.permissions?.length ? m.permissions.map((p: string) => <Tag key={p}>{catalog?.groups?.flatMap((g: any) => g.permissions).find((x: any) => x.key === p)?.description || p}</Tag>) : <Text type="secondary">—</Text>) },
            {
              title: '', width: 140, render: (_, m) => (
                <Space>
                  <Button size="small" onClick={() => openEdit(m)}>Права</Button>
                  <Popconfirm title="Удалить сотрудника?" onConfirm={() => remove(m)}><Button size="small" danger>Удалить</Button></Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title={editing ? `Права: ${editing.full_name}` : 'Новый сотрудник'}
        open={open} onCancel={() => setOpen(false)} onOk={save} okText="Сохранить" width={620}
      >
        <Form form={form} layout="vertical">
          {!editing && (
            <Form.Item name="email" label="Email сотрудника (уже зарегистрирован)" rules={[{ required: true, type: 'email' }]}>
              <Input placeholder="employee@example.com" />
            </Form.Item>
          )}
          <Form.Item name="role" label="Роль">
            <Select options={[{ value: 'manager', label: 'Менеджер (полный доступ)' }, { value: 'staff', label: 'Сотрудник (выбранные права)' }]} />
          </Form.Item>

          {isManager ? (
            <Alert type="info" showIcon message="Менеджер получает доступ ко всем разделам кабинета." />
          ) : (
            <>
              <Text strong>Права сотрудника</Text>
              <div style={{ marginTop: 8 }}>
                {catalog?.groups?.map((g: any) => (
                  <div key={g.group} style={{ marginBottom: 12 }}>
                    <div style={{ fontWeight: 600, color: '#7c4a21', marginBottom: 4 }}>{g.group}</div>
                    {g.permissions.map((p: any) => (
                      <div key={p.key}>
                        <Checkbox checked={perms.includes(p.key)} onChange={(e) => togglePerm(p.key, e.target.checked)}>{p.description}</Checkbox>
                        {p.menu?.length > 0 && (
                          <Tooltip title={p.menu.map((m: any) => m.label).join(', ')}>
                            <Tag color="orange" style={{ marginLeft: 6, cursor: 'help' }}>меню: {p.menu.map((m: any) => m.label).join(' · ')}</Tag>
                          </Tooltip>
                        )}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </>
          )}
        </Form>
      </Modal>
    </div>
  )
}
