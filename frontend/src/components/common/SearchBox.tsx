import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AutoComplete, Input } from 'antd'
import { SearchOutlined, ShopOutlined, TagsOutlined } from '@ant-design/icons'
import { productsApi } from '@/api'

// Header search with live suggestions (products with thumbnails, categories,
// shops). Debounced; falls back to plain catalog search on Enter.
export default function SearchBox({ size = 'large', style }: { size?: 'large' | 'middle'; style?: React.CSSProperties }) {
  const navigate = useNavigate()
  const [value, setValue] = useState('')
  const [options, setOptions] = useState<any[]>([])
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  const goCatalog = (q: string) => {
    if (q.trim()) navigate(`/catalog?q=${encodeURIComponent(q.trim())}`)
  }

  const fetchSuggestions = (q: string) => {
    if (q.trim().length < 2) { setOptions([]); return }
    productsApi.suggest(q.trim()).then((res) => {
      const opts: any[] = []
      if (res.products.length) {
        opts.push({
          label: <span style={{ fontSize: 12, color: '#a8957f' }}>Товары</span>,
          options: res.products.map((p) => ({
            value: `product:${p.id}`,
            label: (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {p.image_url
                  ? <img src={p.image_url} alt="" style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 6 }} />
                  : <span style={{ width: 32, textAlign: 'center' }}>🪵</span>}
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.title}</span>
                <b style={{ color: '#b45309', whiteSpace: 'nowrap' }}>{parseFloat(p.price).toLocaleString('ru')} ₽</b>
              </div>
            ),
          })),
        })
      }
      if (res.categories.length) {
        opts.push({
          label: <span style={{ fontSize: 12, color: '#a8957f' }}>Категории</span>,
          options: res.categories.map((c) => ({
            value: `category:${c.id}`,
            label: <span><TagsOutlined style={{ marginRight: 8, color: '#b45309' }} />{c.name}</span>,
          })),
        })
      }
      if (res.shops.length) {
        opts.push({
          label: <span style={{ fontSize: 12, color: '#a8957f' }}>Магазины</span>,
          options: res.shops.map((s) => ({
            value: `shop:${s.id}`,
            label: <span><ShopOutlined style={{ marginRight: 8, color: '#b45309' }} />{s.name}</span>,
          })),
        })
      }
      setOptions(opts)
    }).catch(() => setOptions([]))
  }

  return (
    <AutoComplete
      value={value}
      options={options}
      style={style}
      popupMatchSelectWidth
      onSearch={(q) => {
        setValue(q)
        clearTimeout(debounceRef.current)
        debounceRef.current = setTimeout(() => fetchSuggestions(q), 250)
      }}
      onSelect={(val: string) => {
        const [kind, id] = val.split(':')
        setValue('')
        setOptions([])
        if (kind === 'product') navigate(`/products/${id}`)
        else if (kind === 'category') navigate(`/catalog?category_id=${id}`)
        else if (kind === 'shop') navigate(`/shops/${id}`)
      }}
    >
      <Input.Search
        placeholder="Поиск товаров, магазинов…"
        size={size}
        enterButton={<SearchOutlined />}
        onSearch={(q) => { setOptions([]); goCatalog(q) }}
        aria-label="Поиск"
      />
    </AutoComplete>
  )
}
