import { useEffect, useState } from 'react'
import { Card, Typography, Button, Modal, Form, Input, message, List, Popconfirm, Spin, Space } from 'antd'
import { PlusOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { chatTemplatesApi, businessHoursApi, shopsApi } from '@/api'

const { Title, Text } = Typography

export default function SellerChatTemplates() {
  const [templates, setTemplates] = useState<{ id: number; title: string; body: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [businessHours, setBusinessHours] = useState('')
  const [savingHours, setSavingHours] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [tpls, shop] = await Promise.all([
        chatTemplatesApi.list(),
        shopsApi.getMy().catch(() => null),
      ])
      setTemplates(tpls)
      if (shop?.business_hours) setBusinessHours(shop.business_hours)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [])

  const handleCreate = async (values: any) => {
    try {
      await chatTemplatesApi.create(values.title, values.body)
      message.success('Шаблон добавлен')
      setModalOpen(false); form.resetFields()
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const remove = async (id: number) => {
    await chatTemplatesApi.remove(id)
    message.success('Шаблон удалён')
    load()
  }

  const saveHours = async () => {
    setSavingHours(true)
    try {
      await businessHoursApi.update(businessHours)
      message.success('Часы работы сохранены')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    } finally {
      setSavingHours(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div style={{ maxWidth: 760 }}>
      <Title level={3}>Чат: шаблоны и часы работы</Title>

      <Card title={<><ClockCircleOutlined /> Часы работы магазина</>} style={{ marginBottom: 24 }}>
        <Text type="secondary">Покупатели увидят, когда вы обычно на связи.</Text>
        <Space.Compact style={{ width: '100%', marginTop: 12 }}>
          <Input
            value={businessHours}
            onChange={(e) => setBusinessHours(e.target.value)}
            placeholder="Например: Пн-Пт 9:00-18:00, Сб 10:00-15:00"
          />
          <Button type="primary" loading={savingHours} onClick={saveHours}>Сохранить</Button>
        </Space.Compact>
      </Card>

      <Card
        title="Шаблоны ответов"
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>Новый шаблон</Button>}
      >
        <Text type="secondary">Готовые ответы для быстрой переписки с покупателями.</Text>
        <List
          style={{ marginTop: 12 }}
          dataSource={templates}
          locale={{ emptyText: 'Пока нет шаблонов' }}
          renderItem={(t) => (
            <List.Item
              actions={[
                <Popconfirm title="Удалить шаблон?" onConfirm={() => remove(t.id)}>
                  <Button type="link" danger size="small">Удалить</Button>
                </Popconfirm>,
              ]}
            >
              <List.Item.Meta title={t.title} description={t.body} />
            </List.Item>
          )}
        />
      </Card>

      <Modal title="Новый шаблон" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()} okText="Создать">
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="title" label="Название" rules={[{ required: true }]}>
            <Input placeholder="Приветствие" />
          </Form.Item>
          <Form.Item name="body" label="Текст" rules={[{ required: true }]}>
            <Input.TextArea rows={4} placeholder="Здравствуйте! Спасибо за интерес к нашему магазину..." />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
