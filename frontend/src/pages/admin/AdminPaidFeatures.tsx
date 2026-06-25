import { useEffect, useState } from 'react'
import {
  Card, Table, Typography, Button, InputNumber, Switch, Tag, message, Space, Input, Modal, Divider,
} from 'antd'
import { promotionsApi } from '@/api'
import type { PaidFeature, Promotion, PromotionStatus } from '@/types'
import dayjs from 'dayjs'

const { Title, Paragraph, Text } = Typography

const statusMeta: Record<PromotionStatus, { color: string; label: string }> = {
  pending: { color: 'gold', label: 'В очереди' },
  active: { color: 'green', label: 'Активно' },
  outbid: { color: 'orange', label: 'Перебито' },
  expired: { color: 'default', label: 'Завершено' },
  cancelled: { color: 'default', label: 'Отменено' },
}

export default function AdminPaidFeatures() {
  const [features, setFeatures] = useState<PaidFeature[]>([])
  const [promotions, setPromotions] = useState<Promotion[]>([])
  const [edit, setEdit] = useState<PaidFeature | null>(null)
  const [draft, setDraft] = useState<Partial<PaidFeature>>({})

  const load = () => {
    promotionsApi.adminFeatures().then(setFeatures).catch(() => {})
    promotionsApi.adminPromotions().then((r) => setPromotions(r.items)).catch(() => {})
  }
  useEffect(() => { load() }, [])

  const save = async () => {
    if (!edit) return
    await promotionsApi.adminUpdateFeature(edit.id, draft)
    message.success('Сохранено')
    setEdit(null)
    load()
  }

  const toggle = async (f: PaidFeature) => {
    await promotionsApi.adminUpdateFeature(f.id, { is_enabled: !f.is_enabled })
    load()
  }

  const settle = async () => {
    const r = await promotionsApi.adminSettle()
    message.success(`Аукцион пересчитан (${r.results.length} размещений)`)
    load()
  }

  return (
    <div>
      <Title level={3}>Платные возможности и продвижение</Title>
      <Paragraph type="secondary">
        Управляйте каталогом платных возможностей: задавайте цену, число слотов аукциона и
        включайте/выключайте каждую. Продвижение на главной разыгрывается аукционом дневных ставок.
      </Paragraph>

      <Card title="Каталог возможностей" style={{ marginBottom: 24 }}>
        <Table<PaidFeature>
          dataSource={features} rowKey="id" pagination={false}
          columns={[
            { title: 'Название', dataIndex: 'name' },
            { title: 'Размещение', dataIndex: 'placement', width: 130 },
            { title: 'Модель', dataIndex: 'pricing_mode', width: 120, render: (v) => <Tag color={v === 'auction' ? 'purple' : 'blue'}>{v === 'auction' ? 'Аукцион' : 'Фикс.'}</Tag> },
            { title: 'Цена/ставка', dataIndex: 'price', width: 120, render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
            { title: 'Период', dataIndex: 'billing_period', width: 90 },
            { title: 'Слотов', dataIndex: 'slots', width: 80 },
            {
              title: 'Включено', dataIndex: 'is_enabled', width: 100,
              render: (v, f) => <Switch checked={v} onChange={() => toggle(f)} />,
            },
            {
              title: '', width: 110,
              render: (_, f) => <Button size="small" onClick={() => { setEdit(f); setDraft({ price: f.price, slots: f.slots, name: f.name, description: f.description, billing_period: f.billing_period }) }}>Изменить</Button>,
            },
          ]}
        />
      </Card>

      <Card
        title="Активные продвижения и аукцион"
        extra={<Button type="primary" onClick={settle}>Пересчитать аукцион</Button>}
      >
        <Text type="secondary">Победители аукциона показываются на витрине. Пересчёт также выполняется автоматически ночью.</Text>
        <Divider style={{ margin: '12px 0' }} />
        <Table<Promotion>
          dataSource={promotions} rowKey="id" pagination={{ pageSize: 15 }} size="small"
          columns={[
            { title: '№', dataIndex: 'id', width: 60 },
            { title: 'Магазин', dataIndex: 'shop_id', width: 90 },
            { title: 'Товар', dataIndex: 'product_id', width: 90, render: (v) => v ?? '—' },
            { title: 'Возможность', dataIndex: 'feature_key' },
            { title: 'Ставка', dataIndex: 'bid_amount', width: 110, render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
            { title: 'Потрачено', dataIndex: 'total_spent', width: 110, render: (v) => `${Number(v).toLocaleString('ru')} ₽` },
            { title: 'Статус', dataIndex: 'status', width: 120, render: (v: PromotionStatus) => <Tag color={statusMeta[v]?.color}>{statusMeta[v]?.label}</Tag> },
            { title: 'Создано', dataIndex: 'created_at', width: 110, render: (v) => dayjs(v).format('DD.MM.YY') },
          ]}
        />
      </Card>

      <Modal title={`Изменить: ${edit?.name || ''}`} open={!!edit} onCancel={() => setEdit(null)} onOk={save} okText="Сохранить">
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text>Название</Text>
            <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          </div>
          <div>
            <Text>Описание</Text>
            <Input.TextArea rows={2} value={draft.description || ''} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
          </div>
          <div>
            <Text>{edit?.pricing_mode === 'auction' ? 'Мин. ставка (резерв), ₽' : 'Цена, ₽'}</Text>
            <InputNumber min={0} style={{ width: '100%' }} value={draft.price ? Number(draft.price) : 0}
              onChange={(v) => setDraft({ ...draft, price: String(v ?? 0) })} />
          </div>
          {edit?.pricing_mode === 'auction' && (
            <div>
              <Text>Число слотов (победителей)</Text>
              <InputNumber min={0} style={{ width: '100%' }} value={draft.slots}
                onChange={(v) => setDraft({ ...draft, slots: v ?? 0 })} />
            </div>
          )}
        </Space>
      </Modal>
    </div>
  )
}
