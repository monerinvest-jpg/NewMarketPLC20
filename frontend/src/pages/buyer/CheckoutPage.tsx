import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Form, Input, Button, Card, Typography, Divider, message,
  Steps, InputNumber, Spin, Alert, Radio, Select, Checkbox
} from 'antd'
import { useCartStore } from '@/store/cartStore'
import { useAuthStore } from '@/store/authStore'
import { ordersApi, deliveryApi } from '@/api'
import type { DeliveryCalculation, PickupPoint, DeliveryQuote } from '@/types'

const { Title, Text } = Typography

export default function CheckoutPage() {
  const { items, totalPrice, fetchCart } = useCartStore()
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [delivery, setDelivery] = useState<DeliveryCalculation | null>(null)
  const [quotes, setQuotes] = useState<DeliveryQuote[]>([])
  const [selectedService, setSelectedService] = useState<string>('cdek')
  const [calculating, setCalculating] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [couponCode, setCouponCode] = useState('')
  const [bonusToUse, setBonusToUse] = useState(0)
  const [referralToUse, setReferralToUse] = useState(0)
  const [referralBalance, setReferralBalance] = useState(0)
  const [deliveryMethod, setDeliveryMethod] = useState<'courier' | 'pickup'>('courier')
  const [pickupPoints, setPickupPoints] = useState<PickupPoint[]>([])
  const [pickupLoading, setPickupLoading] = useState(false)
  const [selectedPickupCode, setSelectedPickupCode] = useState<string | undefined>()
  const [savedAddresses, setSavedAddresses] = useState<any[]>([])
  const [isGift, setIsGift] = useState(false)
  const [giftWrap, setGiftWrap] = useState(false)
  const [giftMessage, setGiftMessage] = useState('')
  const [giftWrapPrice, setGiftWrapPrice] = useState(0)

  useEffect(() => { fetchCart() }, [])

  useEffect(() => {
    import('@/api').then(({ usersApi }) =>
      usersApi.publicConfig().then((c) => setGiftWrapPrice(parseFloat(c.gift_wrap_price || '0'))).catch(() => {})
    )
  }, [])

  useEffect(() => {
    if (user) {
      import('@/api').then(({ usersApi }) =>
        usersApi.getReferralStats()
          .then((s) => setReferralBalance(parseFloat(s.referral_balance || '0')))
          .catch(() => {})
      )
    }
  }, [user])

  useEffect(() => {
    if (user) {
      import('@/api').then(({ addressApi }) =>
        addressApi.list().then((addrs) => {
          setSavedAddresses(addrs)
          // Pre-fill the form with the default address, if any
          const def = addrs.find((a: any) => a.is_default)
          if (def) {
            form.setFieldsValue({
              city_to: def.city,
              delivery_address: formatAddress(def),
            })
            handleCityChange(def.city)
          }
        }).catch(() => {})
      )
    }
  }, [user])

  const formatAddress = (a: any) =>
    [a.postal_code, a.city, a.street, a.building && `д. ${a.building}`, a.apartment && `кв. ${a.apartment}`]
      .filter(Boolean).join(', ')

  const totalWeight = items.reduce((sum, i) => sum + i.product.weight_g * i.quantity, 0)
  const maxBonus = parseFloat(user?.bonus_balance || '0')

  const handleCityChange = async (city: string) => {
    if (!city) return
    setCalculating(true)
    setPickupLoading(true)
    setSelectedPickupCode(undefined)
    try {
      // Fetch quotes from every delivery service so the buyer can compare
      const allQuotes = await deliveryApi.quoteAll({ city_to: city, weight_g: totalWeight })
      setQuotes(allQuotes)
      // Default to the currently selected service (or cheapest if not present)
      const chosen = allQuotes.find((q) => q.code === selectedService) || allQuotes[0]
      if (chosen) {
        setSelectedService(chosen.code)
        setDelivery({ cost: chosen.cost, estimated_days: chosen.estimated_days, service: chosen.code })
        const points = await deliveryApi.getPickupPoints(city, chosen.code)
        setPickupPoints(points)
      }
    } catch {
      message.error('Не удалось рассчитать доставку')
    } finally {
      setCalculating(false)
      setPickupLoading(false)
    }
  }

  const handleServiceChange = async (code: string) => {
    setSelectedService(code)
    const quote = quotes.find((q) => q.code === code)
    if (quote) {
      setDelivery({ cost: quote.cost, estimated_days: quote.estimated_days, service: code })
    }
    const city = form.getFieldValue('city_to')
    if (city && deliveryMethod === 'pickup') {
      setPickupLoading(true)
      try {
        const points = await deliveryApi.getPickupPoints(city, code)
        setPickupPoints(points)
        setSelectedPickupCode(undefined)
      } finally {
        setPickupLoading(false)
      }
    }
  }

  const handleSubmit = async (values: { delivery_address: string; city_to: string }) => {
    if (deliveryMethod === 'pickup' && !selectedPickupCode) {
      message.warning('Выберите пункт выдачи')
      return
    }

    const selectedPoint = pickupPoints.find((p) => p.code === selectedPickupCode)
    const finalAddress = deliveryMethod === 'pickup' && selectedPoint
      ? `Самовывоз: ${selectedPoint.name}, ${selectedPoint.address}`
      : values.delivery_address

    setSubmitting(true)
    try {
      const order = await ordersApi.create({
        delivery_address: finalAddress,
        city_to: values.city_to,
        delivery_service: selectedService,
        coupon_code: couponCode || undefined,
        bonus_to_use: bonusToUse || undefined,
        referral_to_use: referralToUse || undefined,
        is_gift: isGift || giftWrap || !!giftMessage.trim() || undefined,
        gift_wrap: giftWrap || undefined,
        gift_message: giftMessage.trim() || undefined,
      })
      message.success('Заказ создан!')
      if (order.payment?.confirmation_url) {
        window.location.href = order.payment.confirmation_url
      } else {
        navigate(`/orders/${order.id}`)
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка создания заказа')
    } finally {
      setSubmitting(false)
    }
  }

  if (items.length === 0) {
    return <Alert message="Корзина пуста" type="warning" showIcon />
  }

  const subtotal = totalPrice()
  const deliveryCost = delivery ? parseFloat(delivery.cost) : 0
  const giftWrapCost = giftWrap ? giftWrapPrice : 0
  const total = Math.max(subtotal + deliveryCost + giftWrapCost - bonusToUse - referralToUse, 0)

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <Title level={3}>Оформление заказа</Title>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24 }}>
        <Card title="Адрес доставки">
          <Form form={form} layout="vertical" onFinish={handleSubmit} requiredMark={false}>
            <Form.Item
              name="city_to" label="Город"
              rules={[{ required: true, message: 'Укажите город' }]}
            >
              <Input
                placeholder="Например: Санкт-Петербург"
                onBlur={(e) => handleCityChange(e.target.value)}
              />
            </Form.Item>

            <Form.Item label="Способ получения">
              <Radio.Group value={deliveryMethod} onChange={(e) => setDeliveryMethod(e.target.value)}>
                <Radio.Button value="courier">Курьером по адресу</Radio.Button>
                <Radio.Button value="pickup">Самовывоз из пункта</Radio.Button>
              </Radio.Group>
            </Form.Item>

            {quotes.length > 0 && (
              <Form.Item label="Служба доставки">
                <Radio.Group
                  value={selectedService}
                  onChange={(e) => handleServiceChange(e.target.value)}
                  style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
                >
                  {quotes.map((q) => (
                    <Radio key={q.code} value={q.code} style={{ width: '100%' }}>
                      <span style={{ display: 'inline-flex', justifyContent: 'space-between', width: 'calc(100% - 24px)' }}>
                        <span>{q.name}</span>
                        <span>
                          <Text strong>{parseFloat(q.cost).toLocaleString('ru')} ₽</Text>
                          <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>~{q.estimated_days} дн.</Text>
                        </span>
                      </span>
                    </Radio>
                  ))}
                </Radio.Group>
              </Form.Item>
            )}

            {deliveryMethod === 'courier' ? (
              <>
                {savedAddresses.length > 0 && (
                  <Form.Item label="Выбрать сохранённый адрес">
                    <Select
                      placeholder="Выберите из адресной книги"
                      allowClear
                      options={savedAddresses.map((a) => ({ value: a.id, label: `${a.label}: ${formatAddress(a)}` }))}
                      onChange={(id) => {
                        const a = savedAddresses.find((x) => x.id === id)
                        if (a) {
                          form.setFieldsValue({ city_to: a.city, delivery_address: formatAddress(a) })
                          handleCityChange(a.city)
                        }
                      }}
                    />
                  </Form.Item>
                )}
                <Form.Item
                  name="delivery_address" label="Полный адрес"
                  rules={[{ required: true, message: 'Укажите адрес доставки' }]}
                >
                  <Input.TextArea rows={3} placeholder="Улица, дом, квартира, индекс" />
                </Form.Item>
              </>
            ) : (
              <Form.Item label="Пункт выдачи (ПВЗ)" required>
                {pickupLoading ? (
                  <Spin size="small" />
                ) : pickupPoints.length === 0 ? (
                  <Text type="secondary">Укажите город, чтобы увидеть доступные пункты выдачи</Text>
                ) : (
                  <Select
                    placeholder="Выберите пункт выдачи"
                    value={selectedPickupCode}
                    onChange={setSelectedPickupCode}
                    options={pickupPoints.map((p) => ({
                      value: p.code,
                      label: `${p.name} — ${p.address}${p.work_time ? ` (${p.work_time})` : ''}`,
                    }))}
                  />
                )}
              </Form.Item>
            )}

            {calculating && <Spin size="small" />}
            {delivery && (
              <Alert
                style={{ marginBottom: 16 }}
                type="info"
                showIcon
                message={`${quotes.find((q) => q.code === selectedService)?.name || 'Доставка'}: ${parseFloat(delivery.cost).toLocaleString('ru')} ₽, ${delivery.estimated_days} дн.`}
              />
            )}

            <Form.Item label="Промокод">
              <Input
                placeholder="Введите код купона"
                value={couponCode}
                onChange={(e) => setCouponCode(e.target.value)}
              />
            </Form.Item>

            {maxBonus > 0 && (
              <Form.Item label={`Использовать бонусы (доступно: ${maxBonus.toLocaleString('ru')} ₽)`}>
                <InputNumber
                  min={0} max={maxBonus} style={{ width: '100%' }}
                  value={bonusToUse}
                  onChange={(v) => setBonusToUse(v || 0)}
                />
              </Form.Item>
            )}

            {referralBalance > 0 && (
              <Form.Item label={`Реферальный баланс (доступно: ${referralBalance.toLocaleString('ru')} ₽) — оплата до 100%`}>
                <InputNumber
                  min={0}
                  max={Math.min(referralBalance, Math.max(subtotal + deliveryCost - bonusToUse, 0))}
                  style={{ width: '100%' }}
                  value={referralToUse}
                  onChange={(v) => setReferralToUse(v || 0)}
                />
              </Form.Item>
            )}

            <Form.Item label="🎁 Подарок">
              <Checkbox checked={isGift} onChange={(e) => setIsGift(e.target.checked)}>
                Это подарок
              </Checkbox>
              {isGift && (
                <div style={{ marginTop: 8 }}>
                  <Checkbox checked={giftWrap} onChange={(e) => setGiftWrap(e.target.checked)}>
                    Подарочная упаковка{giftWrapPrice > 0 ? ` (+${giftWrapPrice.toLocaleString('ru')} ₽)` : ''}
                  </Checkbox>
                  <Input.TextArea
                    rows={2} style={{ marginTop: 8 }} maxLength={500}
                    placeholder="Поздравление для получателя (необязательно)"
                    value={giftMessage} onChange={(e) => setGiftMessage(e.target.value)}
                  />
                </div>
              )}
            </Form.Item>

            <Button type="primary" htmlType="submit" size="large" block loading={submitting}>
              Перейти к оплате
            </Button>
          </Form>
        </Card>

        <Card title="Ваш заказ">
          {items.map((item) => (
            <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <Text style={{ fontSize: 13 }}>{item.product.title} × {item.quantity}</Text>
              <Text style={{ fontSize: 13 }}>{(parseFloat(item.product.price) * item.quantity).toLocaleString('ru')} ₽</Text>
            </div>
          ))}
          <Divider />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <Text>Сумма товаров:</Text>
            <Text>{subtotal.toLocaleString('ru')} ₽</Text>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <Text>Доставка:</Text>
            <Text>{delivery ? `${deliveryCost.toLocaleString('ru')} ₽` : '—'}</Text>
          </div>
          {bonusToUse > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <Text>Бонусы:</Text>
              <Text style={{ color: '#52c41a' }}>−{bonusToUse.toLocaleString('ru')} ₽</Text>
            </div>
          )}
          {referralToUse > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <Text>Реферальный баланс:</Text>
              <Text style={{ color: '#52c41a' }}>−{referralToUse.toLocaleString('ru')} ₽</Text>
            </div>
          )}
          {giftWrapCost > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <Text>🎁 Упаковка:</Text>
              <Text>{giftWrapCost.toLocaleString('ru')} ₽</Text>
            </div>
          )}
          <Divider />
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text strong style={{ fontSize: 18 }}>Итого:</Text>
            <Text strong style={{ fontSize: 18, color: '#f97316' }}>
              {total.toLocaleString('ru')} ₽
            </Text>
          </div>
        </Card>
      </div>
    </div>
  )
}
