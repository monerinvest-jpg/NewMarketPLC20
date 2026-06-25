import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, Button, Modal, Form, Input, Switch, message, Typography, Empty, Spin, Row, Col, Popconfirm, Tag, Image } from 'antd'
import { PlusOutlined, HeartOutlined } from '@ant-design/icons'
import { wishlistApi } from '@/api'
import type { WishlistCollectionBrief, WishlistCollection } from '@/types'

const { Title, Text } = Typography

export default function WishlistsPage() {
  const [collections, setCollections] = useState<WishlistCollectionBrief[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [openCollection, setOpenCollection] = useState<WishlistCollection | null>(null)

  const load = () => {
    setLoading(true)
    wishlistApi.list().then(setCollections).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const handleCreate = async (values: any) => {
    try {
      await wishlistApi.create(values.name, values.is_public)
      message.success('Коллекция создана')
      setModalOpen(false)
      form.resetFields()
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const handleDelete = async (id: number) => {
    await wishlistApi.remove(id)
    message.success('Коллекция удалена')
    load()
  }

  const viewCollection = async (id: number) => {
    const col = await wishlistApi.get(id)
    setOpenCollection(col)
  }

  const removeItem = async (productId: number) => {
    if (!openCollection) return
    await wishlistApi.removeItem(openCollection.id, productId)
    const updated = await wishlistApi.get(openCollection.id)
    setOpenCollection(updated)
    load()
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}><HeartOutlined /> Мои коллекции</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>Создать коллекцию</Button>
      </div>

      {collections.length === 0 ? (
        <Empty description="Создайте коллекцию, чтобы собирать товары — например, «На день рождения»" />
      ) : (
        <Row gutter={[16, 16]}>
          {collections.map((c) => (
            <Col xs={24} sm={12} md={8} key={c.id}>
              <Card
                hoverable
                title={<>{c.name} {c.is_public && <Tag color="blue">Публичная</Tag>}</>}
                extra={
                  <Popconfirm title="Удалить коллекцию?" onConfirm={() => handleDelete(c.id)}>
                    <Button type="link" size="small" danger>Удалить</Button>
                  </Popconfirm>
                }
                onClick={() => viewCollection(c.id)}
              >
                <Text type="secondary">{c.item_count} товаров</Text>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal title="Новая коллекция" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()} okText="Создать">
        <Form form={form} layout="vertical" onFinish={handleCreate} initialValues={{ is_public: false }}>
          <Form.Item name="name" label="Название" rules={[{ required: true }]}>
            <Input placeholder="На день рождения" />
          </Form.Item>
          <Form.Item name="is_public" label="Публичная (доступна по ссылке)" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={openCollection?.name}
        open={!!openCollection}
        onCancel={() => setOpenCollection(null)}
        footer={null}
        width={720}
      >
        {openCollection && openCollection.items.length === 0 ? (
          <Empty description="В коллекции пока нет товаров" />
        ) : (
          <Row gutter={[12, 12]}>
            {openCollection?.items.map((item) => {
              const img = item.product.images?.find((i) => i.is_main) || item.product.images?.[0]
              return (
                <Col xs={12} md={8} key={item.id}>
                  <Card
                    size="small"
                    cover={img ? <Image src={img.url} height={120} style={{ objectFit: 'cover' }} preview={false} /> : undefined}
                    actions={[<Button type="link" danger size="small" onClick={() => removeItem(item.product_id)}>Убрать</Button>]}
                  >
                    <Link to={`/products/${item.product_id}`}>
                      <Text ellipsis style={{ fontSize: 13 }}>{item.product.title}</Text>
                    </Link>
                    <div><Text strong style={{ color: '#f97316' }}>{parseFloat(item.product.price).toLocaleString('ru')} ₽</Text></div>
                  </Card>
                </Col>
              )
            })}
          </Row>
        )}
      </Modal>
    </div>
  )
}
