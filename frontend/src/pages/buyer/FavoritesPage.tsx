import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Row, Col, Card, Typography, Empty, Spin, Button, message } from 'antd'
import { HeartFilled } from '@ant-design/icons'
import { favoritesApi } from '@/api'
import type { Product } from '@/types'

const { Text } = Typography

export default function FavoritesPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    favoritesApi.list().then(setProducts).finally(() => setLoading(false))
  }, [])

  const handleRemove = async (id: number) => {
    await favoritesApi.remove(id)
    setProducts(products.filter((p) => p.id !== id))
    message.success('Удалено из избранного')
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (products.length === 0) return <Empty description="Список избранного пуст" style={{ margin: 80 }} />

  return (
    <div>
      <Typography.Title level={3}>Избранное</Typography.Title>
      <Row gutter={[16, 16]}>
        {products.map((p) => {
          const img = p.images.find((i) => i.is_main) || p.images[0]
          return (
            <Col key={p.id} xs={24} sm={12} md={8} lg={6}>
              <Card
                hoverable
                cover={
                  <Link to={`/products/${p.id}`}>
                    <div style={{ height: 180, background: '#f5f5f5', overflow: 'hidden' }}>
                      {img && <img src={img.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
                    </div>
                  </Link>
                }
                actions={[
                  <Button key="remove" type="text" danger icon={<HeartFilled />} onClick={() => handleRemove(p.id)}>
                    Убрать
                  </Button>
                ]}
              >
                <Link to={`/products/${p.id}`}>
                  <Text ellipsis style={{ display: 'block' }}>{p.title}</Text>
                </Link>
                <Text strong style={{ color: '#f97316' }}>{parseFloat(p.price).toLocaleString('ru')} ₽</Text>
              </Card>
            </Col>
          )
        })}
      </Row>
    </div>
  )
}
