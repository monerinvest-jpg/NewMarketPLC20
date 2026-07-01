import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, Table, Button, Typography, Empty, Image, Rate, message } from 'antd'
import { useCompareStore } from '@/store/compareStore'
import { attributesApi } from '@/api'
import type { ProductAttributeValue } from '@/types'

const { Title, Text } = Typography

export default function ComparePage() {
  const { items, remove, clear } = useCompareStore()
  const [attrsByProduct, setAttrsByProduct] = useState<Record<number, ProductAttributeValue[]>>({})

  useEffect(() => {
    // Load attributes for each compared product
    Promise.all(
      items.map((p) => attributesApi.getForProduct(p.id).then((a) => [p.id, a] as const).catch(() => [p.id, []] as const))
    ).then((results) => {
      const map: Record<number, ProductAttributeValue[]> = {}
      results.forEach(([id, a]) => { map[id] = a })
      setAttrsByProduct(map)
    })
  }, [items])

  if (items.length === 0) {
    return <Empty description="Список сравнения пуст. Добавьте товары из каталога." style={{ margin: 80 }} />
  }

  // Collect all distinct attribute names across compared products
  const allAttrNames = Array.from(new Set(
    Object.values(attrsByProduct).flat().map((a) => a.attribute.name)
  ))

  const rows = [
    {
      key: 'price', label: 'Цена',
      render: (pid: number) => {
        const p = items.find((x) => x.id === pid)!
        return <Text strong style={{ color: '#b45309' }}>{parseFloat(p.price).toLocaleString('ru')} ₽</Text>
      },
    },
    {
      key: 'rating', label: 'Рейтинг',
      render: (pid: number) => {
        const p = items.find((x) => x.id === pid)!
        return <Rate disabled value={parseFloat(p.rating)} allowHalf style={{ fontSize: 12 }} />
      },
    },
    ...allAttrNames.map((name) => ({
      key: `attr-${name}`, label: name,
      render: (pid: number) => {
        const found = (attrsByProduct[pid] || []).find((a) => a.attribute.name === name)
        return found ? found.value : '—'
      },
    })),
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Сравнение товаров</Title>
        <Button onClick={clear}>Очистить</Button>
      </div>

      <Card style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ width: 160, textAlign: 'left', padding: 12 }} />
              {items.map((p) => {
                const img = p.images.find((i) => i.is_main) || p.images[0]
                return (
                  <th key={p.id} style={{ padding: 12, minWidth: 180, verticalAlign: 'top' }}>
                    <div style={{ textAlign: 'center' }}>
                      {img && <Image src={img.url} width={120} height={120} style={{ objectFit: 'cover', borderRadius: 8 }} />}
                      <div style={{ marginTop: 8 }}>
                        <Link to={`/products/${p.id}`}><Text style={{ fontSize: 13 }}>{p.title}</Text></Link>
                      </div>
                      <Button size="small" danger type="text" onClick={() => remove(p.id)}>Убрать</Button>
                    </div>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} style={{ borderTop: '1px solid #f0f0f0' }}>
                <td style={{ padding: 12, fontWeight: 500, color: '#888' }}>{row.label}</td>
                {items.map((p) => (
                  <td key={p.id} style={{ padding: 12, textAlign: 'center' }}>{row.render(p.id)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
