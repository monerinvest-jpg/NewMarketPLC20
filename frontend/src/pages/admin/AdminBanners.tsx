import { useEffect, useState } from 'react'
import { Table, Button, Modal, Form, Input, Switch, InputNumber, message, Typography, Popconfirm, Image, Tag } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { adminApi } from '@/api'
import type { HomepageBanner } from '@/types'

const { Title } = Typography

export default function AdminBanners() {
  const [banners, setBanners] = useState<HomepageBanner[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const load = () => {
    setLoading(true)
    adminApi.listBanners().then(setBanners).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleSubmit = async (values: any) => {
    try {
      await adminApi.createBanner(values)
      message.success('Баннер создан')
      setModalOpen(false)
      form.resetFields()
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const handleDelete = async (id: number) => {
    await adminApi.deleteBanner(id)
    message.success('Удалено')
    load()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Баннеры на главной</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>Добавить баннер</Button>
      </div>

      <Table
        loading={loading}
        dataSource={banners}
        rowKey="id"
        pagination={false}
        columns={[
          { title: 'Картинка', dataIndex: 'image_url', render: (v) => <Image src={v} width={120} height={60} style={{ objectFit: 'cover' }} /> },
          { title: 'Заголовок', dataIndex: 'title' },
          { title: 'Подзаголовок', dataIndex: 'subtitle' },
          { title: 'Ссылка', dataIndex: 'link', render: (v) => v || '—' },
          { title: 'Активен', dataIndex: 'is_active', render: (v) => v ? <Tag color="green">Да</Tag> : <Tag>Нет</Tag> },
          { title: 'Порядок', dataIndex: 'sort_order' },
          {
            title: '', render: (_, b) => (
              <Popconfirm title="Удалить баннер?" onConfirm={() => handleDelete(b.id)}>
                <Button size="small" danger>Удалить</Button>
              </Popconfirm>
            ),
          },
        ]}
      />

      <Modal title="Новый баннер" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={handleSubmit} initialValues={{ is_active: true, sort_order: 0 }}>
          <Form.Item name="title" label="Заголовок" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="subtitle" label="Подзаголовок">
            <Input />
          </Form.Item>
          <Form.Item name="image_url" label="URL изображения" rules={[{ required: true }]}>
            <Input placeholder="https://..." />
          </Form.Item>
          <Form.Item name="link" label="Ссылка при клике">
            <Input placeholder="/catalog?category=..." />
          </Form.Item>
          <Form.Item name="sort_order" label="Порядок сортировки">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_active" label="Активен" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
