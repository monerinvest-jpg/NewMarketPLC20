import { Row, Col, Card, Typography } from 'antd'
import { Link } from 'react-router-dom'
import type { Product } from '@/types'

const { Title, Text } = Typography

/**
 * A horizontal row of product recommendation cards. Renders nothing when there
 * are no products, so callers can drop it in unconditionally.
 */
export default function RecommendationRow({
  title, products, max = 6,
}: { title: string; products: Product[]; max?: number }) {
  if (!products || products.length === 0) return null
  return (
    <div style={{ marginTop: 32 }}>
      <Title level={4}>{title}</Title>
      <Row gutter={[16, 16]}>
        {products.slice(0, max).map((p) => {
          const img = p.images?.find((i) => i.is_main) || p.images?.[0]
          return (
            <Col key={p.id} xs={12} sm={8} md={6} lg={4}>
              <Link to={`/products/${p.id}`}>
                <Card
                  hoverable
                  styles={{ body: { padding: 12 } }}
                  cover={
                    <div style={{ height: 150, overflow: 'hidden', background: '#f5f5f5' }}>
                      {img && <img src={img.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
                    </div>
                  }
                >
                  <Text ellipsis style={{ display: 'block', fontSize: 13, marginBottom: 4 }}>{p.title}</Text>
                  <Text strong style={{ color: '#b45309' }}>{parseFloat(p.price).toLocaleString('ru')} ₽</Text>
                </Card>
              </Link>
            </Col>
          )
        })}
      </Row>
    </div>
  )
}
