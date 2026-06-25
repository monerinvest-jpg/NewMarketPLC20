import { useEffect, useState } from 'react'
import {
  Card, Row, Col, Typography, Button, Table, Tag, Select, InputNumber, Form,
  message, Statistic, Space, Alert, Empty,
} from 'antd'
import { RiseOutlined } from '@ant-design/icons'
import { promotionsApi, productsApi } from '@/api'
import type { PaidFeature, Promotion, AuctionStanding, Product, PromotionStatus, AdWallet } from '@/types'
import dayjs from 'dayjs'

const { Title, Text, Paragraph } = Typography

const statusMeta: Record<PromotionStatus, { color: string; label: string }> = {
  pending: { color: 'gold', label: 'В очереди' },
  active: { color: 'green', label: 'Активно' },
  outbid: { color: 'orange', label: 'Ставка перебита' },
  expired: { color: 'default', label: 'Завершено' },
  cancelled: { color: 'default', label: 'Отменено' },
}

export default function SellerPromotion() {
  const [features, setFeatures] = useState<PaidFeature[]>([])
  const [promotions, setPromotions] = useState<Promotion[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [standings, setStandings] = useState<Record<string, AuctionStanding>>({})
  const [form] = Form.useForm()
  const [selectedFeature, setSelectedFeature] = useState<PaidFeature | null>(null)
  const [wallet, setWallet] = useState<AdWallet | null>(null)
  const [analytics, setAnalytics] = useState<any | null>(null)

  const loadWallet = () => promotionsApi.wallet().then(setWallet).catch(() => {})

  const load = () => {
    promotionsApi.features().then((f) => {
      setFeatures(f)
      f.filter((x) => x.pricing_mode === 'auction').forEach((x) =>
        promotionsApi.standing(x.key).then((s) => setStandings((prev) => ({ ...prev, [x.key]: s }))).catch(() => {}))
    }).catch(() => {})
    promotionsApi.mine().then(setPromotions).catch(() => {})
    productsApi.myProducts({ page_size: 100 }).then((r) => setProducts(r.items)).catch(() => {})
    promotionsApi.analytics().then(setAnalytics).catch(() => {})
    loadWallet()
  }
  useEffect(() => { load() }, [])

  const topup = async (packageId: string) => {
    try {
      await promotionsApi.topup(packageId)
      message.success('Кошелёк пополнен')
      loadWallet()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Не удалось пополнить')
    }
  }

  const submit = async () => {
    const v = await form.validateFields()
    try {
      await promotionsApi.create({ feature_key: v.feature_key, bid_amount: v.bid_amount, product_id: v.product_id })
      message.success('Продвижение оформлено')
      form.resetFields()
      setSelectedFeature(null)
      load()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'Не удалось оформить')
    }
  }

  const cancel = async (id: number) => {
    await promotionsApi.cancel(id)
    message.success('Отменено')
    load()
  }

  const isAuction = selectedFeature?.pricing_mode === 'auction'
  const standing = selectedFeature ? standings[selectedFeature.key] : undefined

  return (
    <div>
      <Title level={3}><RiseOutlined /> Продвижение магазина</Title>
      <Paragraph type="secondary">
        Поднимите товары в выдаче и на главной. Продвижение на главной работает по системе аукциона:
        выигрывают самые высокие дневные ставки, списание — с рекламного кошелька магазина.
      </Paragraph>

      {wallet && (
        <Card style={{ marginBottom: 24 }}>
          <Row gutter={16} align="middle">
            <Col xs={24} md={6}>
              <Statistic title="Рекламный кошелёк" value={`${Number(wallet.ad_balance).toLocaleString('ru')} ₽`} valueStyle={{ color: '#f97316' }} />
            </Col>
            <Col xs={24} md={18}>
              <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>Пополнить (списывается с основного баланса; крупные пакеты — с бонусом):</Text>
              <Space wrap>
                {wallet.packages.map((p) => (
                  <Button key={p.id} onClick={() => topup(p.id)}>
                    {Number(p.amount).toLocaleString('ru')} ₽
                    {Number(p.bonus) > 0 && <Text type="success" style={{ marginLeft: 4 }}>+{Number(p.bonus).toLocaleString('ru')}</Text>}
                  </Button>
                ))}
              </Space>
            </Col>
          </Row>
          {wallet.transactions.length > 0 && (
            <Table
              size="small" style={{ marginTop: 16 }} pagination={false}
              dataSource={wallet.transactions.slice(0, 5)} rowKey="id"
              columns={[
                { title: 'Операция', dataIndex: 'description' },
                { title: 'Сумма', dataIndex: 'change', width: 120, render: (v) => <Text type={Number(v) < 0 ? 'danger' : 'success'}>{Number(v) > 0 ? '+' : ''}{Number(v).toLocaleString('ru')} ₽</Text> },
                { title: 'Остаток', dataIndex: 'balance_after', width: 120, render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
                { title: 'Дата', dataIndex: 'created_at', width: 130, render: (v) => dayjs(v).format('DD.MM.YY HH:mm') },
              ]}
            />
          )}
        </Card>
      )}

      <Row gutter={16}>
        {features.map((f) => (
          <Col xs={24} md={8} key={f.id} style={{ marginBottom: 16 }}>
            <Card
              title={f.name}
              extra={<Tag color={f.pricing_mode === 'auction' ? 'purple' : 'blue'}>{f.pricing_mode === 'auction' ? 'Аукцион' : 'Фикс. цена'}</Tag>}
            >
              <Paragraph type="secondary" style={{ minHeight: 44 }}>{f.description}</Paragraph>
              <Statistic
                title={f.pricing_mode === 'auction' ? 'Мин. ставка / день' : `Цена / ${f.billing_period === 'week' ? 'неделя' : f.billing_period === 'day' ? 'день' : 'разово'}`}
                value={`${Number(f.price).toLocaleString('ru')} ₽`}
              />
              {f.pricing_mode === 'auction' && standings[f.key] && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Слотов: {standings[f.key].slots} · ставок: {standings[f.key].bidders} ·
                  мин. выигрышная: {Number(standings[f.key].min_winning_bid).toLocaleString('ru')} ₽
                </Text>
              )}
              <Button type="primary" block style={{ marginTop: 12 }}
                onClick={() => { setSelectedFeature(f); form.setFieldsValue({ feature_key: f.key, bid_amount: Number(f.price) }) }}>
                {f.pricing_mode === 'auction' ? 'Сделать ставку' : 'Купить'}
              </Button>
            </Card>
          </Col>
        ))}
        {features.length === 0 && <Col span={24}><Empty description="Платные возможности пока отключены" /></Col>}
      </Row>

      {selectedFeature && (
        <Card title={`Оформление: ${selectedFeature.name}`} style={{ marginBottom: 24 }}>
          {isAuction && standing && (
            <Alert
              type="info" showIcon style={{ marginBottom: 16 }}
              message={`Чтобы попасть в топ-${standing.slots}, ставка должна быть не ниже ${Number(standing.min_winning_bid).toLocaleString('ru')} ₽/день.`}
            />
          )}
          <Form form={form} layout="inline" onFinish={submit}>
            <Form.Item name="feature_key" hidden><input /></Form.Item>
            <Form.Item name="product_id" label="Товар" rules={[{ required: true, message: 'Выберите товар' }]}>
              <Select style={{ width: 260 }} placeholder="Выберите товар"
                options={products.map((p) => ({ value: p.id, label: p.title }))} />
            </Form.Item>
            <Form.Item name="bid_amount" label={isAuction ? 'Ставка ₽/день' : 'Цена ₽'}
              rules={[{ required: true, message: 'Укажите сумму' }]}>
              <InputNumber min={Number(selectedFeature.price)} style={{ width: 160 }} />
            </Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">{isAuction ? 'Поставить' : 'Оплатить'}</Button>
              <Button onClick={() => { setSelectedFeature(null); form.resetFields() }}>Отмена</Button>
            </Space>
          </Form>
        </Card>
      )}

      <Title level={4}>Аналитика рекламы (ROI)</Title>
      {analytics?.totals && (
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col xs={8} md={4}><Card size="small"><Statistic title="Показы" value={analytics.totals.impressions} /></Card></Col>
          <Col xs={8} md={4}><Card size="small"><Statistic title="Клики" value={analytics.totals.clicks} /></Card></Col>
          <Col xs={8} md={4}><Card size="small"><Statistic title="CTR" value={analytics.totals.ctr} suffix="%" /></Card></Col>
          <Col xs={8} md={4}><Card size="small"><Statistic title="Расход" value={`${Number(analytics.totals.spent).toLocaleString('ru')} ₽`} /></Card></Col>
          <Col xs={8} md={4}><Card size="small"><Statistic title="Выручка" value={`${Number(analytics.totals.revenue).toLocaleString('ru')} ₽`} valueStyle={{ color: '#3f8600' }} /></Card></Col>
          <Col xs={8} md={4}><Card size="small"><Statistic title="ROI" value={analytics.totals.roi ?? '—'} suffix={analytics.totals.roi != null ? '%' : ''} valueStyle={{ color: (analytics.totals.roi ?? 0) >= 0 ? '#3f8600' : '#cf1322' }} /></Card></Col>
        </Row>
      )}
      <Table
        dataSource={analytics?.rows || []} rowKey="promotion_id" pagination={{ pageSize: 8 }} size="small"
        style={{ marginBottom: 32 }}
        columns={[
          { title: 'Товар', dataIndex: 'product_title', render: (v) => v || '—' },
          { title: 'Размещение', dataIndex: 'placement', width: 110 },
          { title: 'Показы', dataIndex: 'impressions', width: 90 },
          { title: 'Клики', dataIndex: 'clicks', width: 80 },
          { title: 'CTR', dataIndex: 'ctr', width: 80, render: (v) => `${v}%` },
          { title: 'CPC', dataIndex: 'cpc', width: 90, render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
          { title: 'Расход', dataIndex: 'spent', width: 100, render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
          { title: 'Выручка', dataIndex: 'revenue', width: 110, render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
          { title: 'Заказы', dataIndex: 'orders', width: 80 },
          { title: 'ROI', dataIndex: 'roi', width: 90, render: (v) => v == null ? '—' : <Text type={v >= 0 ? 'success' : 'danger'}>{v}%</Text> },
        ]}
      />

      <Title level={4}>Мои продвижения</Title>
      <Table<Promotion>
        dataSource={promotions} rowKey="id" pagination={{ pageSize: 10 }}
        columns={[
          { title: '№', dataIndex: 'id', width: 60 },
          { title: 'Возможность', dataIndex: 'feature_key' },
          { title: 'Размещение', dataIndex: 'placement', width: 120 },
          { title: 'Ставка/цена', dataIndex: 'bid_amount', width: 120, render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
          { title: 'Потрачено', dataIndex: 'total_spent', width: 110, render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
          { title: 'Статус', dataIndex: 'status', width: 140, render: (v: PromotionStatus) => <Tag color={statusMeta[v]?.color}>{statusMeta[v]?.label}</Tag> },
          { title: 'Создано', dataIndex: 'created_at', width: 120, render: (v) => dayjs(v).format('DD.MM.YY') },
          {
            title: '', width: 110, render: (_, r) => (
              ['pending', 'active', 'outbid'].includes(r.status)
                ? <Button size="small" danger onClick={() => cancel(r.id)}>Отменить</Button> : null
            ),
          },
        ]}
      />
    </div>
  )
}
