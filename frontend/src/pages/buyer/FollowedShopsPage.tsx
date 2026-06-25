import { useEffect, useState } from 'react'
import { Row, Col, Card, Typography, Empty, Tag, Avatar, Button, Spin } from 'antd'
import { ShopOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { shopsApi } from '@/api'
import type { Shop, Product } from '@/types'

const { Title, Text } = Typography

function ProductCard({ product }: { product: Product }) {
  const img = product.images?.find((i) => i.is_main) || product.images?.[0]
  return (
    <Link to={`/products/${product.id}`}>
      <Card hoverable styles={{ body: { padding: 12 } }}
        cover={<div style={{ height: 150, background: '#f5f5f5', overflow: 'hidden' }}>
          {img && <img src={img.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
        </div>}>
        <Text ellipsis style={{ display: 'block', fontSize: 13 }}>{product.title}</Text>
        <Text strong style={{ color: '#f97316' }}>{parseFloat(product.price).toLocaleString('ru')} ₽</Text>
      </Card>
    </Link>
  )
}

export default function FollowedShopsPage() {
  const [shops, setShops] = useState<Shop[]>([])
  const [feed, setFeed] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([shopsApi.following(), shopsApi.feed()])
      .then(([s, f]) => { setShops(s); setFeed(f) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
      <Title level={3}>Мои подписки</Title>

      {shops.length === 0 ? (
        <Empty description="Вы пока не подписаны ни на один магазин">
          <Link to="/catalog"><Button type="primary">Перейти в каталог</Button></Link>
        </Empty>
      ) : (
        <>
          <Title level={5}>Магазины <Tag>{shops.length}</Tag></Title>
          <Row gutter={[12, 12]} style={{ marginBottom: 32 }}>
            {shops.map((s) => (
              <Col key={s.id}>
                <Link to={`/shops/${s.id}`}>
                  <Card size="small" hoverable style={{ minWidth: 180 }}>
                    <Card.Meta
                      avatar={<Avatar src={s.logo_url || undefined} icon={<ShopOutlined />} />}
                      title={s.name}
                      description={<Text type="secondary" style={{ fontSize: 12 }}>{s.total_sales} продаж</Text>}
                    />
                  </Card>
                </Link>
              </Col>
            ))}
          </Row>

          <Title level={5}>Новинки от ваших магазинов</Title>
          {feed.length === 0 ? (
            <Empty description="Пока нет новинок" />
          ) : (
            <Row gutter={[16, 16]}>
              {feed.map((p) => (
                <Col xs={12} sm={8} md={6} lg={4} key={p.id}>
                  <ProductCard product={p} />
                </Col>
              ))}
            </Row>
          )}
        </>
      )}
    </div>
  )
}
