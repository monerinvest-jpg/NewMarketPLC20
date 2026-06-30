import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { Row, Col, Card, Typography, Rate, Spin, Empty, Button, Tag, message, Progress, Space, Modal, Form, Input, InputNumber } from 'antd'
import { FlagOutlined, ShopOutlined, CheckCircleFilled, HeartOutlined, HeartFilled } from '@ant-design/icons'
import { shopsApi, productsApi, reviewsApi, customApi } from '@/api'
import type { Shop, Product, ShopRatingSummary } from '@/types'
import { useAuthStore } from '@/store/authStore'
import ReportModal from '@/components/common/ReportModal'

const { Title, Text, Paragraph } = Typography

export default function ShopPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [customModalOpen, setCustomModalOpen] = useState(false)
  const [customForm] = Form.useForm()
  const [shop, setShop] = useState<Shop | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [summary, setSummary] = useState<ShopRatingSummary | null>(null)
  const [follow, setFollow] = useState<{ following: boolean; followers: number }>({ following: false, followers: 0 })
  const [loading, setLoading] = useState(true)
  const [reportModalOpen, setReportModalOpen] = useState(false)
  const [badge, setBadge] = useState<string | null>(null)

  useEffect(() => {
    const shopId = parseInt(id!)
    Promise.all([
      shopsApi.get(shopId),
      productsApi.list({ page_size: 24 }),
    ]).then(([shopData, productsRes]) => {
      setShop(shopData)
      // Filter client-side: the public product listing endpoint doesn't
      // currently support filtering by shop_id, only by category/search.
      setProducts(productsRes.items.filter((p) => p.shop_id === shopId))
    }).catch(() => message.error('Магазин не найден'))
      .finally(() => setLoading(false))
    reviewsApi.shopSummary(shopId).then(setSummary).catch(() => {})
    shopsApi.badge(shopId).then((r) => setBadge(r.badge)).catch(() => {})
    if (user) shopsApi.followStatus(shopId).then(setFollow).catch(() => {})
  }, [id])

  const toggleFollow = async () => {
    if (!user) { message.info('Войдите, чтобы подписаться на магазин'); return }
    const shopId = parseInt(id!)
    const res = follow.following ? await shopsApi.unfollow(shopId) : await shopsApi.follow(shopId)
    setFollow(res)
    message.success(res.following ? 'Вы подписались на магазин' : 'Вы отписались')
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
  if (!shop) return <Empty description="Магазин не найден" />

  return (
    <div>
      {shop.banner_url && (
        <div style={{
          height: 180, borderRadius: 12, marginBottom: 16, overflow: 'hidden',
          background: `url(${shop.banner_url}) center/cover`,
        }} />
      )}
      <Card style={{ marginBottom: 24, borderTop: `3px solid ${shop.accent_color || '#f97316'}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            {shop.logo_url ? (
              <img src={shop.logo_url} alt={shop.name} style={{ width: 64, height: 64, borderRadius: 12, objectFit: 'cover' }} />
            ) : (
              <div style={{
                width: 64, height: 64, borderRadius: 12, background: `${shop.accent_color || '#f97316'}22`,
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28,
              }}>
                <ShopOutlined style={{ color: shop.accent_color || '#f97316' }} />
              </div>
            )}
            <div>
              <Title level={3} style={{ margin: 0 }}>
                {shop.name}{' '}
                {badge === 'vip' && <Tag color="gold">★ VIP</Tag>}
                {badge === 'verified' && <Tag color="green">✓ Проверенный</Tag>}
              </Title>
              {shop.tagline && <Text type="secondary">{shop.tagline}</Text>}
              {(summary && summary.reviews_count > 0) ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <Rate disabled value={summary.rating} allowHalf style={{ fontSize: 14 }} />
                  <Text strong>{summary.rating.toFixed(1)}</Text>
                  <Text type="secondary">· {summary.reviews_count} отзывов · {shop.total_sales} продаж</Text>
                </div>
              ) : (
                <div><Text type="secondary">{shop.total_sales} продаж · пока нет отзывов</Text></div>
              )}
            </div>
          </div>
          <Space>
            <Button
              type={follow.following ? 'default' : 'primary'}
              icon={follow.following ? <HeartFilled /> : <HeartOutlined />}
              onClick={toggleFollow}
            >
              {follow.following ? 'Вы подписаны' : 'Подписаться'}
              {follow.followers > 0 && ` · ${follow.followers}`}
            </Button>
            <Button
              icon={<FlagOutlined />}
              onClick={() => {
                if (!user) { message.info('Войдите, чтобы отправить жалобу'); return }
                setReportModalOpen(true)
              }}
            >
              Пожаловаться
            </Button>
            <Button type="primary" ghost onClick={() => {
              if (!user) { message.info('Войдите, чтобы заказать изготовление'); return }
              setCustomModalOpen(true)
            }}>
              ✨ Заказать своё
            </Button>
          </Space>
        </div>
        {shop.description && (
          <Paragraph style={{ marginTop: 16, marginBottom: 0 }}>{shop.description}</Paragraph>
        )}
        {(shop.contact_email || shop.contact_phone) && (
          <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
            {shop.contact_email && <>✉ {shop.contact_email}  </>}
            {shop.contact_phone && <>☎ {shop.contact_phone}</>}
          </Text>
        )}
      </Card>

      {summary && summary.reviews_count > 0 && (
        <Card title="Рейтинг продавца" style={{ marginBottom: 24 }}>
          <Row gutter={24} align="middle">
            <Col xs={24} sm={8} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 44, fontWeight: 700, lineHeight: 1 }}>{summary.rating.toFixed(1)}</div>
              <Rate disabled value={summary.rating} allowHalf style={{ fontSize: 16 }} />
              <div style={{ marginTop: 8 }}>
                <Text type="secondary">{summary.reviews_count} отзывов</Text>
              </div>
              {summary.verified_count > 0 && (
                <Tag color="green" icon={<CheckCircleFilled />} style={{ marginTop: 8 }}>
                  {summary.verified_count} проверенных покупок
                </Tag>
              )}
            </Col>
            <Col xs={24} sm={16}>
              {[5, 4, 3, 2, 1].map((star) => {
                const cnt = summary.distribution[String(star)] || 0
                const pct = summary.reviews_count ? Math.round((cnt / summary.reviews_count) * 100) : 0
                return (
                  <div key={star} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Text style={{ width: 28 }}>{star}★</Text>
                    <Progress percent={pct} showInfo={false} strokeColor="#f97316" style={{ flex: 1, margin: 0 }} />
                    <Text type="secondary" style={{ width: 36, textAlign: 'right' }}>{cnt}</Text>
                  </div>
                )
              })}
            </Col>
          </Row>
        </Card>
      )}

      <Title level={4}>Товары магазина ({products.length})</Title>
      {products.length === 0 ? (
        <Empty description="В этом магазине пока нет товаров" />
      ) : (
        <Row gutter={[16, 16]}>
          {products.map((p) => {
            const img = p.images.find((i) => i.is_main) || p.images[0]
            return (
              <Col key={p.id} xs={24} sm={12} md={8} lg={6}>
                <Link to={`/products/${p.id}`}>
                  <Card
                    hoverable
                    cover={
                      <div style={{ height: 180, background: '#f5f5f5', overflow: 'hidden' }}>
                        {img && <img src={img.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
                      </div>
                    }
                  >
                    <Text ellipsis style={{ display: 'block' }}>{p.title}</Text>
                    <Text strong style={{ color: '#f97316' }}>{parseFloat(p.price).toLocaleString('ru')} ₽</Text>
                  </Card>
                </Link>
              </Col>
            )
          })}
        </Row>
      )}

      <ReportModal
        open={reportModalOpen}
        onClose={() => setReportModalOpen(false)}
        targetType="shop"
        targetId={shop.id}
        targetLabel={shop.name}
      />

      <Modal
        title={`Индивидуальный заказ · ${shop.name}`}
        open={customModalOpen}
        onCancel={() => setCustomModalOpen(false)}
        okText="Отправить запрос"
        onOk={async () => {
          const v = await customForm.validateFields()
          try {
            await customApi.create({ shop_id: shop.id, title: v.title, description: v.description, budget: v.budget })
            message.success('Запрос отправлен мастеру')
            setCustomModalOpen(false); customForm.resetFields()
            navigate('/custom-requests')
          } catch (e: any) {
            message.error(e.response?.data?.detail || 'Ошибка')
          }
        }}
      >
        <Paragraph type="secondary">Опишите, что хотите изготовить — мастер пришлёт оферту с ценой и сроком.</Paragraph>
        <Form form={customForm} layout="vertical">
          <Form.Item name="title" label="Что нужно изготовить" rules={[{ required: true }]}>
            <Input placeholder="Напр.: деревянная шкатулка с гравировкой" />
          </Form.Item>
          <Form.Item name="description" label="Детали (размеры, материалы, пожелания)" rules={[{ required: true }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="budget" label="Бюджет, ₽ (необязательно)">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
