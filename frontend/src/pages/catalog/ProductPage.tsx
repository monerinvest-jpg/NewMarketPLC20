import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Row, Col, Image, Button, Rate, Typography, Tabs, InputNumber,
  Spin, message, Form, Input, List, Avatar, Empty, Card, Radio, Modal, Tag, Checkbox
} from 'antd'
import {
  ShoppingCartOutlined, HeartOutlined, HeartFilled, LikeOutlined,
  LikeFilled, FlagOutlined, SwapOutlined, PlusOutlined, FolderAddOutlined,
  CheckCircleFilled
} from '@ant-design/icons'
import {
  productsApi, reviewsApi, favoritesApi, variantsApi,
  questionsApi, recommendationsApi, chatApi, productSubsApi, promoRulesApi
} from '@/api'
import type { Product, Review, ProductVariant, ProductQuestion } from '@/types'
import { useCartStore } from '@/store/cartStore'
import { useAuthStore } from '@/store/authStore'
import { useCompareStore } from '@/store/compareStore'
import ReportModal from '@/components/common/ReportModal'
import dayjs from 'dayjs'

const { Title, Text, Paragraph } = Typography

export default function ProductPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuthStore()
  const { addItem } = useCartStore()
  const compare = useCompareStore()

  const [product, setProduct] = useState<Product | null>(null)
  const [reviews, setReviews] = useState<Review[]>([])
  const [bundles, setBundles] = useState<any[]>([])
  const [verifiedOnly, setVerifiedOnly] = useState(false)
  const [variants, setVariants] = useState<ProductVariant[]>([])
  const [selectedVariant, setSelectedVariant] = useState<number | null>(null)
  const [questions, setQuestions] = useState<ProductQuestion[]>([])
  const [recommendations, setRecommendations] = useState<Product[]>([])
  const [isFavorite, setIsFavorite] = useState(false)
  const [quantity, setQuantity] = useState(1)
  const [reportModalOpen, setReportModalOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [selectedImage, setSelectedImage] = useState<string>('')
  const [reviewPhotos, setReviewPhotos] = useState<string[]>([])
  const [questionText, setQuestionText] = useState('')
  const [wishlistModalOpen, setWishlistModalOpen] = useState(false)
  const [wishlistCollections, setWishlistCollections] = useState<{ id: number; name: string; item_count: number }[]>([])
  const [form] = Form.useForm()

  const reloadReviews = (verified: boolean) => {
    setVerifiedOnly(verified)
    reviewsApi.list(parseInt(id!), { page: 1, verified_only: verified })
      .then((res) => setReviews(res.items))
      .catch(() => {})
  }

  const load = async () => {
    setLoading(true)
    try {
      const pid = parseInt(id!)
      const [p, reviewsRes, v, q, recs] = await Promise.all([
        productsApi.get(pid),
        reviewsApi.list(pid, { page: 1 }),
        variantsApi.list(pid).catch(() => []),
        questionsApi.list(pid).catch(() => []),
        recommendationsApi.forProduct(pid).catch(() => []),
      ])
      setProduct(p)
      setReviews(reviewsRes.items)
      setVariants(v)
      if (v.length > 0) setSelectedVariant(v[0].id)
      setQuestions(q)
      setRecommendations(recs)
      promoRulesApi.productBundles(pid).then(setBundles).catch(() => {})
      const img = p.images.find((i) => i.is_main) || p.images[0]
      setSelectedImage(img?.url || '')
      if (user) {
        const favs = await favoritesApi.list().catch(() => [])
        setIsFavorite(favs.some((f: any) => f.id === pid || f.product_id === pid))
      }
    } catch {
      message.error('Не удалось загрузить товар')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  const currentPrice = (() => {
    if (!product) return 0
    if (selectedVariant) {
      const v = variants.find((x) => x.id === selectedVariant)
      if (v?.price) return parseFloat(v.price)
    }
    return parseFloat(product.price)
  })()

  const handleAddToCart = async () => {
    if (!user) { message.info('Войдите, чтобы добавить в корзину'); return }
    if (variants.length > 0 && !selectedVariant) { message.warning('Выберите вариант товара'); return }
    try {
      await addItem(parseInt(id!), quantity, selectedVariant || undefined)
      message.success('Добавлено в корзину!')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const handleFavorite = async () => {
    if (!user) { message.info('Войдите, чтобы добавить в избранное'); return }
    if (isFavorite) {
      await favoritesApi.remove(parseInt(id!))
      setIsFavorite(false)
    } else {
      await favoritesApi.add(parseInt(id!))
      setIsFavorite(true)
    }
  }

  const openWishlistModal = async () => {
    if (!user) { message.info('Войдите, чтобы добавить в коллекцию'); return }
    const { wishlistApi } = await import('@/api')
    const cols = await wishlistApi.list()
    setWishlistCollections(cols)
    setWishlistModalOpen(true)
  }

  const addToCollection = async (collectionId: number) => {
    if (!product) return
    const { wishlistApi } = await import('@/api')
    await wishlistApi.addItem(collectionId, product.id)
    message.success('Добавлено в коллекцию')
    setWishlistModalOpen(false)
  }

  const createAndAdd = async (name: string) => {
    if (!product || !name.trim()) return
    const { wishlistApi } = await import('@/api')
    const col = await wishlistApi.create(name.trim())
    await wishlistApi.addItem(col.id, product.id)
    message.success('Коллекция создана, товар добавлен')
    setWishlistModalOpen(false)
  }

  const handleChat = async () => {
    if (!user) { message.info('Войдите, чтобы написать продавцу'); return }
    if (!product) return
    const text = prompt('Сообщение продавцу:')
    if (!text) return
    try {
      await chatApi.start(product.shop_id, text)
      message.success('Сообщение отправлено! Ответ придёт в раздел «Сообщения»')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const handleReview = async (values: { rating: number; text: string }) => {
    setReviewLoading(true)
    try {
      const review = await reviewsApi.create(parseInt(id!), { ...values, photos: reviewPhotos })
      if (review.status === 'approved') {
        setReviews([review, ...reviews])
        message.success('Отзыв опубликован')
      } else {
        message.success('Отзыв отправлен на модерацию и появится после проверки')
      }
      form.resetFields()
      setReviewPhotos([])
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    } finally {
      setReviewLoading(false)
    }
  }

  const handleVote = async (reviewId: number) => {
    if (!user) { message.info('Войдите, чтобы оценить отзыв'); return }
    try {
      const result = await reviewsApi.vote(reviewId)
      setReviews(reviews.map((r) =>
        r.id === reviewId ? { ...r, helpful_count: result.helpful_count, voted_by_me: result.voted } : r
      ))
    } catch {
      message.error('Ошибка')
    }
  }

  const handleAskQuestion = async () => {
    if (!user) { message.info('Войдите, чтобы задать вопрос'); return }
    if (!questionText.trim()) return
    try {
      const q = await questionsApi.ask(parseInt(id!), questionText)
      setQuestions([q, ...questions])
      setQuestionText('')
      message.success('Вопрос отправлен')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />
  if (!product) return <Empty description="Товар не найден" />

  const inCompare = compare.has(product.id)

  return (
    <div>
      <Row gutter={32}>
        <Col xs={24} md={10}>
          <Image src={selectedImage} alt={product.title} style={{ width: '100%', borderRadius: 12 }} />
          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            {product.images.map((img) => (
              <img
                key={img.id} src={img.url} alt=""
                onClick={() => setSelectedImage(img.url)}
                style={{
                  width: 64, height: 64, objectFit: 'cover', borderRadius: 8, cursor: 'pointer',
                  border: selectedImage === img.url ? '2px solid #f97316' : '1px solid #eee',
                }}
              />
            ))}
          </div>
        </Col>

        <Col xs={24} md={14}>
          <Title level={2} style={{ marginBottom: 8 }}>{product.title}</Title>
          <Link to={`/shops/${product.shop_id}`}>
            <Text type="secondary" style={{ fontSize: 13 }}>Перейти в магазин →</Text>
          </Link>

          <div style={{ margin: '12px 0' }}>
            <Rate disabled value={parseFloat(product.rating)} allowHalf />
            <Text type="secondary" style={{ marginLeft: 8 }}>{product.reviews_count} отзывов</Text>
          </div>

          {product.flash_price && !selectedVariant ? (
            <div style={{ margin: '16px 0' }}>
              <Title level={2} style={{ color: '#cf1322', margin: 0, display: 'inline-block' }}>
                {parseFloat(product.flash_price).toLocaleString('ru')} ₽
              </Title>
              <Text delete type="secondary" style={{ fontSize: 18, marginLeft: 12 }}>
                {parseFloat(product.price).toLocaleString('ru')} ₽
              </Text>
              <Tag color="red" style={{ marginLeft: 12 }}>
                Акция −{product.flash_discount_percent ? parseFloat(product.flash_discount_percent) : ''}%
              </Tag>
              {product.flash_ends_at && (
                <div><Text type="secondary" style={{ fontSize: 13 }}>
                  До {dayjs(product.flash_ends_at).format('DD.MM.YYYY HH:mm')}
                </Text></div>
              )}
            </div>
          ) : (
            <Title level={2} style={{ color: '#f97316', margin: '16px 0' }}>
              {currentPrice.toLocaleString('ru')} ₽
              {product.compare_at_price && (
                <Text delete type="secondary" style={{ fontSize: 18, marginLeft: 12 }}>
                  {parseFloat(product.compare_at_price).toLocaleString('ru')} ₽
                </Text>
              )}
            </Title>
          )}

          {variants.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <Text strong>Вариант:</Text>
              <div style={{ marginTop: 8 }}>
                <Radio.Group value={selectedVariant} onChange={(e) => setSelectedVariant(e.target.value)}>
                  {variants.map((v) => (
                    <Radio.Button key={v.id} value={v.id} disabled={v.quantity === 0}>
                      {v.name}{v.quantity === 0 ? ' (нет в наличии)' : ''}
                    </Radio.Button>
                  ))}
                </Radio.Group>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
            {product.quantity > 0 ? (
              <>
                <InputNumber min={1} value={quantity} onChange={(v) => setQuantity(v || 1)} />
                <Button
                  type="primary" size="large" icon={<ShoppingCartOutlined />}
                  onClick={handleAddToCart}
                >
                  В корзину
                </Button>
              </>
            ) : (
              <Button
                size="large" type="primary" ghost
                onClick={async () => {
                  if (!user) { message.info('Войдите, чтобы подписаться'); return }
                  try {
                    await productSubsApi.subscribe(product.id, 'back_in_stock')
                    message.success('Уведомим, когда товар появится в наличии')
                  } catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
                }}
              >
                Уведомить о наличии
              </Button>
            )}
            <Button
              size="large" icon={isFavorite ? <HeartFilled style={{ color: '#ff4d4f' }} /> : <HeartOutlined />}
              onClick={handleFavorite}
            />
            <Button
              size="large" icon={<FolderAddOutlined />}
              onClick={openWishlistModal}
              title="Добавить в коллекцию"
            />
            <Button
              size="large" icon={<SwapOutlined />}
              type={inCompare ? 'primary' : 'default'}
              onClick={() => { compare.toggle(product); message.success(inCompare ? 'Убрано из сравнения' : 'Добавлено к сравнению') }}
              title="Сравнить"
            />
            <Button
              size="large" icon={<FlagOutlined />}
              onClick={() => {
                if (!user) { message.info('Войдите, чтобы отправить жалобу'); return }
                setReportModalOpen(true)
              }}
              title="Пожаловаться на товар"
            />
          </div>

          <Button onClick={handleChat} style={{ marginBottom: 16 }}>Написать продавцу</Button>
          <Button
            type="link" style={{ marginBottom: 16, paddingLeft: 8 }}
            onClick={async () => {
              if (!user) { message.info('Войдите, чтобы следить за ценой'); return }
              const target = prompt('Уведомить, когда цена опустится до (₽):', String(Math.floor(currentPrice * 0.9)))
              if (!target) return
              try {
                await productSubsApi.subscribe(product.id, 'price_drop', parseFloat(target))
                message.success('Уведомим при снижении цены')
              } catch (e: any) { message.error(e.response?.data?.detail || 'Ошибка') }
            }}
          >
            Следить за ценой
          </Button>

          <div style={{ background: '#f9f9f9', borderRadius: 8, padding: 16 }}>
            <Text type="secondary">✅ Бесплатный возврат в течение 30 дней</Text><br />
            <Text type="secondary">🚚 Доставка по всей России</Text><br />
            <Text type="secondary">🔒 Безопасная оплата через ЮKassa</Text>
          </div>

          <ReportModal
            open={reportModalOpen}
            onClose={() => setReportModalOpen(false)}
            targetType="product"
            targetId={product.id}
            targetLabel={product.title}
          />

          <Modal
            title="Добавить в коллекцию"
            open={wishlistModalOpen}
            onCancel={() => setWishlistModalOpen(false)}
            footer={null}
          >
            {wishlistCollections.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                {wishlistCollections.map((c) => (
                  <Button
                    key={c.id} block style={{ marginBottom: 8, textAlign: 'left' }}
                    onClick={() => addToCollection(c.id)}
                  >
                    {c.name} <Text type="secondary">({c.item_count})</Text>
                  </Button>
                ))}
              </div>
            )}
            <Input.Search
              placeholder="Новая коллекция — введите название"
              enterButton="Создать"
              onSearch={createAndAdd}
            />
          </Modal>
        </Col>
      </Row>

      {/* Tabs: description + reviews + Q&A */}
      <div style={{ marginTop: 32 }}>
        <Tabs
          items={[
            {
              key: 'desc',
              label: 'Описание',
              children: <Paragraph>{product.description || 'Описание отсутствует'}</Paragraph>,
            },
            {
              key: 'reviews',
              label: `Отзывы (${product.reviews_count})`,
              children: (
                <div>
                  {user && (
                    <Card style={{ marginBottom: 24 }} title="Написать отзыв">
                      <Form form={form} layout="vertical" onFinish={handleReview}>
                        <Form.Item name="rating" label="Оценка" rules={[{ required: true, message: 'Поставьте оценку' }]}>
                          <Rate />
                        </Form.Item>
                        <Form.Item name="text" label="Отзыв">
                          <Input.TextArea rows={3} placeholder="Поделитесь впечатлениями" />
                        </Form.Item>
                        <Form.Item label="Фото (URL, по одному)">
                          <Input.Search
                            placeholder="Вставьте URL фото и нажмите +"
                            enterButton={<PlusOutlined />}
                            onSearch={(v) => { if (v) setReviewPhotos([...reviewPhotos, v]) }}
                          />
                          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                            {reviewPhotos.map((url, i) => (
                              <div key={i} style={{ position: 'relative' }}>
                                <img src={url} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6 }} />
                                <Button
                                  size="small" danger type="text"
                                  style={{ position: 'absolute', top: -8, right: -8 }}
                                  onClick={() => setReviewPhotos(reviewPhotos.filter((_, idx) => idx !== i))}
                                >×</Button>
                              </div>
                            ))}
                          </div>
                        </Form.Item>
                        <Button type="primary" htmlType="submit" loading={reviewLoading}>Отправить</Button>
                      </Form>
                    </Card>
                  )}

                  {reviews.length === 0 && !verifiedOnly ? (
                    <Empty description="Отзывов пока нет. Будьте первым!" />
                  ) : (
                    <>
                      <div style={{ marginBottom: 12 }}>
                        <Checkbox checked={verifiedOnly} onChange={(e) => reloadReviews(e.target.checked)}>
                          Только проверенные покупки
                        </Checkbox>
                      </div>
                      {reviews.length === 0 ? (
                        <Empty description="Нет проверенных отзывов" />
                      ) : (
                    <List
                      dataSource={reviews}
                      renderItem={(r) => (
                        <List.Item style={{ display: 'block' }}>
                          <List.Item.Meta
                            avatar={<Avatar>{r.user.full_name[0]}</Avatar>}
                            title={
                              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                                <Text strong>{r.user.full_name}</Text>
                                <Rate disabled value={r.rating} style={{ fontSize: 12 }} />
                                {r.is_verified_purchase && (
                                  <Tag color="green" icon={<CheckCircleFilled />} style={{ fontSize: 11, marginInlineEnd: 0 }}>
                                    Проверенная покупка
                                  </Tag>
                                )}
                                <Text type="secondary" style={{ fontSize: 12 }}>
                                  {dayjs(r.created_at).format('DD.MM.YYYY')}
                                </Text>
                              </div>
                            }
                            description={r.text}
                          />
                          {r.photos && r.photos.length > 0 && (
                            <div style={{ display: 'flex', gap: 8, marginTop: 8, marginLeft: 48 }}>
                              {r.photos.map((ph) => (
                                <Image key={ph.id} src={ph.url} width={72} height={72} style={{ objectFit: 'cover', borderRadius: 6 }} />
                              ))}
                            </div>
                          )}
                          <div style={{ marginTop: 8, marginLeft: 48, display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Button
                              size="small" type="text"
                              icon={r.voted_by_me ? <LikeFilled style={{ color: '#f97316' }} /> : <LikeOutlined />}
                              onClick={() => handleVote(r.id)}
                            >
                              Полезно {r.helpful_count > 0 ? `(${r.helpful_count})` : ''}
                            </Button>
                          </div>
                          {r.reply && (
                            <div style={{
                              marginTop: 8, marginLeft: 48, padding: 12,
                              background: '#fff7ed', borderRadius: 8, borderLeft: '3px solid #f97316',
                            }}>
                              <Text strong style={{ fontSize: 13, color: '#ea580c' }}>Ответ продавца</Text>
                              <Paragraph style={{ marginBottom: 0, marginTop: 4, fontSize: 13 }}>{r.reply.text}</Paragraph>
                            </div>
                          )}
                        </List.Item>
                      )}
                    />
                      )}
                    </>
                  )}
                </div>
              ),
            },
            {
              key: 'qa',
              label: `Вопросы (${questions.length})`,
              children: (
                <div>
                  {user && (
                    <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
                      <Input.TextArea
                        rows={2} value={questionText}
                        onChange={(e) => setQuestionText(e.target.value)}
                        placeholder="Задайте вопрос о товаре"
                      />
                      <Button type="primary" onClick={handleAskQuestion}>Спросить</Button>
                    </div>
                  )}
                  {questions.length === 0 ? (
                    <Empty description="Вопросов пока нет" />
                  ) : (
                    <List
                      dataSource={questions}
                      renderItem={(q) => (
                        <List.Item style={{ display: 'block' }}>
                          <div style={{ display: 'flex', gap: 8 }}>
                            <Text strong>В:</Text>
                            <div>
                              <Text>{q.question}</Text>
                              <div><Text type="secondary" style={{ fontSize: 11 }}>{q.user.full_name} · {dayjs(q.created_at).format('DD.MM.YYYY')}</Text></div>
                            </div>
                          </div>
                          {q.answer && (
                            <div style={{ display: 'flex', gap: 8, marginTop: 8, marginLeft: 16, padding: 12, background: '#f6ffed', borderRadius: 8 }}>
                              <Text strong style={{ color: '#52c41a' }}>О:</Text>
                              <Text>{q.answer}</Text>
                            </div>
                          )}
                        </List.Item>
                      )}
                    />
                  )}
                </div>
              ),
            },
          ]}
        />
      </div>

      {/* Bundles containing this product */}
      {bundles.length > 0 && (
        <div style={{ marginTop: 32 }}>
          <Title level={4}>Выгодные наборы</Title>
          <Row gutter={[16, 16]}>
            {bundles.map((b) => (
              <Col xs={24} md={12} key={b.id}>
                <Card>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <Text strong style={{ fontSize: 16 }}>{b.title}</Text>
                      {b.description && <Paragraph type="secondary" style={{ marginBottom: 8 }}>{b.description}</Paragraph>}
                      <div>
                        {b.items.map((it: any) => (
                          <div key={it.product_id}>
                            <Text type="secondary" style={{ fontSize: 13 }}>• {it.title} ×{it.quantity}</Text>
                          </div>
                        ))}
                      </div>
                    </div>
                    <Tag color="green">−{Number(b.saving).toLocaleString('ru')} ₽</Tag>
                  </div>
                  <div style={{ marginTop: 12, display: 'flex', alignItems: 'baseline', gap: 8 }}>
                    <Text delete type="secondary">{Number(b.list_price).toLocaleString('ru')} ₽</Text>
                    <Text strong style={{ fontSize: 18, color: '#f97316' }}>{Number(b.bundle_price).toLocaleString('ru')} ₽</Text>
                  </div>
                  <Button type="primary" style={{ marginTop: 12 }} onClick={async () => {
                    for (const it of b.items) { await addItem(it.product_id, it.quantity) }
                    message.success('Набор добавлен в корзину — скидка применится автоматически')
                  }}>
                    Добавить набор в корзину
                  </Button>
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div style={{ marginTop: 32 }}>
          <Title level={4}>С этим товаром покупают</Title>
          <Row gutter={[16, 16]}>
            {recommendations.slice(0, 4).map((rec) => {
              const img = rec.images.find((i) => i.is_main) || rec.images[0]
              return (
                <Col key={rec.id} xs={12} md={6}>
                  <Link to={`/products/${rec.id}`}>
                    <Card
                      hoverable
                      cover={<div style={{ height: 160, overflow: 'hidden' }}>{img && <img src={img.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}</div>}
                    >
                      <Text ellipsis style={{ display: 'block', fontSize: 13 }}>{rec.title}</Text>
                      <Text strong style={{ color: '#f97316' }}>{parseFloat(rec.price).toLocaleString('ru')} ₽</Text>
                    </Card>
                  </Link>
                </Col>
              )
            })}
          </Row>
        </div>
      )}
    </div>
  )
}
