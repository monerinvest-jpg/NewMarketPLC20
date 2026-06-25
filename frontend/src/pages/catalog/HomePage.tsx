import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Row, Col, Card, Typography, Button, Spin, Tag } from 'antd'
import { ShoppingCartOutlined, ArrowRightOutlined } from '@ant-design/icons'
import { productsApi, categoriesApi, homeApi } from '@/api'
import type { Product, Category } from '@/types'
import { useCartStore } from '@/store/cartStore'
import { useAuthStore } from '@/store/authStore'
import { message } from 'antd'

const { Title, Text } = Typography

function ProductCard({ product }: { product: Product }) {
  const { addItem } = useCartStore()
  const { user } = useAuthStore()
  const mainImage = product.images.find((i) => i.is_main) || product.images[0]

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.preventDefault()
    if (!user) { message.info('Войдите, чтобы добавить в корзину'); return }
    try {
      await addItem(product.id)
      message.success('Добавлено в корзину')
    } catch {
      message.error('Ошибка добавления в корзину')
    }
  }

  return (
    <Link to={`/products/${product.id}`}>
      <Card
        hoverable
        className="product-card"
        cover={
          <div style={{ height: 200, overflow: 'hidden', background: '#f5f5f5' }}>
            {mainImage ? (
              <img
                src={mainImage.url}
                alt={product.title}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: 48 }}>
                🛍️
              </div>
            )}
          </div>
        }
        bodyStyle={{ padding: '12px 16px' }}
      >
        <Text ellipsis style={{ display: 'block', marginBottom: 4 }}>{product.title}</Text>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <Text strong style={{ fontSize: 18, color: '#f97316' }}>
              {parseFloat(product.price).toLocaleString('ru')} ₽
            </Text>
            {product.compare_at_price && (
              <Text delete type="secondary" style={{ marginLeft: 8, fontSize: 13 }}>
                {parseFloat(product.compare_at_price).toLocaleString('ru')} ₽
              </Text>
            )}
          </div>
          <Button
            type="primary" size="small" icon={<ShoppingCartOutlined />}
            onClick={handleAddToCart}
          />
        </div>
        {product.rating > 0 && (
          <div style={{ marginTop: 4 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              ⭐ {product.rating} ({product.reviews_count})
            </Text>
          </div>
        )}
      </Card>
    </Link>
  )
}

