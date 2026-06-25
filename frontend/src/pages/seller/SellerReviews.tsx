import { useEffect, useState } from 'react'
import {
  Card, List, Avatar, Rate, Typography, Input, Button,
  message, Empty, Spin, Tag, Popconfirm
} from 'antd'
import { productsApi, reviewsApi } from '@/api'
import type { Product, Review } from '@/types'
import dayjs from 'dayjs'

const { Title, Text, Paragraph } = Typography

interface ProductWithReviews {
  product: Product
  reviews: Review[]
}

export default function SellerReviews() {
  const [items, setItems] = useState<ProductWithReviews[]>([])
  const [loading, setLoading] = useState(true)
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({})
  const [submittingId, setSubmittingId] = useState<number | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const productsRes = await productsApi.myProducts({ page_size: 100 })
      const withReviews = await Promise.all(
        productsRes.items.map(async (product) => {
          const reviewsRes = await reviewsApi.list(product.id, { page: 1 })
          return { product, reviews: reviewsRes.items }
        })
      )
      setItems(withReviews.filter((i) => i.reviews.length > 0))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleReply = async (reviewId: number) => {
    const text = replyDrafts[reviewId]?.trim()
    if (!text) { message.warning('Введите текст ответа'); return }
    setSubmittingId(reviewId)
    try {
      const reply = await reviewsApi.reply(reviewId, text)
      setItems((prev) =>
        prev.map((group) => ({
          ...group,
          reviews: group.reviews.map((r) => (r.id === reviewId ? { ...r, reply } : r)),
        }))
      )
      message.success('Ответ опубликован')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    } finally {
      setSubmittingId(null)
    }
  }

  const handleDeleteReply = async (reviewId: number) => {
    await reviewsApi.deleteReply(reviewId)
    setItems((prev) =>
      prev.map((group) => ({
        ...group,
        reviews: group.reviews.map((r) => (r.id === reviewId ? { ...r, reply: undefined } : r)),
      }))
    )
    message.success('Ответ удалён')
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  if (items.length === 0) {
    return <Empty description="На ваши товары пока нет отзывов" style={{ margin: 80 }} />
  }

  return (
    <div>
      <Title level={3}>Отзывы на ваши товары</Title>

      {items.map(({ product, reviews }) => (
        <Card key={product.id} title={product.title} style={{ marginBottom: 24 }}>
          <List
            dataSource={reviews}
            renderItem={(review) => (
              <List.Item style={{ display: 'block' }}>
                <List.Item.Meta
                  avatar={<Avatar>{review.user.full_name[0]}</Avatar>}
                  title={
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <Text strong>{review.user.full_name}</Text>
                      <Rate disabled value={review.rating} style={{ fontSize: 12 }} />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {dayjs(review.created_at).format('DD.MM.YYYY')}
                      </Text>
                      {review.helpful_count > 0 && (
                        <Tag color="orange">👍 {review.helpful_count}</Tag>
                      )}
                    </div>
                  }
                  description={review.text}
                />

                {review.reply ? (
                  <div style={{
                    marginTop: 8, marginLeft: 48, padding: 12,
                    background: '#fff7ed', borderRadius: 8, borderLeft: '3px solid #f97316',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <Text strong style={{ fontSize: 13, color: '#ea580c' }}>Ваш ответ</Text>
                        <Paragraph style={{ marginBottom: 0, marginTop: 4, fontSize: 13 }}>{review.reply.text}</Paragraph>
                      </div>
                      <Popconfirm title="Удалить ответ?" onConfirm={() => handleDeleteReply(review.id)}>
                        <Button size="small" type="text" danger>Удалить</Button>
                      </Popconfirm>
                    </div>
                  </div>
                ) : (
                  <div style={{ marginTop: 8, marginLeft: 48, display: 'flex', gap: 8 }}>
                    <Input.TextArea
                      rows={2}
                      placeholder="Ответить покупателю..."
                      value={replyDrafts[review.id] || ''}
                      onChange={(e) => setReplyDrafts({ ...replyDrafts, [review.id]: e.target.value })}
                    />
                    <Button
                      type="primary"
                      loading={submittingId === review.id}
                      onClick={() => handleReply(review.id)}
                    >
                      Ответить
                    </Button>
                  </div>
                )}
              </List.Item>
            )}
          />
        </Card>
      ))}
    </div>
  )
}
