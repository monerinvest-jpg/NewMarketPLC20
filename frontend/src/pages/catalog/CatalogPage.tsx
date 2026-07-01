import { useEffect, useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import {
  Row, Col, Card, Slider, Select, Input, Pagination,
  Typography, Button, Spin, Empty, Rate, Drawer, Grid, Badge
} from 'antd'
import { ShoppingCartOutlined, SwapOutlined, FilterOutlined } from '@ant-design/icons'
import { productsApi, categoriesApi, facetsApi } from '@/api'
import type { Product, Category, CatalogFacet } from '@/types'
import { useCartStore } from '@/store/cartStore'
import { useAuthStore } from '@/store/authStore'
import { useCompareStore } from '@/store/compareStore'
import { message } from 'antd'

const { Title, Text } = Typography

export default function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const { addItem } = useCartStore()
  const { user } = useAuthStore()
  const compare = useCompareStore()

  const page = parseInt(searchParams.get('page') || '1')
  const q = searchParams.get('q') || ''
  const categoryId = searchParams.get('category_id') || ''
  const sort = searchParams.get('sort') || 'created_at_desc'
  const [priceRange, setPriceRange] = useState<[number, number]>([0, 100000])
  const [facets, setFacets] = useState<CatalogFacet[]>([])
  const [selectedAttrs, setSelectedAttrs] = useState<Record<number, string>>({})
  // Mobile: the filter sidebar collapses into a drawer behind a "Фильтры" button.
  const screens = Grid.useBreakpoint()
  const isMobile = screens.md === false
  const [filtersOpen, setFiltersOpen] = useState(false)
  const activeFilterCount =
    (categoryId ? 1 : 0) +
    (priceRange[0] > 0 || priceRange[1] < 100000 ? 1 : 0) +
    Object.values(selectedAttrs).filter(Boolean).length

  useEffect(() => {
    categoriesApi.list().then(setCategories)
  }, [])

  useEffect(() => {
    facetsApi.get(categoryId ? parseInt(categoryId) : undefined)
      .then(setFacets).catch(() => setFacets([]))
    setSelectedAttrs({})
  }, [categoryId])

  useEffect(() => {
    setLoading(true)
    const attrsParam = Object.entries(selectedAttrs)
      .filter(([, v]) => v)
      .map(([id, v]) => `${id}:${v}`)
      .join(',')
    productsApi.list({
      page,
      page_size: 20,
      q: q || undefined,
      category_id: categoryId ? parseInt(categoryId) : undefined,
      sort,
      min_price: priceRange[0] || undefined,
      max_price: priceRange[1] < 100000 ? priceRange[1] : undefined,
      attrs: attrsParam || undefined,
    }).then((res) => {
      setProducts(res.items)
      setTotal(res.total)
    }).finally(() => setLoading(false))
  }, [searchParams, priceRange, selectedAttrs])

  const setParam = (key: string, value: string) => {
    const p = new URLSearchParams(searchParams)
    if (value) p.set(key, value); else p.delete(key)
    p.set('page', '1')
    setSearchParams(p)
  }

  const handleAddToCart = async (e: React.MouseEvent, productId: number) => {
    e.preventDefault()
    // Guests can add too — the cart store keeps a local copy until login.
    try {
      await addItem(productId)
      message.success('Добавлено в корзину')
    } catch {
      message.error('Ошибка')
    }
  }

  // Shared filter controls — desktop sidebar Card and the mobile Drawer render the same content.
  const filtersContent = (
    <>
          <div style={{ marginBottom: 16 }}>
            <Text strong>Категория</Text>
            <Select
              style={{ width: '100%', marginTop: 8 }}
              value={categoryId || undefined}
              placeholder="Все категории"
              allowClear
              onChange={(v) => setParam('category_id', v || '')}
              options={categories.map((c) => ({ value: String(c.id), label: c.name }))}
            />
          </div>
          <div style={{ marginBottom: 16 }}>
            <Text strong>Цена, ₽</Text>
            <Slider
              range
              min={0} max={100000} step={100}
              value={priceRange}
              onChange={(v) => setPriceRange(v as [number, number])}
              tooltip={{ formatter: (v) => `${v?.toLocaleString('ru')} ₽` }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text type="secondary">{priceRange[0].toLocaleString('ru')} ₽</Text>
              <Text type="secondary">{priceRange[1].toLocaleString('ru')} ₽</Text>
            </div>
          </div>

          {facets.map((facet) => (
            <div key={facet.id} style={{ marginBottom: 12 }}>
              <Text strong>{facet.name}</Text>
              <Select
                allowClear
                placeholder="Любое"
                style={{ width: '100%', marginTop: 8 }}
                value={selectedAttrs[facet.id] || undefined}
                onChange={(v) => setSelectedAttrs({ ...selectedAttrs, [facet.id]: v || '' })}
                options={facet.values.map((val) => ({ value: val, label: val }))}
              />
            </div>
          ))}

          <div>
            <Text strong>Сортировка</Text>
            <Select
              style={{ width: '100%', marginTop: 8 }}
              value={sort}
              onChange={(v) => setParam('sort', v)}
              options={[
                { value: 'created_at_desc', label: 'Новинки' },
                { value: 'price_asc', label: 'Цена: по возрастанию' },
                { value: 'price_desc', label: 'Цена: по убыванию' },
                { value: 'rating_desc', label: 'По рейтингу' },
                { value: 'views_desc', label: 'Популярные' },
              ]}
            />
          </div>
    </>
  )

  return (
    <Row gutter={24}>
      {/* Filters — desktop sidebar (hidden on mobile in favour of the drawer) */}
      <Col xs={0} md={6}>
        <Card title="Фильтры" size="small" style={{ marginBottom: 16 }}>
          {filtersContent}
        </Card>
      </Col>

      {/* Mobile filters drawer */}
      <Drawer
        title="Фильтры"
        placement="left"
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        width={300}
      >
        {filtersContent}
        <Button type="primary" block style={{ marginTop: 8 }} onClick={() => setFiltersOpen(false)}>
          Показать ({total})
        </Button>
      </Drawer>

      {/* Products grid */}
      <Col xs={24} md={18}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          <Title level={4} style={{ margin: 0 }}>
            {q ? `Результаты поиска: "${q}"` : 'Все товары'} ({total})
          </Title>
          {isMobile ? (
            <Badge count={activeFilterCount} size="small">
              <Button icon={<FilterOutlined />} onClick={() => setFiltersOpen(true)}>
                Фильтры
              </Button>
            </Badge>
          ) : (
            <Input.Search
              placeholder="Поиск..."
              defaultValue={q}
              onSearch={(v) => setParam('q', v)}
              style={{ width: 260 }}
            />
          )}
        </div>

        {loading ? (
          <Spin style={{ display: 'block', textAlign: 'center', margin: 80 }} />
        ) : products.length === 0 ? (
          <Empty description="Товары не найдены" />
        ) : (
          <>
            <Row gutter={[16, 16]}>
              {products.map((p) => {
                const img = p.images.find((i) => i.is_main) || p.images[0]
                return (
                  <Col key={p.id} xs={12} sm={12} lg={8}>
                    <Link to={`/products/${p.id}`}>
                      <Card
                        hoverable className="product-card" style={{ position: 'relative' }}
                        cover={
                          <div style={{ height: 180, background: '#f5f5f5', overflow: 'hidden' }}>
                            {img ? (
                              <img src={img.url} alt={p.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            ) : (
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: 40 }}>🛍️</div>
                            )}
                          </div>
                        }
                        bodyStyle={{ padding: '12px' }}
                        actions={[
                          <Button
                            key="cart" type="primary" icon={<ShoppingCartOutlined />} size="small"
                            onClick={(e) => handleAddToCart(e, p.id)}
                          >
                            В корзину
                          </Button>
                        ]}
                      >
                        <Text ellipsis={{ tooltip: p.title }} style={{ display: 'block', marginBottom: 4 }}>
                          {p.title}
                        </Text>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                          {p.flash_price ? (
                            <>
                              <Text strong style={{ color: '#cf1322', fontSize: 16 }}>
                                {parseFloat(p.flash_price).toLocaleString('ru')} ₽
                              </Text>
                              <Text delete type="secondary" style={{ fontSize: 12 }}>
                                {parseFloat(p.price).toLocaleString('ru')} ₽
                              </Text>
                            </>
                          ) : (
                            <>
                              <Text strong style={{ color: '#f97316', fontSize: 16 }}>
                                {parseFloat(p.price).toLocaleString('ru')} ₽
                              </Text>
                              {p.compare_at_price && (
                                <Text delete type="secondary" style={{ fontSize: 12 }}>
                                  {parseFloat(p.compare_at_price).toLocaleString('ru')} ₽
                                </Text>
                              )}
                            </>
                          )}
                        </div>
                        {p.rating > 0 && (
                          <Rate disabled defaultValue={parseFloat(p.rating)} allowHalf style={{ fontSize: 12 }} />
                        )}
                        <Button
                          size="small" type="text" icon={<SwapOutlined />}
                          style={{ position: 'absolute', top: 8, right: 8, background: 'rgba(255,255,255,0.85)' }}
                          onClick={(e) => {
                            e.preventDefault()
                            compare.toggle(p)
                            message.success(compare.has(p.id) ? 'Убрано из сравнения' : 'Добавлено к сравнению')
                          }}
                          title="Сравнить"
                        />
                      </Card>
                    </Link>
                  </Col>
                )
              })}
            </Row>
            <Pagination
              current={page}
              total={total}
              pageSize={20}
              style={{ marginTop: 24, textAlign: 'center' }}
              onChange={(p) => setParam('page', String(p))}
              showSizeChanger={false}
            />
          </>
        )}
      </Col>
    </Row>
  )
}
