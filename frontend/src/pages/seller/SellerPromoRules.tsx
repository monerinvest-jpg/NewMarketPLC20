import { useEffect, useState } from 'react'
import {
  Tabs, Card, Table, Button, Tag, Typography, Modal, Form, Input, InputNumber,
  Select, Switch, message, Space, Popconfirm, Divider,
} from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { promoRulesApi, productsApi } from '@/api'
import type { PromoRule, Bundle, Product } from '@/types'

const { Title, Text, Paragraph } = Typography

const typeLabel: Record<string, string> = { nplus: 'N+1', volume: 'Объёмная скидка' }

export default function SellerPromoRules() {
  const [rules, setRules] = useState<PromoRule[]>([])
  const [bundles, setBundles] = useState<Bundle[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [ruleModal, setRuleModal] = useState(false)
  const [bundleModal, setBundleModal] = useState(false)
  const [ruleForm] = Form.useForm()
  const [bundleForm] = Form.useForm()
  const ruleType = Form.useWatch('type', ruleForm)

  const load = () => {
    promoRulesApi.listRules().then(setRules).catch(() => {})
    promoRulesApi.listBundles().then(setBundles).catch(() => {})
    productsApi.myProducts({ page_size: 200 }).then((r) => setProducts(r.items)).catch(() => {})
  }
  useEffect(() => { load() }, [])

  const productName = (id?: number | null) => products.find((p) => p.id === id)?.title

  const submitRule = async () => {
    const v = await ruleForm.validateFields()
    const payload: any = {
      title: v.title, type: v.type, is_active: true, product_id: v.product_id || null,
    }
    if (v.type === 'nplus') { payload.buy_quantity = v.buy_quantity; payload.free_quantity = v.free_quantity }
    else { payload.tiers = (v.tiers || []).map((t: any) => ({ min_qty: t.min_qty, percent: t.percent })) }
    await promoRulesApi.createRule(payload)
    message.success('Акция создана')
    setRuleModal(false); ruleForm.resetFields(); load()
  }

  const submitBundle = async () => {
    const v = await bundleForm.validateFields()
    await promoRulesApi.createBundle({
      title: v.title, description: v.description, bundle_price: v.bundle_price,
      items: (v.items || []).map((i: any) => ({ product_id: i.product_id, quantity: i.quantity || 1 })),
    })
    message.success('Набор создан')
    setBundleModal(false); bundleForm.resetFields(); load()
  }

  const toggleRule = async (r: PromoRule) => { await promoRulesApi.updateRule(r.id, { is_active: !r.is_active }); load() }
  const delRule = async (id: number) => { await promoRulesApi.deleteRule(id); load() }
  const delBundle = async (id: number) => { await promoRulesApi.deleteBundle(id); load() }

  return (
    <div>
      <Title level={3}>Акции и наборы</Title>
      <Paragraph type="secondary">
        Автоматические скидки применяются в корзине без промокода. «N+1» — например, 2+1.
        «Объёмная скидка» — процент за количество. Набор — комплект товаров по выгодной цене.
      </Paragraph>

      <Tabs
        items={[
          {
            key: 'rules', label: 'Акции',
            children: (
              <Card extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setRuleModal(true)}>Создать акцию</Button>}>
                <Table<PromoRule>
                  dataSource={rules} rowKey="id" pagination={false}
                  columns={[
                    { title: 'Название', dataIndex: 'title' },
                    { title: 'Тип', dataIndex: 'type', width: 150, render: (v) => <Tag>{typeLabel[v]}</Tag> },
                    { title: 'Условие', render: (_, r) => r.type === 'nplus'
                        ? `Купи ${r.buy_quantity} + ${r.free_quantity} в подарок`
                        : (r.tiers || []).map((t) => `${t.min_qty}+ → −${t.percent}%`).join(', ') },
                    { title: 'Товар', render: (_, r) => productName(r.product_id) || 'Весь магазин' },
                    { title: 'Активна', width: 90, render: (_, r) => <Switch checked={r.is_active} onChange={() => toggleRule(r)} /> },
                    { title: '', width: 60, render: (_, r) => (
                      <Popconfirm title="Удалить акцию?" onConfirm={() => delRule(r.id)}>
                        <Button size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    ) },
                  ]}
                />
              </Card>
            ),
          },
          {
            key: 'bundles', label: 'Наборы',
            children: (
              <Card extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setBundleModal(true)}>Создать набор</Button>}>
                <Table<Bundle>
                  dataSource={bundles} rowKey="id" pagination={false}
                  columns={[
                    { title: 'Название', dataIndex: 'title' },
                    { title: 'Состав', render: (_, b) => b.items.map((i) => `${productName(i.product_id) || i.product_id} ×${i.quantity}`).join(', ') },
                    { title: 'Цена набора', dataIndex: 'bundle_price', width: 130, render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
                    { title: 'Активен', dataIndex: 'is_active', width: 90, render: (v) => v ? <Tag color="green">Да</Tag> : <Tag>Нет</Tag> },
                    { title: '', width: 60, render: (_, b) => (
                      <Popconfirm title="Удалить набор?" onConfirm={() => delBundle(b.id)}>
                        <Button size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    ) },
                  ]}
                />
              </Card>
            ),
          },
        ]}
      />

      {/* Rule modal */}
      <Modal title="Новая акция" open={ruleModal} onCancel={() => setRuleModal(false)} onOk={submitRule} okText="Создать">
        <Form form={ruleForm} layout="vertical" initialValues={{ type: 'volume' }}>
          <Form.Item name="title" label="Название" rules={[{ required: true }]}><Input placeholder="Напр.: Скидка за объём" /></Form.Item>
          <Form.Item name="type" label="Тип акции" rules={[{ required: true }]}>
            <Select options={[{ value: 'volume', label: 'Объёмная скидка (% за количество)' }, { value: 'nplus', label: 'N+1 (купи N, получи M в подарок)' }]} />
          </Form.Item>
          <Form.Item name="product_id" label="Товар (пусто = весь магазин)">
            <Select allowClear showSearch optionFilterProp="label"
              options={products.map((p) => ({ value: p.id, label: p.title }))} />
          </Form.Item>
          {ruleType === 'nplus' ? (
            <Space>
              <Form.Item name="buy_quantity" label="Купить (N)" rules={[{ required: true }]}><InputNumber min={1} /></Form.Item>
              <Form.Item name="free_quantity" label="В подарок (M)" rules={[{ required: true }]}><InputNumber min={1} /></Form.Item>
            </Space>
          ) : (
            <>
              <Divider orientation="left" plain>Пороги скидки</Divider>
              <Form.List name="tiers" initialValue={[{ min_qty: 2, percent: 10 }]}>
                {(fields, { add, remove }) => (
                  <>
                    {fields.map((f) => (
                      <Space key={f.key} align="baseline">
                        <Form.Item name={[f.name, 'min_qty']} label="От, шт"><InputNumber min={1} /></Form.Item>
                        <Form.Item name={[f.name, 'percent']} label="Скидка, %"><InputNumber min={1} max={100} /></Form.Item>
                        <Button danger size="small" onClick={() => remove(f.name)}>×</Button>
                      </Space>
                    ))}
                    <Button onClick={() => add({ min_qty: 3, percent: 15 })}>+ Порог</Button>
                  </>
                )}
              </Form.List>
            </>
          )}
        </Form>
      </Modal>

      {/* Bundle modal */}
      <Modal title="Новый набор" open={bundleModal} onCancel={() => setBundleModal(false)} onOk={submitBundle} okText="Создать">
        <Form form={bundleForm} layout="vertical">
          <Form.Item name="title" label="Название" rules={[{ required: true }]}><Input placeholder="Напр.: Стартовый комплект" /></Form.Item>
          <Form.Item name="description" label="Описание"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="bundle_price" label="Цена набора, ₽" rules={[{ required: true }]}><InputNumber min={1} style={{ width: '100%' }} /></Form.Item>
          <Divider orientation="left" plain>Товары набора (минимум 2)</Divider>
          <Form.List name="items" initialValue={[{ quantity: 1 }, { quantity: 1 }]}>
            {(fields, { add, remove }) => (
              <>
                {fields.map((f) => (
                  <Space key={f.key} align="baseline" style={{ display: 'flex' }}>
                    <Form.Item name={[f.name, 'product_id']} rules={[{ required: true, message: 'Товар' }]} style={{ flex: 1, minWidth: 220 }}>
                      <Select placeholder="Товар" showSearch optionFilterProp="label" style={{ width: 240 }}
                        options={products.map((p) => ({ value: p.id, label: p.title }))} />
                    </Form.Item>
                    <Form.Item name={[f.name, 'quantity']} initialValue={1}><InputNumber min={1} /></Form.Item>
                    {fields.length > 2 && <Button danger size="small" onClick={() => remove(f.name)}>×</Button>}
                  </Space>
                ))}
                <Button onClick={() => add({ quantity: 1 })}>+ Товар</Button>
              </>
            )}
          </Form.List>
        </Form>
      </Modal>
    </div>
  )
}
