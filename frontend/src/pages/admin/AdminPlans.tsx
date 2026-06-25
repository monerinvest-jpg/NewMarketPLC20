import { useEffect, useState } from 'react'
import {
  Table, Button, Modal, Form, Input, InputNumber, Switch,
  Tag, message, Typography, Popconfirm, Alert, Space
} from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons'
import { adminApi } from '@/api'
import type { SellerPlan, Setting } from '@/types'

const { Title, Text } = Typography

export default function AdminPlans() {
  const [plans, setPlans] = useState<SellerPlan[]>([])
  const [paidEnabled, setPaidEnabled] = useState(false)
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<SellerPlan | null>(null)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const [p, settings] = await Promise.all([adminApi.listPlans(), adminApi.getSettings()])
      setPlans(p)
      const flag = settings.find((s: Setting) => s.key === 'enable_paid_placement')
      setPaidEnabled(flag?.value === 'true')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleTogglePaid = async (checked: boolean) => {
    await adminApi.updateSetting('enable_paid_placement', String(checked))
    setPaidEnabled(checked)
    message.success(checked ? 'Платное размещение включено' : 'Платное размещение отключено')
  }

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ monthly_price: 0, commission_percent: 10, trial_days: 0, is_active: true, is_default: false, sort_order: 0 })
    setModalOpen(true)
  }

  const openEdit = (plan: SellerPlan) => {
    setEditing(plan)
    form.setFieldsValue({
      ...plan,
      monthly_price: parseFloat(plan.monthly_price),
      commission_percent: parseFloat(plan.commission_percent),
    })
    setModalOpen(true)
  }

  const handleSubmit = async (values: any) => {
    try {
      if (editing) {
        await adminApi.updatePlan(editing.id, values)
        message.success('Тариф обновлён')
      } else {
        await adminApi.createPlan(values)
        message.success('Тариф создан')
      }
      setModalOpen(false)
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await adminApi.deletePlan(id)
      message.success('Тариф удалён')
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка удаления')
    }
  }

  return (
    <div>
      <Title level={3}>Тарифы продавцов</Title>

      <Alert
        style={{ marginBottom: 16 }}
        type={paidEnabled ? 'success' : 'info'}
        message={
          <Space>
            <Text strong>Платное размещение продавцов:</Text>
            <Switch checked={paidEnabled} onChange={handleTogglePaid} />
            <Text>{paidEnabled ? 'включено' : 'отключено'}</Text>
          </Space>
        }
        description="Когда включено, продавцы могут выбирать тариф: бесплатно с повышенной комиссией или платно со сниженной. Когда отключено — действует единая глобальная комиссия."
      />

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>Создать тариф</Button>
      </div>

      <Table
        loading={loading}
        dataSource={plans}
        rowKey="id"
        pagination={false}
        columns={[
          { title: 'Название', dataIndex: 'name' },
          {
            title: 'Цена/мес', dataIndex: 'monthly_price',
            render: (v) => parseFloat(v) === 0 ? <Tag color="green">Бесплатно</Tag> : `${parseFloat(v).toLocaleString('ru')} ₽`,
          },
          { title: 'Комиссия', dataIndex: 'commission_percent', render: (v) => <Tag color="blue">{v}%</Tag> },
          { title: 'Триал', dataIndex: 'trial_days', render: (v) => v > 0 ? `${v} дн.` : '—' },
          { title: 'По умолчанию', dataIndex: 'is_default', render: (v) => v ? <Tag color="orange">Да</Tag> : '—' },
          { title: 'Активен', dataIndex: 'is_active', render: (v) => v ? <Tag color="green">Да</Tag> : <Tag>Нет</Tag> },
          {
            title: 'Действия',
            render: (_, plan) => (
              <Space>
                <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(plan)} />
                <Popconfirm title="Удалить тариф?" onConfirm={() => handleDelete(plan.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? 'Редактировать тариф' : 'Новый тариф'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="name" label="Название" rules={[{ required: true }]}>
            <Input placeholder="Например: Профи" />
          </Form.Item>
          <Form.Item name="description" label="Описание">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="monthly_price" label="Цена в месяц, ₽ (0 = бесплатный)" rules={[{ required: true }]}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="commission_percent" label="Комиссия платформы, %" rules={[{ required: true }]}>
            <InputNumber min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="trial_days" label="Пробный период, дней (0 = нет)">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="sort_order" label="Порядок сортировки">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Space size="large">
            <Form.Item name="is_active" label="Активен" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="is_default" label="По умолчанию для новых продавцов" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  )
}
