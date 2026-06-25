import { useEffect, useState } from 'react'
import { Card, List, Tag, Typography, Button, Empty, Spin, message } from 'antd'
import { Link } from 'react-router-dom'
import { productSubsApi } from '@/api'
import type { ProductSubscription } from '@/types'

const { Title, Text } = Typography

export default function ProductSubscriptionsPage() {
  const [subs, setSubs] = useState<ProductSubscription[]>([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    productSubsApi.my().then(setSubs).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const remove = async (id: number) => {
    await productSubsApi.remove(id)
    message.success('Подписка удалена')
    load()
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div style={{ maxWidth: 720 }}>
      <Title level={3}>Подписки на товары</Title>
      <Card>
        {subs.length === 0 ? (
          <Empty description="Вы не подписаны на уведомления о товарах" />
        ) : (
          <List
            dataSource={subs}
            renderItem={(s) => (
              <List.Item
                actions={[<Button key="del" size="small" danger onClick={() => remove(s.id)}>Удалить</Button>]}
              >
                <List.Item.Meta
                  title={<Link to={`/products/${s.product_id}`}>Товар #{s.product_id}</Link>}
                  description={
                    <>
                      {s.kind === 'back_in_stock'
                        ? <Tag color="blue">Уведомить о наличии</Tag>
                        : <Tag color="orange">Снижение цены до {s.target_price ? `${parseFloat(s.target_price).toLocaleString('ru')} ₽` : '—'}</Tag>}
                      {s.is_notified && <Tag color="green">Уведомление отправлено</Tag>}
                    </>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  )
}
