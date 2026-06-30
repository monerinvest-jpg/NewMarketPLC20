import { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Typography, Button, Empty, Spin, message } from 'antd'
import { Link, useNavigate } from 'react-router-dom'
import { ShopOutlined, PlusOutlined } from '@ant-design/icons'
import { shopsApi, productsApi } from '@/api'
import type { Shop, Product } from '@/types'
import { Form, Input, Divider } from 'antd'
import RequisitesFields from '@/components/common/RequisitesFields'

const { Title, Text } = Typography

export default function SellerDashboard() {
  const [shop, setShop] = useState<Shop | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [createForm] = Form.useForm()
  const navigate = useNavigate()

  useEffect(() => {
    shopsApi.getMy()
      .then((s) => {
        setShop(s)
        return productsApi.myProducts({ page_size: 5 })
      })
      .then((res) => setProducts(res.items))
      .catch(() => setShop(null))
      .finally(() => setLoading(false))
  }, [])

  const handleCreateShop = async (values: any) => {
    setCreating(true)
    try {
      const { name, description, ...requisites } = values
      const newShop = await shopsApi.create({ name, description, requisites })
      setShop(newShop)
      message.success('Магазин создан и отправлен на модерацию!')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  if (!shop) {
    return (
      <Card style={{ maxWidth: 560, margin: '40px auto' }}>
        <Title level={4}>Создайте свой магазин</Title>
        <Text type="secondary">Для продажи на площадке укажите данные магазина и налоговые реквизиты.</Text>
        <Form layout="vertical" form={createForm} onFinish={handleCreateShop} style={{ marginTop: 16 }}>
          <Form.Item name="name" label="Название магазина" rules={[{ required: true }]}>
            <Input size="large" placeholder="Мой Handmade Магазин" />
          </Form.Item>
          <Form.Item name="description" label="Описание">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Divider>Налоговые реквизиты</Divider>
          <RequisitesFields form={createForm} />
          <Button type="primary" htmlType="submit" size="large" block loading={creating} style={{ marginTop: 8 }}>
            Создать магазин
          </Button>
        </Form>
      </Card>
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          <ShopOutlined /> {shop.name}
        </Title>
        <Link to="/products">
          <Button type="primary" icon={<PlusOutlined />}>Добавить товар</Button>
        </Link>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card><Statistic title="Продаж всего" value={shop.total_sales} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Рейтинг магазина" value={parseFloat(shop.rating)} suffix="/ 5" precision={1} /></Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Ваша комиссия"
              value={shop.commission_percent ? `${shop.commission_percent}%` : 'Глобальная'}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Статус" value={shop.is_active ? 'Активен' : 'Заблокирован'} /></Card>
        </Col>
      </Row>

      <Card title="Последние товары">
        {products.length === 0 ? (
          <Empty description="У вас пока нет товаров">
            <Link to="/products"><Button type="primary">Добавить первый товар</Button></Link>
          </Empty>
        ) : (
          products.map((p) => (
            <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
              <Text>{p.title}</Text>
              <Text>{parseFloat(p.price).toLocaleString('ru')} ₽ — {p.status}</Text>
            </div>
          ))
        )}
      </Card>
    </div>
  )
}
