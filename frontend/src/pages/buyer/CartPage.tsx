import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Table, Button, InputNumber, Typography, Card, Image,
  Empty, Divider, Space, message, Popconfirm
} from 'antd'
import { DeleteOutlined, ShoppingOutlined } from '@ant-design/icons'
import { useCartStore } from '@/store/cartStore'
import { useAuthStore } from '@/store/authStore'
import { recommendationsApi, promoRulesApi } from '@/api'
import RecommendationRow from '@/components/common/RecommendationRow'
import type { Product, CartPromoSummary } from '@/types'

const { Title, Text } = Typography

export default function CartPage() {
  const { items, loading, fetchCart, updateItem, removeItem, totalPrice } = useCartStore()
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [recs, setRecs] = useState<Product[]>([])
  const [promo, setPromo] = useState<CartPromoSummary | null>(null)

  useEffect(() => { fetchCart() }, [user])

  useEffect(() => {
    const ids = items.map((i) => i.product_id)
    if (ids.length > 0) {
      recommendationsApi.forCart(ids).then(setRecs).catch(() => {})
      // Promo rules evaluate the SERVER cart — meaningless for a guest's local cart.
      if (user) promoRulesApi.cartSummary().then(setPromo).catch(() => {})
    } else {
      setRecs([])
      setPromo(null)
    }
  }, [items, user])

  const handleCheckout = () => {
    if (!user) {
      message.info('Войдите, чтобы оформить заказ — корзина сохранится')
      navigate('/login')
      return
    }
    navigate('/checkout')
  }

  if (loading) return null

  if (items.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Empty description="Корзина пуста">
          <Link to="/catalog"><Button type="primary">Перейти в каталог</Button></Link>
        </Empty>
      </div>
    )
  }

  return (
    <div>
      <Title level={3}>Корзина ({items.length})</Title>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24 }}>
        <div>
          {items.map((item) => {
            const img = item.product.images.find((i) => i.is_main) || item.product.images[0]
            return (
              <Card key={item.id} style={{ marginBottom: 12 }} bodyStyle={{ padding: 16 }}>
                <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                  <Link to={`/products/${item.product_id}`}>
                    {img ? (
                      <img src={img.url} alt="" style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 8 }} />
                    ) : (
                      <div style={{ width: 80, height: 80, background: '#f5f5f5', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>🛍️</div>
                    )}
                  </Link>
                  <div style={{ flex: 1 }}>
                    <Link to={`/products/${item.product_id}`}>
                      <Text strong>{item.product.title}</Text>
                    </Link>
                    <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 16 }}>
                      <InputNumber
                        min={1} max={item.product.quantity}
                        value={item.quantity}
                        onChange={(v) => v && updateItem(item.id, v)}
                        size="small"
                      />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        × {parseFloat(item.product.price).toLocaleString('ru')} ₽
                      </Text>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <Text strong style={{ color: '#b45309', fontSize: 18 }}>
                      {(parseFloat(item.product.price) * item.quantity).toLocaleString('ru')} ₽
                    </Text>
                    <br />
                    <Popconfirm title="Удалить из корзины?" onConfirm={() => removeItem(item.id)}>
                      <Button type="text" danger size="small" icon={<DeleteOutlined />} style={{ marginTop: 4 }} />
                    </Popconfirm>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>

        {/* Order summary */}
        <Card title="Итого">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <Text>Товары ({items.length}):</Text>
            <Text>{totalPrice().toLocaleString('ru')} ₽</Text>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
            <Text>Доставка:</Text>
            <Text type="secondary">рассчитается при оформлении</Text>
          </div>
          <Divider />
          {promo && Number(promo.promo_discount) > 0 && (
            <>
              {promo.breakdown.map((b, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <Text type="secondary" style={{ fontSize: 13 }}>{b.label}</Text>
                  <Text type="success" style={{ fontSize: 13 }}>−{Number(b.amount).toLocaleString('ru')} ₽</Text>
                </div>
              ))}
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <Text strong>Скидка по акциям:</Text>
                <Text strong type="success">−{Number(promo.promo_discount).toLocaleString('ru')} ₽</Text>
              </div>
            </>
          )}
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
            <Text strong style={{ fontSize: 18 }}>Итого:</Text>
            <Text strong style={{ fontSize: 18, color: '#b45309' }}>
              {(promo ? Number(promo.estimated_total) : totalPrice()).toLocaleString('ru')} ₽
            </Text>
          </div>
          <Button
            type="primary" size="large" block icon={<ShoppingOutlined />}
            onClick={handleCheckout}
          >
            {user ? 'Оформить заказ' : 'Войти и оформить заказ'}
          </Button>
        </Card>
      </div>

      <RecommendationRow title="С этими товарами часто покупают" products={recs} />
    </div>
  )
}