export default function HomePage() {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [banners, setBanners] = useState<any[]>([])
  const [promoted, setPromoted] = useState<{ promotion_id: number; product: Product }[]>([])
  const [recentlyViewed, setRecentlyViewed] = useState<Product[]>([])
  const [recommended, setRecommended] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const { user } = useAuthStore()

  useEffect(() => {
    Promise.all([
      productsApi.list({ page_size: 8, sort: 'views_desc' }),
      categoriesApi.list(),
      homeApi.banners().catch(() => []),
    ]).then(([pRes, cats, bnrs]) => {
      setProducts(pRes.items)
      setCategories(cats)
      setBanners(bnrs)
    }).finally(() => setLoading(false))
    import('@/api').then(({ promotionsApi }) =>
      promotionsApi.homepage().then((items) => {
        setPromoted(items)
        // Report impressions for the shown promoted cards.
        items.forEach((it) => promotionsApi.recordEvent(it.promotion_id, 'impression'))
      }).catch(() => {}))
  }, [])

  useEffect(() => {
    if (user) {
      import('@/api').then(({ historyApi, recommendationsApi }) => {
        historyApi.recentlyViewed().then(setRecentlyViewed).catch(() => {})
        recommendationsApi.forMe().then(setRecommended).catch(() => {})
      })
    } else {
      setRecentlyViewed([])
      setRecommended([])
    }
  }, [user])

  if (loading) return <Spin size="large" style={{ display: 'block', textAlign: 'center', margin: 80 }} />

  return (
    <div>
      {/* Admin-managed promotional banners */}
      {banners.length > 0 && (
        <div style={{ display: 'flex', gap: 16, overflowX: 'auto', marginBottom: 24 }}>
          {banners.map((b) => {
            const content = (
              <div style={{
                minWidth: 320, height: 160, borderRadius: 12, overflow: 'hidden',
                background: `url(${b.image_url}) center/cover`, position: 'relative', cursor: b.link ? 'pointer' : 'default',
              }}>
                <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: 16, background: 'linear-gradient(transparent, rgba(0,0,0,0.6))' }}>
                  <Text style={{ color: '#fff', fontSize: 18, fontWeight: 600, display: 'block' }}>{b.title}</Text>
                  {b.subtitle && <Text style={{ color: 'rgba(255,255,255,0.9)' }}>{b.subtitle}</Text>}
                </div>
              </div>
            )
            return b.link
              ? <Link key={b.id} to={b.link}>{content}</Link>
              : <div key={b.id}>{content}</div>
          })}
        </div>
      )}

      {/* Hero banner */}
      <div style={{
        background: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
        borderRadius: 16, padding: '48px 40px', marginBottom: 40, color: '#fff',
      }}>
        <Title level={1} style={{ color: '#fff', margin: 0 }}>
          Уникальные товары от лучших мастеров
        </Title>
        <Text style={{ color: 'rgba(255,255,255,0.9)', fontSize: 18, display: 'block', margin: '12px 0 24px' }}>
          Handmade, эксклюзив и всё что делает жизнь лучше
        </Text>
        <Link to="/catalog">
          <Button size="large" style={{ background: '#fff', color: '#f97316', border: 'none', fontWeight: 600 }}>
            Перейти в каталог <ArrowRightOutlined />
          </Button>
        </Link>
      </div>

      {/* Recently viewed (logged-in only) */}
      {recentlyViewed.length > 0 && (
        <>
          <Title level={3}>Вы недавно смотрели</Title>
          <Row gutter={[16, 16]} style={{ marginBottom: 40 }}>
            {recentlyViewed.slice(0, 6).map((p) => (
              <Col xs={12} sm={8} md={4} key={p.id}>
                <ProductCard product={p} />
              </Col>
            ))}
          </Row>
        </>
      )}

      {/* Recommended for you (logged-in, based on purchase history) */}
      {recommended.length > 0 && (
        <>
          <Title level={3}>Рекомендуем вам</Title>
          <Row gutter={[16, 16]} style={{ marginBottom: 40 }}>
            {recommended.slice(0, 6).map((p) => (
              <Col xs={12} sm={8} md={4} key={p.id}>
                <ProductCard product={p} />
              </Col>
            ))}
          </Row>
        </>
      )}

      {/* Promoted (homepage auction winners) */}
      {promoted.length > 0 && (
        <>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <Title level={3} style={{ marginBottom: 8 }}>Рекомендуемые товары</Title>
            <Text type="secondary" style={{ fontSize: 12 }}>Реклама</Text>
          </div>
          <Row gutter={[16, 16]} style={{ marginBottom: 40 }}>
            {promoted.map((it) => (
              <Col xs={12} sm={8} md={4} key={it.promotion_id}
                onClick={() => import('@/api').then(({ promotionsApi }) => promotionsApi.recordEvent(it.promotion_id, 'click'))}>
                <ProductCard product={it.product} />
              </Col>
            ))}
          </Row>
        </>
      )}

      {/* Categories */}
      <Title level={3}>Категории</Title>
      <Row gutter={[12, 12]} style={{ marginBottom: 40 }}>
        {categories.map((cat) => (
          <Col key={cat.id}>
            <Link to={`/catalog?category_id=${cat.id}`}>
              <Tag
                style={{
                  padding: '8px 16px', fontSize: 14, cursor: 'pointer',
                  border: '1px solid #f97316', color: '#f97316', background: '#fff7ed',
                  borderRadius: 20,
                }}
              >
                {cat.name}
              </Tag>
            </Link>
          </Col>
        ))}
      </Row>

      {/* Popular products */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <Title level={3} style={{ margin: 0 }}>Популярные товары</Title>
        <Link to="/catalog">
          <Button type="link">Все товары <ArrowRightOutlined /></Button>
        </Link>
      </div>
      <Row gutter={[16, 16]}>
        {products.map((p) => (
          <Col key={p.id} xs={24} sm={12} md={8} lg={6}>
            <ProductCard product={p} />
          </Col>
        ))}
      </Row>
    </div>
  )
}
