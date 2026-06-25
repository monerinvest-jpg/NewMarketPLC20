import { useEffect, useState } from 'react'
import { Table, InputNumber, Typography, message, Input, Space, Button, Tag, Select, Modal } from 'antd'
import { adminApi } from '@/api'
import type { Shop } from '@/types'

const { Title } = Typography

const statusLabels: Record<string, { label: string; color: string }> = {
  pending: { label: 'На проверке', color: 'orange' },
  active: { label: 'Одобрен', color: 'green' },
  rejected: { label: 'Отклонён', color: 'red' },
  suspended: { label: 'Заблокирован', color: 'volcano' },
}

export default function AdminShops() {
  const [shops, setShops] = useState<Shop[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [editingCommission, setEditingCommission] = useState<Record<number, number | null>>({})
  const [modModal, setModModal] = useState<{ open: boolean; shop?: Shop; action?: string }>({ open: false })
  const [requisites, setRequisites] = useState<any>(null)
  const [reason, setReason] = useState('')

  const load = () => {
    setLoading(true)
    adminApi.listShops({ page, q: q || undefined, status: statusFilter })
      .then((res) => { setShops(res.items); setTotal(res.total) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page, statusFilter])

  const handleSaveCommission = async (shop: Shop) => {
    const value = editingCommission[shop.id]
    try {
      const updated = await adminApi.updateShop(shop.id, { commission_percent: value })
      setShops(shops.map((s) => (s.id === shop.id ? updated : s)))
      message.success('Комиссия обновлена')
      const ne = { ...editingCommission }; delete ne[shop.id]; setEditingCommission(ne)
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const handleModerate = async () => {
    if (!modModal.shop || !modModal.action) return
    try {
      const updated = await adminApi.moderateShop(modModal.shop.id, modModal.action, reason || undefined)
      setShops(shops.map((s) => (s.id === modModal.shop!.id ? updated : s)))
      message.success('Статус магазина обновлён')
      setModModal({ open: false }); setReason('')
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const openModerate = (shop: Shop, action: string) => {
    setModModal({ open: true, shop, action })
    setReason('')
    setRequisites(null)
    adminApi.shopRequisites(shop.id).then(setRequisites).catch(() => setRequisites(null))
  }

  return (
    <div>
      <Title level={3}>Магазины</Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          placeholder="Поиск по названию" value={q}
          onChange={(e) => setQ(e.target.value)} onSearch={() => { setPage(1); load() }}
          style={{ width: 240 }} allowClear
        />
        <Select
          placeholder="Все статусы" value={statusFilter} allowClear style={{ width: 180 }}
          onChange={(v) => { setStatusFilter(v); setPage(1) }}
          options={Object.entries(statusLabels).map(([k, v]) => ({ value: k, label: v.label }))}
        />
      </Space>

      <Table
        loading={loading}
        dataSource={shops}
        rowKey="id"
        pagination={{ current: page, total, pageSize: 20, onChange: setPage }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: 'Название', dataIndex: 'name' },
          {
            title: 'Статус', dataIndex: 'status', width: 130,
            render: (s) => <Tag color={statusLabels[s || 'active']?.color}>{statusLabels[s || 'active']?.label}</Tag>,
          },
          {
            title: 'Причина', dataIndex: 'moderation_reason', ellipsis: true,
            render: (v) => v || '—',
          },
          {
            title: 'Комиссия %', width: 160,
            render: (_, shop) => (
              <Space>
                <InputNumber
                  min={0} max={100} size="small" style={{ width: 70 }}
                  value={editingCommission[shop.id] !== undefined ? editingCommission[shop.id] : (shop.commission_percent ? parseFloat(shop.commission_percent) : null)}
                  onChange={(v) => setEditingCommission({ ...editingCommission, [shop.id]: v })}
                  placeholder="глоб."
                />
                {editingCommission[shop.id] !== undefined && (
                  <Button size="small" type="link" onClick={() => handleSaveCommission(shop)}>✓</Button>
                )}
              </Space>
            ),
          },
          {
            title: 'Модерация', width: 260,
            render: (_, shop) => (
              <Space wrap>
                {shop.status !== 'active' && (
                  <Button size="small" type="primary" onClick={() => openModerate(shop, 'active')}>Одобрить</Button>
                )}
                {shop.status === 'pending' && (
                  <Button size="small" danger onClick={() => openModerate(shop, 'rejected')}>Отклонить</Button>
                )}
                {shop.status === 'active' && (
                  <Button size="small" danger onClick={() => openModerate(shop, 'suspended')}>Заблокировать</Button>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={modModal.action === 'active' ? 'Одобрить магазин' : modModal.action === 'rejected' ? 'Отклонить магазин' : 'Заблокировать магазин'}
        open={modModal.open}
        onCancel={() => setModModal({ open: false })}
        onOk={handleModerate}
        okText="Подтвердить"
      >
        {requisites ? (
          <div style={{ marginBottom: 16, padding: 12, background: '#fafafa', borderRadius: 8, fontSize: 13 }}>
            <Typography.Text strong>Налоговые реквизиты</Typography.Text>
            <div>Режим: {requisites.tax_regime === 'self_employed' ? 'Самозанятость' : requisites.tax_regime === 'individual' ? 'ИП' : 'ООО'}</div>
            <div>{requisites.legal_name}</div>
            <div>ИНН: {requisites.inn}{requisites.ogrn ? ` · ОГРН: ${requisites.ogrn}` : ''}{requisites.kpp ? ` · КПП: ${requisites.kpp}` : ''}</div>
            {requisites.legal_address && <div>Адрес: {requisites.legal_address}</div>}
            {requisites.bank_account && <div>Счёт: {requisites.bank_account} ({requisites.bank_name}, БИК {requisites.bik})</div>}
          </div>
        ) : (
          <div style={{ marginBottom: 16 }}><Typography.Text type="secondary">Реквизиты не заполнены</Typography.Text></div>
        )}
        {modModal.action !== 'active' && (
          <Input.TextArea
            rows={3} value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="Причина (обязательно для отклонения/блокировки)"
          />
        )}
        {modModal.action === 'active' && <p>Магазин станет видимым на витрине и сможет продавать товары.</p>}
      </Modal>
    </div>
  )
}
