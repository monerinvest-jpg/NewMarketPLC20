import { useEffect, useState } from 'react'
import { Card, Form, Input, Button, Typography, message, Tag, Row, Col, ColorPicker, Divider, Alert } from 'antd'
import { Link } from 'react-router-dom'
import { shopsApi } from '@/api'
import type { Shop } from '@/types'

const { Title, Text } = Typography

export default function SellerShopSettings() {
  const [shop, setShop] = useState<Shop | null>(null)
  const [loading, setLoading] = useState(false)
  const [accentColor, setAccentColor] = useState('#f97316')
  const [form] = Form.useForm()

  useEffect(() => {
    shopsApi.getMy().then((s) => {
      setShop(s)
      form.setFieldsValue(s)
      setAccentColor(s.accent_color || '#f97316')
    })
  }, [])

  const onFinish = async (values: any) => {
    setLoading(true)
    try {
      const updated = await shopsApi.updateMy({ ...values, accent_color: accentColor })
      setShop(updated)
      message.success('Настройки магазина сохранены')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    } finally {
      setLoading(false)
    }
  }

  if (!shop) return null

  return (
    <div style={{ maxWidth: 760 }}>
      <Title level={3}>Настройки магазина</Title>

      {shop.status && shop.status !== 'active' && (
        <Alert
          style={{ marginBottom: 16 }}
          type={shop.status === 'pending' ? 'info' : 'error'}
          showIcon
          message={
            shop.status === 'pending' ? 'Магазин на проверке'
              : shop.status === 'rejected' ? 'Магазин отклонён модератором'
              : 'Магазин заблокирован'
          }
          description={
            shop.status === 'pending'
              ? 'Пока магазин не одобрен модератором, он не отображается на витрине. Обычно проверка занимает немного времени.'
              : (shop.moderation_reason || 'Обратитесь в поддержку для уточнения причины.')
          }
        />
      )}
      {shop.status === 'active' && (
        <Alert style={{ marginBottom: 16 }} type="success" showIcon message="Магазин активен и виден покупателям" />
      )}

      <Card style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Text>Комиссия платформы: </Text>
            <Tag color="orange">
              {shop.commission_percent ? `${shop.commission_percent}% (индивидуальная)` : 'По тарифу / глобальная ставка'}
            </Tag>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              Комиссия зависит от вашего тарифа. Управлять тарифом можно на странице «Тариф и комиссия».
            </Text>
          </div>
          <Link to="/seller/plan"><Button>Выбрать тариф</Button></Link>
        </div>
      </Card>

      <Card title="Витрина магазина">
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Row gutter={24}>
            <Col span={12}>
              <Form.Item name="name" label="Название" rules={[{ required: true }]}>
                <Input size="large" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="tagline" label="Слоган (краткое описание)">
                <Input size="large" placeholder="Например: уникальные вещи ручной работы" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="description" label="Описание">
            <Input.TextArea rows={4} placeholder="Расскажите о вашем магазине покупателям" />
          </Form.Item>

          <Row gutter={24}>
            <Col span={12}>
              <Form.Item name="logo_url" label="URL логотипа">
                <Input placeholder="https://..." />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="banner_url" label="URL баннера (шапка магазина)">
                <Input placeholder="https://..." />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item label="Акцентный цвет витрины">
            <ColorPicker
              value={accentColor}
              onChange={(c) => setAccentColor(c.toHexString())}
              showText
            />
            <Text type="secondary" style={{ marginLeft: 12, fontSize: 12 }}>
              Используется в оформлении публичной страницы магазина
            </Text>
          </Form.Item>

          <Divider>Контакты</Divider>
          <Row gutter={24}>
            <Col span={12}>
              <Form.Item name="contact_email" label="Email для покупателей">
                <Input placeholder="shop@example.com" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="contact_phone" label="Телефон">
                <Input placeholder="+7 900 000 00 00" />
              </Form.Item>
            </Col>
          </Row>

          <div style={{ display: 'flex', gap: 12 }}>
            <Button type="primary" htmlType="submit" loading={loading}>Сохранить</Button>
            <Link to={`/shops/${shop.id}`}><Button>Посмотреть витрину</Button></Link>
          </div>
        </Form>
      </Card>
    </div>
  )
}
