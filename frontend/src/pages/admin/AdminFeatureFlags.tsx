import { useEffect, useState } from 'react'
import { Card, Table, Typography, Button, Modal, Form, Input, Switch, InputNumber, message, Tag, Popconfirm, Spin } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { adminApi } from '@/api'
import dayjs from 'dayjs'

const { Title, Text } = Typography

export default function AdminFeatureFlags() {
  const [flags, setFlags] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const load = () => {
    setLoading(true)
    adminApi.listFeatureFlags().then(setFlags).catch(() => {}).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const handleSubmit = async (values: any) => {
    try {
      await adminApi.upsertFeatureFlag({
        key: values.key,
        description: values.description,
        is_enabled: values.is_enabled || false,
        rollout_percent: values.rollout_percent ?? 100,
      })
      message.success('Флаг сохранён')
      setModalOpen(false); form.resetFields()
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const toggle = async (flag: any) => {
    await adminApi.upsertFeatureFlag({ ...flag, is_enabled: !flag.is_enabled })
    load()
  }

  const remove = async (id: number) => {
    await adminApi.deleteFeatureFlag(id)
    message.success('Флаг удалён')
    load()
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Feature flags</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>Новый флаг</Button>
      </div>
      <Text type="secondary">Включайте функции без передеплоя. rollout % — доля пользователей, для которых флаг активен.</Text>

      <Card style={{ marginTop: 16 }}>
        <Table
          dataSource={flags}
          rowKey="id"
          pagination={false}
          columns={[
            { title: 'Ключ', dataIndex: 'key', render: (v) => <Text code>{v}</Text> },
            { title: 'Описание', dataIndex: 'description', render: (v) => v || '—' },
            {
              title: 'Статус', dataIndex: 'is_enabled', width: 120,
              render: (v, r) => <Switch checked={v} onChange={() => toggle(r)} checkedChildren="вкл" unCheckedChildren="выкл" />,
            },
            { title: 'Rollout', dataIndex: 'rollout_percent', width: 100, render: (v) => <Tag>{v}%</Tag> },
            { title: 'Обновлён', dataIndex: 'updated_at', render: (v) => dayjs(v).format('DD.MM.YY HH:mm') },
            {
              title: '', width: 80,
              render: (_, r) => (
                <Popconfirm title="Удалить флаг?" onConfirm={() => remove(r.id)}>
                  <Button type="link" danger size="small">Удалить</Button>
                </Popconfirm>
              ),
            },
          ]}
        />
      </Card>

      <Modal title="Feature flag" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()} okText="Сохранить">
        <Form form={form} layout="vertical" onFinish={handleSubmit} initialValues={{ is_enabled: false, rollout_percent: 100 }}>
          <Form.Item name="key" label="Ключ" rules={[{ required: true }]}>
            <Input placeholder="new_checkout_flow" />
          </Form.Item>
          <Form.Item name="description" label="Описание">
            <Input placeholder="Краткое описание функции" />
          </Form.Item>
          <Form.Item name="is_enabled" label="Включён" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="rollout_percent" label="Rollout, %">
            <InputNumber min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
