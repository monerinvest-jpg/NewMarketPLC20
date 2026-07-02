import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Row, Col, Card, Slider, Select, Input, Pagination,
  Typography, Button, Empty, Drawer, Grid, Badge, Tree
} from 'antd'
import { FilterOutlined } from '@ant-design/icons'
import { productsApi, categoriesApi, facetsApi } from '@/api'
import type { Product, Category, CatalogFacet } from '@/types'
import ProductCard, { ProductGridSkeleton } from '@/components/common/ProductCard'
import Seo from '@/components/common/Seo'

const { Title, Text } = Typography

export default function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  const page = parseInt(searchParams.get('page') || '1')
  const q = searchParams.get('q') || ''
  const categoryId = searchParams.get('category_id') || ''
  const sort = searchParams.get('sort') || 'created_at_desc'
  // priceDraft follows the slider handles live; priceRange (the one queries use)
  // is only committed on release — otherwise every dragged pixel fires the API.
  const [priceDraft, setPriceDraft] = useState<[number, number]>([0, 100000])
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

  // Shared filter controls — desktop sidebar Card and the mobile Drawer render the same content.
  const filtersContent = (
    <>
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <Text strong>Категория</Text>
              {categoryId && (
                <Button type="link" size="small" style={{ padding: 0 }} onClick={() => setParam('category_id', '')}>
                  сбросить
                </Button>
              )}
            </div>
            <Tree
              style={{ marginTop: 8, background: 'transparent' }}
              blockNode
              selectedKeys={categoryId ? [categoryId] : []}
              defaultExpandedKeys={
                // Expand the root that owns the selected child.
                categoryId
                  ? categories.filter((c) => c.children?.some((ch) => String(ch.id) === categoryId)).map((c) => String(c.id))
                  : []
              }
              onSelect={(keys) => setParam('category_id', (keys[0] as string) || '')}
              treeData={categories.map((c) => ({
                title: c.name,
                key: String(c.id),
                children: (c.children || []).map((ch) => ({ title: ch.name, key: String(ch.id) })),
              }))}
            />
          </div>
          <div style={{ marginBottom: 16 }}>
            <Text strong>Цена, ₽</Text>
            <Slider
              range
              min={0} max={100000} step={100}
              value={priceDraft}
              onChange={(v) => setPriceDraft(v as [number, number])}
              onChangeComplete={(v) => setPriceRange(v as [number, number])}
              tooltip={{ formatter: (v) => `${v?.toLocaleString('ru')} ₽` }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text type="secondary">{priceDraft[0].toLocaleString('ru')} ₽</Text>
              <Text type="secondary">{priceDraft[1].toLocaleString('ru')} ₽</Text>
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

  const categoryName = categoryId
    ? categories.flatMap((c) => [c, ...(c.children || [])])
        .find((c) => String(c.id) === categoryId)?.name
    : undefined

  return (
    <Row gutter={24}>
      <Seo
        title={q ? `Поиск: ${q}` : categoryName || 'Каталог'}
        description={categoryName ? `${categoryName} — купить изделия ручной работы на маркетплейсе.` : undefined}
      />
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
          <ProductGridSkeleton count={9} colProps={{ xs: 12, sm: 12, md: 12, lg: 8 }} />
        ) : products.length === 0 ? (
          <Empty description="Товары не найдены" />
        ) : (
          <>
            <Row gutter={[16, 16]}>
              {products.map((p) => (
                <Col key={p.id} xs={12} sm={12} lg={8}>
                  <ProductCard product={p} coverHeight={180} />
                </Col>
              ))}
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
