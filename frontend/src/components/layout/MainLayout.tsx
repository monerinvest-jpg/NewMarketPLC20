import { Outlet, Link, useNavigate } from 'react-router-dom'
import { Layout, Menu, Button, Input, Badge, Avatar, Dropdown, Space, Select } from 'antd'
import {
  ShoppingCartOutlined, UserOutlined, SearchOutlined,
  ShopOutlined, MessageOutlined, LogoutOutlined, HeartOutlined, SwapOutlined,
  CustomerServiceOutlined, GiftOutlined, CrownOutlined,
} from '@ant-design/icons'
import NotificationBell from '@/components/common/NotificationBell'
import { useCompareStore } from '@/store/compareStore'
import { useCurrencyStore } from '@/store/currencyStore'
import { currencyApi } from '@/api'
import { useAuthStore } from '@/store/authStore'
import { useCartStore } from '@/store/cartStore'
import { useEffect, useState } from 'react'
import { useNavigate as useNav } from 'react-router-dom'

const { Header, Content, Footer } = Layout

export default function MainLayout() {
  const { user, logout } = useAuthStore()
  const { fetchCart, totalItems } = useCartStore()
  const compareCount = useCompareStore((s) => s.items.length)
  const { current: currentCurrency, rates, setCurrent, setRates } = useCurrencyStore()
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    if (user) fetchCart()
  }, [user])

  useEffect(() => {
    currencyApi.list().then(setRates).catch(() => {})
  }, [])

  const handleSearch = () => {
    if (searchQuery.trim()) {
      navigate(`/catalog?q=${encodeURIComponent(searchQuery.trim())}`)
    }
  }

  const userMenuItems = [
    { key: 'profile', label: <Link to="/profile">Профиль</Link>, icon: <UserOutlined /> },
    { key: 'orders', label: <Link to="/orders">Мои заказы</Link> },
    { key: 'returns', label: <Link to="/returns">Возвраты</Link> },
    { key: 'favorites', label: <Link to="/favorites">Избранное</Link>, icon: <HeartOutlined /> },
    { key: 'wishlists', label: <Link to="/wishlists">Мои коллекции</Link> },
    { key: 'addresses', label: <Link to="/addresses">Мои адреса</Link> },
    { key: 'my-subscriptions', label: <Link to="/my-subscriptions">Подписки на товары</Link> },
    { key: 'referral', label: <Link to="/referral">Реферальная программа</Link> },
    { key: 'security', label: <Link to="/security">Безопасность (2FA)</Link> },
    { key: 'support', label: <Link to="/support">Поддержка</Link>, icon: <CustomerServiceOutlined /> },
    { key: 'following', label: <Link to="/following">Мои подписки</Link>, icon: <ShopOutlined /> },
    { key: 'disputes', label: <Link to="/disputes">Споры</Link> },
    { key: 'gift-certificates', label: <Link to="/gift-certificates">Сертификаты и промо-баланс</Link>, icon: <GiftOutlined /> },
    { key: 'loyalty', label: <Link to="/loyalty">Программа лояльности</Link>, icon: <CrownOutlined /> },
    ...(user?.role === 'support' || user?.role === 'moderator' || user?.role === 'superadmin'
      ? [{ key: 'dispute-desk', label: <Link to="/dispute-desk">Арбитраж споров</Link> }]
      : []),
    ...(user?.role === 'support' || user?.role === 'moderator' || user?.role === 'superadmin'
      ? [{ key: 'support-desk', label: <Link to="/support-desk">Стол поддержки</Link> }]
      : []),
    ...(user?.role === 'seller' || user?.role === 'superadmin'
      ? [
          { key: 'seller', label: <Link to="/seller">Личный кабинет продавца</Link>, icon: <ShopOutlined /> },
          { key: 'seller-analytics', label: <Link to="/seller/analytics">Аналитика продаж</Link> },
          { key: 'seller-reviews', label: <Link to="/seller/reviews">Отзывы на товары</Link> },
          { key: 'seller-returns', label: <Link to="/seller/returns">Возвраты</Link> },
          { key: 'seller-coupons', label: <Link to="/seller/coupons">Мои промокоды</Link> },
          { key: 'seller-import', label: <Link to="/seller/import">Импорт товаров (CSV)</Link> },
          { key: 'seller-inventory', label: <Link to="/seller/inventory">Склад</Link> },
          { key: 'seller-flash-sales', label: <Link to="/seller/flash-sales">Акции и распродажи</Link> },
          { key: 'seller-chat-templates', label: <Link to="/seller/chat-templates">Чат: шаблоны и часы</Link> },
          { key: 'seller-requisites', label: <Link to="/seller/requisites">Налоговые реквизиты</Link> },
          { key: 'seller-payouts', label: <Link to="/seller/payouts">Вывод средств</Link> },
          { key: 'seller-plan', label: <Link to="/seller/plan">Тариф и комиссия</Link> },
          { key: 'seller-promotion', label: <Link to="/seller/promotion">Продвижение</Link> },
          { key: 'seller-promo-rules', label: <Link to="/seller/promo-rules">Акции и наборы</Link> },
          { key: 'seller-disputes', label: <Link to="/seller/disputes">Споры по заказам</Link> },
        ]
      : []),
    ...(user?.role === 'moderator' || user?.role === 'superadmin'
      ? [{ key: 'admin', label: <Link to="/admin">Админ-панель</Link> }]
      : []),
    { type: 'divider' as const },
    {
      key: 'logout',
      label: 'Выйти',
      icon: <LogoutOutlined />,
      danger: true,
      onClick: () => { logout(); navigate('/') },
    },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          position: 'sticky', top: 0, zIndex: 100,
          background: '#fff', padding: '0 24px',
          display: 'flex', alignItems: 'center', gap: 16,
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        }}
      >
        {/* Logo */}
        <Link to="/" style={{ fontSize: 22, fontWeight: 700, color: '#f97316', whiteSpace: 'nowrap' }}>
          🛍️ Marketplace
        </Link>

        {/* Search */}
        <Input.Search
          placeholder="Поиск товаров..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onSearch={handleSearch}
          style={{ flex: 1, maxWidth: 600 }}
          size="large"
        />

        {/* Nav */}
        <Space size={8}>
          <Link to="/catalog">
            <Button type="text">Каталог</Button>
          </Link>

          {user ? (
            <>
              <Select
                value={currentCurrency}
                onChange={setCurrent}
                size="small"
                style={{ width: 80 }}
                options={rates.map((r) => ({ value: r.code, label: `${r.symbol} ${r.code}` }))}
              />
              <Link to="/chat">
                <Button type="text" icon={<MessageOutlined style={{ fontSize: 18 }} />} />
              </Link>
              <NotificationBell />
              <Link to="/compare">
                <Badge count={compareCount} size="small">
                  <Button type="text" icon={<SwapOutlined style={{ fontSize: 18 }} />} />
                </Badge>
              </Link>
              <Link to="/cart">
                <Badge count={totalItems()} size="small">
                  <Button type="text" icon={<ShoppingCartOutlined style={{ fontSize: 20 }} />} />
                </Badge>
              </Link>
              <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
                <Avatar style={{ background: '#f97316', cursor: 'pointer' }}>
                  {user.full_name[0]?.toUpperCase()}
                </Avatar>
              </Dropdown>
            </>
          ) : (
            <>
              <Link to="/login"><Button>Войти</Button></Link>
              <Link to="/register"><Button type="primary">Регистрация</Button></Link>
            </>
          )}
        </Space>
      </Header>

      <Content style={{ padding: '24px', maxWidth: 1280, margin: '0 auto', width: '100%' }}>
        <Outlet />
      </Content>

      <Footer style={{ textAlign: 'center', background: '#fff', borderTop: '1px solid #f0f0f0' }}>
        © {new Date().getFullYear()} Marketplace. Все права защищены.
      </Footer>
    </Layout>
  )
}
