import { useEffect, useState } from 'react'
import { Card, Table, Typography, InputNumber, Input, Button, message, Spin } from 'antd'
import { adminApi } from '@/api'
import type { Currency } from '@/types'

const { Title, Paragraph } = Typography

export default function AdminCurrencies() {
  const [currencies, setCurrencies] = useState<Currency[]>([])
  const [loading, setLoading] = useState(true)
  const [edits, setEdits] = useState<Record<string, { rate: number; symbol: string }>>({})

  const load = () => {
    setLoading(true)
    adminApi.listCurrencies().then((list) => {
      setCurrencies(list)
      const e: Record<string, { rate: number; symbol: string }> = {}
      list.forEach((c) => { e[c.code] = { rate: parseFloat(c.rate), symbol: c.symbol } })
      setEdits(e)
    }).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const save = async (code: string) => {
    try {
      await adminApi.upsertCurrency(code, edits[code].rate, edits[code].symbol)
      message.success(`Курс ${code} обновлён`)
      load()
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  if (loading) return <Spin size="large" style={{ display: 'block', margin: 80 }} />

  return (
    <div style={{ maxWidth: 720 }}>
      <Title level={3}>Валюты</Title>
      <Paragraph type="secondary">
        Базовая валюта — рубль (RUB, курс 1). Для остальных валют укажите коэффициент: сумма в валюте = сумма в рублях × курс.
      </Paragraph>
      <Card>
        <Table
          dataSource={currencies}
          rowKey="code"
          pagination={false}
          columns={[
            { title: 'Код', dataIndex: 'code', width: 100 },
            {
              title: 'Курс от RUB', width: 200,
              render: (_, c) => (
                <InputNumber
                  min={0} step={0.001} value={edits[c.code]?.rate} disabled={c.code === 'RUB'}
                  onChange={(v) => setEdits({ ...edits, [c.code]: { ...edits[c.code], rate: v ?? 0 } })}
                  style={{ width: '100%' }}
                />
              ),
            },
            {
              title: 'Символ', width: 120,
              render: (_, c) => (
                <Input
                  value={edits[c.code]?.symbol} maxLength={8}
                  onChange={(e) => setEdits({ ...edits, [c.code]: { ...edits[c.code], symbol: e.target.value } })}
                />
              ),
            },
            {
              title: '', render: (_, c) => c.code !== 'RUB' && (
                <Button size="small" type="primary" onClick={() => save(c.code)}>Сохранить</Button>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}
