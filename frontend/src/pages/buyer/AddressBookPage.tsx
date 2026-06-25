import { useEffect, useState } from 'react'
import { Card, Button, Modal, Form, Input, Switch, message, Typography, Empty, Spin, Tag, Popconfirm, Row, Col } from 'antd'
import { PlusOutlined, EnvironmentOutlined } from '@ant-design/icons'
import { addressApi } from '@/api'
import type { Address } from '@/types'

const { Title, Text } = Typography

export default function AddressBookPage() {
  const [addresses, setAddresses] = useState<Address[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Address | null>(null)
  const [form] = Form.useForm()

  const load = () => {
    setLoading(true)
    addressApi.list().then(setAddresses).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (a: Address) => {
    setEditing(a)
    form.setFieldsValue(a)
    setModalOpen(true)
  }

  const handleSubmit = async (values: any) => {
    try {
      if (editing) {
        await addressApi.update(editing.id, values)
        message.success('Адрес обновлён')
      } else {
        await addressApi.create(values)
        message.success('Адрес добавлен')
      }
      setModalOpen(false)
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const handleDelete = async (id: number) => {
    await addressApi.remove(id)
    message.success('Адрес удалён')
    load()
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div style={{ maxWidth: 820 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}><EnvironmentOutlined /> Мои адреса</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>Добавить адрес</Button>
      </div>

      {addresses.length === 0 ? (
        <Empty description="У вас пока нет сохранённых адресов" />
      ) : (
        <Row gutter={[16, 16]}>
          {addresses.map((a) => (
            <Col xs={24} md={12} key={a.id}>
              <Card
                size="small"
                title={<>{a.label} {a.is_default && <Tag color="orange">По умолчанию</Tag>}</>}
                extra={
                  <>
                    <Button type="link" size="small" onClick={() => openEdit(a)}>Изменить</Button>
                    <Popconfirm title="Удалить адрес?" onConfirm={() => handleDelete(a.id)}>
                      <Button type="link" size="small" danger>Удалить</Button>
                    </Popconfirm>
                  </>
                }
              >
                <Text>{a.full_name}, {a.phone}</Text><br />
                <Text type="secondary">
                  {[a.postal_code, a.city, a.street, a.building && `д. ${a.building}`, a.apartment && `кв. ${a.apartment}`].filter(Boolean).join(', ')}
                </Text>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title={editing ? 'Изменить адрес' : 'Новый адрес'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        okText="Сохранить"
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit} initialValues={{ is_default: false }}>
          <Form.Item name="label" label="Название (Дом, Работа)" rules={[{ required: true }]}>
            <Input placeholder="Дом" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="full_name" label="Получатель" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="phone" label="Телефон" rules={[{ required: true }]}><Input placeholder="+7..." /></Form.Item></Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="city" label="Город" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="postal_code" label="Индекс"><Input /></Form.Item></Col>
          </Row>
          <Form.Item name="street" label="Улица" rules={[{ required: true }]}><Input /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="building" label="Дом"><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="apartment" label="Квартира"><Input /></Form.Item></Col>
          </Row>
          <Form.Item name="is_default" label="Адрес по умолчанию" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
