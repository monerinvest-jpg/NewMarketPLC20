import { useEffect, useState } from 'react'
import {
  Card, Table, Typography, Tag, Select, Space, Spin, Button, Modal,
  Descriptions, message, InputNumber, Row, Col, Statistic,
} from 'antd'
import { adminApi } from '@/api'
import type { FiscalReceipt, FiscalReceiptStatus } from '@/types'
import dayjs from 'dayjs'

const { Title, Text } = Typography

const statusMeta: Record<FiscalReceiptStatus, { color: string; label: string }> = {
  succeeded: { color: 'green', label: 'Зарегистрирован' },
  pending: { color: 'gold', label: 'Ожидает ОФД' },
  canceled: { color: 'volcano', label: 'Отклонён' },
  failed: { color: 'red', label: 'Ошибка' },
}

const typeMeta: Record<string, { color: string; label: string }> = {
  income: { color: 'blue', label: 'Приход' },
  income_refund: { color: 'purple', label: 'Возврат прихода' },
}

export default function AdminFiscalReceipts() {
  const [items, setItems] = useState<FiscalReceipt[]>([])
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState<string | undefined>()
  const [type, setType] = useState<string | undefined>()
  const [orderId, setOrderId] = useState<number | undefined>()
  const [selected, setSelected] = useState<FiscalReceipt | null>(null)
  const [retrying, setRetrying] = useState<number | null>(null)

  const load = () => {
    setLoading(true)
    adminApi.listFiscalReceipts({ status, type, order_id: orderId, page, page_size: 50 })
      .then((res) => { setItems(res.items); setTotal(res.total); setCounts(res.counts || {}) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [page, status, type, orderId])

  const retry = (id: number) => {
    setRetrying(id)
    adminApi.retryFiscalReceipt(id)
      .then((res) => { message.success(`Чек отправлен повторно: ${res.status}`); load() })
      .catch((e) => message.error(e?.response?.data?.detail || 'Не удалось отправить чек'))
      .finally(() => setRetrying(null))
  }

  return (
    <div>
      <Title level={3}>Фискальные чеки (54-ФЗ)</Title>
      <Text type="secondary">
        Чеки регистрируются в ОФД автоматически через встроенную фискализацию ЮKassa.
        Здесь отслеживается статус регистрации; зависшие и ошибочные чеки можно отправить повторно.
      </Text>

      <Row gutter={16} style={{ margin: '16px 0' }}>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Зарегистрировано" value={counts.succeeded || 0} valueStyle={{ color: '#3f8600' }} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Ожидают ОФД" value={counts.pending || 0} valueStyle={{ color: '#d48806' }} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Отклонены" value={counts.canceled || 0} valueStyle={{ color: '#d4380d' }} /></Card></Col>
        <Col xs={12} md={6}><Card size="small"><Statistic title="Ошибки" value={counts.failed || 0} valueStyle={{ color: '#cf1322' }} /></Card></Col>
      </Row>

      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          placeholder="Статус" allowClear style={{ width: 180 }}
          value={status} onChange={(v) => { setStatus(v); setPage(1) }}
          options={Object.entries(statusMeta).map(([v, m]) => ({ value: v, label: m.label }))}
        />
        <Select
          placeholder="Тип" allowClear style={{ width: 180 }}
          value={type} onChange={(v) => { setType(v); setPage(1) }}
          options={Object.entries(typeMeta).map(([v, m]) => ({ value: v, label: m.label }))}
        />
        <InputNumber
          placeholder="№ заказа" style={{ width: 140 }} min={1}
          value={orderId} onChange={(v) => { setOrderId(v || undefined); setPage(1) }}
        />
        <Button onClick={load}>Обновить</Button>
      </Space>

      <Card>
        <Spin spinning={loading}>
          <Table<FiscalReceipt>
            dataSource={items}
            rowKey="id"
            pagination={{ current: page, total, pageSize: 50, onChange: setPage }}
            columns={[
              { title: '№', dataIndex: 'id', width: 70 },
              { title: 'Заказ', dataIndex: 'order_id', width: 90, render: (v) => `#${v}` },
              { title: 'Тип', dataIndex: 'type', width: 150, render: (v) => <Tag color={typeMeta[v]?.color}>{typeMeta[v]?.label || v}</Tag> },
              { title: 'Статус', dataIndex: 'status', width: 160, render: (v: FiscalReceiptStatus) => <Tag color={statusMeta[v]?.color}>{statusMeta[v]?.label || v}</Tag> },
              { title: 'Покупатель', dataIndex: 'customer_contact', ellipsis: true },
              { title: 'Сумма', dataIndex: 'total', width: 110, render: (v) => `${Number(v).toLocaleString('ru-RU')} ₽` },
              { title: 'Создан', dataIndex: 'created_at', width: 150, render: (v) => dayjs(v).format('DD.MM.YY HH:mm') },
              {
                title: '', width: 200, render: (_, r) => (
                  <Space>
                    <Button size="small" onClick={() => setSelected(r)}>Детали</Button>
                    {(r.status === 'failed' || r.status === 'canceled') && (
                      <Button size="small" type="primary" loading={retrying === r.id} onClick={() => retry(r.id)}>
                        Повторить
                      </Button>
                    )}
                  </Space>
                ),
              },
            ]}
          />
        </Spin>
      </Card>

      <Modal
        open={!!selected}
        title={selected ? `Чек #${selected.id} · заказ #${selected.order_id}` : ''}
        footer={null}
        onCancel={() => setSelected(null)}
        width={680}
      >
        {selected && (
          <>
            <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
              <Descriptions.Item label="Тип"><Tag color={typeMeta[selected.type]?.color}>{typeMeta[selected.type]?.label}</Tag></Descriptions.Item>
              <Descriptions.Item label="Статус"><Tag color={statusMeta[selected.status]?.color}>{statusMeta[selected.status]?.label}</Tag></Descriptions.Item>
              <Descriptions.Item label="Покупатель" span={2}>{selected.customer_contact}</Descriptions.Item>
              <Descriptions.Item label="Сумма">{Number(selected.total).toLocaleString('ru-RU')} ₽</Descriptions.Item>
              <Descriptions.Item label="СНО (код)">{selected.tax_system_code ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="ФД">{selected.fiscal_document_number ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="ФН">{selected.fiscal_storage_number ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="ФПД">{selected.fiscal_attribute ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="Зарегистрирован">{selected.registered_at ? dayjs(selected.registered_at).format('DD.MM.YY HH:mm') : '—'}</Descriptions.Item>
              {selected.error && <Descriptions.Item label="Ошибка" span={2}><Text type="danger">{selected.error}</Text></Descriptions.Item>}
            </Descriptions>

            <Text strong>Позиции чека</Text>
            <Table
              size="small"
              style={{ marginTop: 8 }}
              dataSource={selected.items.map((it, i) => ({ key: i, ...it }))}
              pagination={false}
              columns={[
                { title: 'Наименование', dataIndex: 'description', ellipsis: true },
                { title: 'Кол-во', dataIndex: 'quantity', width: 80 },
                { title: 'Цена', dataIndex: 'amount', width: 110, render: (a) => `${Number(a?.value).toLocaleString('ru-RU')} ₽` },
                { title: 'НДС', dataIndex: 'vat_code', width: 70 },
              ]}
            />
          </>
        )}
      </Modal>
    </div>
  )
}
