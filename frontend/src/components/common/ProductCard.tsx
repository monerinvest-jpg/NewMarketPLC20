import { Link } from 'react-router-dom'
import { Card, Typography, Button, Rate, Tag, Skeleton, Row, Col, message } from 'antd'
import { ShoppingCartOutlined, HeartOutlined, HeartFilled, SwapOutlined } from '@ant-design/icons'
import type { Product } from '@/types'
import { useCartStore } from '@/store/cartStore'
import { useAuthStore } from '@/store/authStore'
import { useFavoritesStore } from '@/store/favoritesStore'
import { useCompareStore } from '@/store/compareStore'

const { Text } = Typography

// Single product card used across the storefront (home, catalog, rec rows) —
// one look everywhere: discount badge, favorite heart, compare, stars, price.
export default function ProductCard({ product, coverHeight = 190 }: { product: Product; coverHeight?: number }) {
  const { addItem } = useCartStore()
  const { user } = useAuthStore()
  const favorites = useFavoritesStore()
  const compare = useCompareStore()

  const mainImage = product.images.find((i) => i.is_main) || product.images[0]
  const isFav = favorites.has(product.id)

  const price = parseFloat(product.flash_price || product.price)
  const oldPrice = product.flash_price
    ? parseFloat(product.price)
    : product.compare_at_price
      ? parseFloat(product.compare_at_price)
      : null
  const discount = oldPrice && oldPrice > price ? Math.round((1 - price / oldPrice) * 100) : 0

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.preventDefault()
    try {
      await addItem(product.id)
      message.success('Добавлено в корзину')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Ошибка добавления в корзину')
    }
  }

  const handleFavorite = async (e: React.MouseEvent) => {
    e.preventDefault()
    if (!user) { message.info('Войдите, чтобы добавить в избранное'); return }
    const nowFav = await favorites.toggle(product.id)
    message.success(nowFav ? 'Добавлено в избранное' : 'Убрано из избранного')
  }

  const handleCompare = (e: React.MouseEvent) => {
    e.preventDefault()
    compare.toggle(product)
    message.success(compare.has(product.id) ? 'Убрано из сравнения' : 'Добавлено к сравнению')
  }

  return (
    <Link to={`/products/${product.id}`}>
      <Card
        hoverable
        className="product-card"
        style={{ position: 'relative', height: '100%' }}
        cover={
          <div style={{ height: coverHeight, overflow: 'hidden', background: '#f5f1ea', position: 'relative' }}>
            {mainImage ? (
              <img
                src={mainImage.url}
                alt={product.title}
                loading="lazy"
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: 42 }}>
                🪵
              </div>
            )}
            {discount > 0 && (
              <Tag color="red" style={{ position: 'absolute', top: 8, left: 8, margin: 0, fontWeight: 600 }}>
                −{discount}%
              </Tag>
            )}
          </div>
        }
        bodyStyle={{ padding: '12px 14px' }}
      >
        {/* Overlay actions: favorite + compare */}
        <div style={{ position: 'absolute', top: 8, right: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Button
            size="small" type="text" aria-label="В избранное"
            icon={isFav ? <HeartFilled style={{ color: '#cf1322' }} /> : <HeartOutlined />}
            style={{ background: 'rgba(255,255,255,0.9)' }}
            onClick={handleFavorite}
          />
          <Button
            size="small" type="text" aria-label="Сравнить"
            icon={<SwapOutlined style={compare.has(product.id) ? { color: '#b45309' } : undefined} />}
            style={{ background: 'rgba(255,255,255,0.9)' }}
            onClick={handleCompare}
          />
        </div>

        <Text ellipsis={{ tooltip: product.title }} style={{ display: 'block', marginBottom: 4 }}>
          {product.title}
        </Text>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <div style={{ minWidth: 0 }}>
            <Text strong style={{ fontSize: 17, color: product.flash_price ? '#cf1322' : '#b45309' }}>
              {price.toLocaleString('ru')} ₽
            </Text>
            {oldPrice && oldPrice > price && (
              <Text delete type="secondary" style={{ marginLeft: 6, fontSize: 12 }}>
                {oldPrice.toLocaleString('ru')} ₽
              </Text>
            )}
          </div>
          <Button
            type="primary" size="small" icon={<ShoppingCartOutlined />} aria-label="В корзину"
            onClick={handleAddToCart}
          />
        </div>
        {Number(product.rating) > 0 && (
          <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Rate disabled allowHalf defaultValue={Number(product.rating)} style={{ fontSize: 11 }} />
            <Text type="secondary" style={{ fontSize: 12 }}>({product.reviews_count})</Text>
          </div>
        )}
      </Card>
    </Link>
  )
}

// Loading placeholder that mirrors the product grid — no layout jump, no
// full-page spinner.
export function ProductGridSkeleton({ count = 8, colProps }: { count?: number; colProps?: object }) {
  return (
    <Row gutter={[16, 16]}>
      {Array.from({ length: count }).map((_, i) => (
        <Col key={i} xs={12} sm={12} md={8} lg={6} {...(colProps || {})}>
          <Card cover={<Skeleton.Image active style={{ width: '100%', height: 190 }} />}>
            <Skeleton active paragraph={{ rows: 2 }} title={false} />
          </Card>
        </Col>
      ))}
    </Row>
  )
}
