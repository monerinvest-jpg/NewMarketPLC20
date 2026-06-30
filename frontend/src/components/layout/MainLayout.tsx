import { Outlet, Link, useNavigate } from 'react-router-dom'
import { Layout, Menu, Button, Input, Badge, Avatar, Dropdown, Space, Select } from 'antd'
import {
  ShoppingCartOutlined, UserOutlined,
  ShopOutlined, MessageOutlined, LogoutOutlined, HeartOutlined, SwapOutlined,
  CustomerServiceOutlined, GiftOutlined, SettingOutlined,
} from '@ant-design/icons'
import NotificationBell from '@/components/common/NotificationBell'
import { useCompareStore } from '@/store/compareStore'
import { useCurrencyStore } from '@/store/currencyStore'
import { currencyApi } from '@/api'
import { useAuthStore } from '@/store/authStore'
import { useCartStore } from '@/store/cartStore'
import { useEffect, useState } from 'react'
import { useNavigate as useNav } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

const { Header, Content, Footer } = Layout

export default function MainLayout() {
  const { user, logout } = useAuthStore()
  const { fetchCart, totalItems } = useCartStore()
  const compareCount = useCompareStore((s) => s.items.length)
  const { current: currentCurrency, rates, setCurrent, setRates } = useCurrencyStore()
  const navigate = useNavigate()
  const { t, i18n } = useTranslation()
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

  const isStaff = user?.role === 'support' || user?.role === 'moderator' || user?.role === 'superadmin'
  const isSeller = user?.role === 'seller' || user?.role === 'superadmin'

  // Grouped account menu — submenus keep the (large) cabinet scannable instead
  // of one long flat list.
  const userMenuItems = [
    { key: 'profile', label: <Link to="/profile">Профиль</Link>, icon: <UserOutlined /> },
    {
      key: 'grp-purchases', label: 'Покупки', icon: <ShoppingCartOutlined />,
      children: [
        { key: 'orders', label: <Link to="/orders">Мои заказы</Link> },
        { key: 'downloads', label: <Link to="/my/downloads">Мои покупки</Link> },
        { key: 'learning', label: <Link to="/learning">Обучение</Link> },
        { key: 'returns', label: <Link to="/returns">Возвраты</Link> },
        { key: 'disputes', label: <Link to="/disputes">Споры</Link> },
        { key: 'my-subscriptions', label: <Link to="/my-subscriptions">Подписки на товары</Link> },
      ],
    },
    {
      key: 'grp-lists', label: 'Избранное и коллекции', icon: <HeartOutlined />,
      children: [
        { key: 'favorites', label: <Link to="/favorites">Избранное</Link> },
        { key: 'wishlists', label: <Link to="/wishlists">Мои коллекции</Link> },
        { key: 'following', label: <Link to="/following">Магазины, на которые я подписан</Link> },
      ],
    },
    {
      key: 'grp-bonus', label: 'Бонусы и баланс', icon: <GiftOutlined />,
      children: [
        { key: 'referral', label: <Link to="/referral">Реферальная программа</Link> },
        { key: 'gift-certificates', label: <Link to="/gift-certificates">Сертификаты и промо-баланс</Link> },
        { key: 'loyalty', label: <Link to="/loyalty">Программа лояльности</Link> },
      ],
    },
    {
      key: 'grp-account', label: 'Аккаунт', icon: <SettingOutlined />,
      children: [
        { key: 'addresses', label: <Link to="/addresses">Мои адреса</Link> },
        { key: 'security', label: <Link to="/security">Безопасность (2FA)</Link> },
        { key: 'support', label: <Link to="/support">Поддержка</Link> },
      ],
    },
    ...(isSeller
      ? [{
          key: 'grp-seller', label: 'Кабинет продавца', icon: <ShopOutlined />,
          children: [
            { key: 'seller', label: <Link to="/seller">Обзор</Link> },
            { key: 'seller-products', label: <Link to="/seller/products">Товары</Link> },
            { key: 'seller-orders', label: <Link to="/seller/orders">Заказы</Link> },
            { key: 'seller-analytics', label: <Link to="/seller/analytics">Аналитика продаж</Link> },
            { key: 'seller-reviews', label: <Link to="/seller/reviews">Отзывы на товары</Link> },
            { key: 'seller-returns', label: <Link to="/seller/returns">Возвраты</Link> },
            { key: 'seller-coupons', label: <Link to="/seller/coupons">Мои промокоды</Link> },
            { key: 'seller-import', label: <Link to="/seller/import">Импорт товаров (CSV)</Link> },
            { key: 'seller-inventory', label: <Link to="/seller/inventory">Склад</Link> },
            { key: 'seller-flash-sales', label: <Link to="/seller/flash-sales">Акции и распродажи</Link> },
            { key: 'seller-promo-rules', label: <Link to="/seller/promo-rules">Акции и наборы</Link> },
            { key: 'seller-promotion', label: <Link to="/seller/promotion">Продвижение</Link> },
            { key: 'seller-chat-templates', label: <Link to="/seller/chat-templates">Чат: шаблоны и часы</Link> },
            { key: 'seller-requisites', label: <Link to="/seller/requisites">Налоговые реквизиты</Link> },
            { key: 'seller-staff', label: <Link to="/seller/staff">Сотрудники</Link> },
            { key: 'seller-trust', label: <Link to="/seller/trust">Доверие и статус (KYC/VIP)</Link> },
            { key: 'seller-academy', label: <Link to="/seller/academy">Академия продавца</Link> },
            { key: 'seller-payouts', label: <Link to="/seller/payouts">Вывод средств</Link> },
            { key: 'seller-plan', label: <Link to="/seller/plan">Тариф и комиссия</Link> },
            { key: 'seller-disputes', label: <Link to="/seller/disputes">Споры по заказам</Link> },
          ],
        }]
      : []),
    ...(isStaff
      ? [{
          key: 'grp-staff', label: 'Персоналу', icon: <CustomerServiceOutlined />,
          children: [
            { key: 'dispute-desk', label: <Link to="/dispute-desk">Арбитраж споров</Link> },
            { key: 'support-desk', label: <Link to="/support-desk">Стол поддержки</Link> },
            ...(user?.role === 'moderator' || user?.role === 'superadmin'
              ? [{ key: 'admin', label: <Link to="/admin">Админ-панель</Link> }]
              : []),
          ],
        }]
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
          background: '#fffdf9', padding: 0,
          borderBottom: '1px solid #efe3d2',
          boxShadow: '0 2px 8px rgba(91,58,30,0.06)',
          height: 'auto',
        }}
      >
        <div
          className="page-container"
          style={{ display: 'flex', alignItems: 'center', gap: 16, minHeight: 64, flexWrap: 'wrap' }}
        >
        {/* Logo */}
        <Link to="/" style={{ fontSize: 22, fontWeight: 700, color: '#b45309', whiteSpace: 'nowrap' }}>
          🪵 Маркетплейс
        </Link>

        {/* Search */}
        <Input.Search
          placeholder={t('header.search')}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onSearch={handleSearch}
          style={{ flex: 1, minWidth: 180, maxWidth: 600 }}
          size="large"
        />

        {/* Nav */}
        <Space size={8}>
          <Link to="/catalog">
            <Button type="text">{t('nav.catalog')}</Button>
          </Link>

          <Select
            value={i18n.language?.startsWith('en') ? 'en' : 'ru'}
            onChange={(lng) => i18n.changeLanguage(lng)}
            size="small" style={{ width: 72 }}
            options={[{ value: 'ru', label: '🇷🇺 RU' }, { value: 'en', label: '🇬🇧 EN' }]}
          />

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
              <Link to="/login"><Button>{t('nav.login')}</Button></Link>
              <Link to="/register"><Button type="primary">{t('nav.register')}</Button></Link>
            </>
          )}
        </Space>
        </div>
      </Header>

      <Content className="page-container" style={{ paddingTop: 24, paddingBottom: 40 }}>
        <Outlet />
      </Content>

      <Footer style={{ textAlign: 'center', background: '#fffdf9', borderTop: '1px solid #efe3d2', color: '#a8957f' }}>
        🪵 {t('footer')} · © {new Date().getFullYear()}
      </Footer>
    </Layout>
  )
}
