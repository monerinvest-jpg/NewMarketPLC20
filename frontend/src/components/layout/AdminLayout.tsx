import { useEffect, useState } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { Layout, Menu, Button, Avatar, Typography, Space, Grid } from 'antd'
import { adminApi } from '@/api'
import {
  DashboardOutlined, UserOutlined, ShopOutlined, AppstoreOutlined,
  ShoppingOutlined, TagsOutlined, WarningOutlined, SettingOutlined,
  GiftOutlined, TeamOutlined, LinkOutlined, LogoutOutlined, StarOutlined, CreditCardOutlined,
  WalletOutlined, PictureOutlined, AreaChartOutlined, DollarOutlined,
  SafetyCertificateOutlined, FileSearchOutlined, MessageOutlined, FileDoneOutlined,
  RiseOutlined, CrownOutlined, HomeOutlined, ShoppingCartOutlined, NotificationOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/authStore'

const { Sider, Content } = Layout
const { useBreakpoint } = Grid

// Grouped navigation — 27 destinations organised into 6 collapsible sections so
// the sider stays scannable instead of a single endless list.
const groups = [
  {
    key: 'grp-overview', icon: <DashboardOutlined />, label: 'Обзор',
    children: [
      { key: '/admin', icon: <DashboardOutlined />, label: 'Дашборд' },
      { key: '/admin/platform-analytics', icon: <AreaChartOutlined />, label: 'Аналитика платформы' },
      { key: '/admin/cohorts', icon: <RiseOutlined />, label: 'Когорты и LTV' },
      { key: '/admin/reconciliation', icon: <WalletOutlined />, label: 'Реконсиляция' },
      { key: '/admin/metrics', icon: <AreaChartOutlined />, label: 'Метрики (Grafana)' },
    ],
  },
  {
    key: 'grp-users', icon: <TeamOutlined />, label: 'Люди и магазины',
    children: [
      { key: '/admin/users', icon: <UserOutlined />, label: 'Пользователи' },
      { key: '/admin/shops', icon: <ShopOutlined />, label: 'Магазины' },
      { key: '/admin/moderators', icon: <TeamOutlined />, label: 'Модераторы' },
    ],
  },
  {
    key: 'grp-catalog', icon: <AppstoreOutlined />, label: 'Каталог',
    children: [
      { key: '/admin/products', icon: <AppstoreOutlined />, label: 'Товары' },
      { key: '/admin/moderation-queue', icon: <SafetyCertificateOutlined />, label: 'Очередь модерации' },
      { key: '/admin/categories', icon: <TagsOutlined />, label: 'Категории' },
      { key: '/admin/reviews', icon: <StarOutlined />, label: 'Отзывы' },
    ],
  },
  {
    key: 'grp-sales', icon: <ShoppingCartOutlined />, label: 'Продажи и финансы',
    children: [
      { key: '/admin/orders', icon: <ShoppingOutlined />, label: 'Заказы' },
      { key: '/admin/payouts', icon: <WalletOutlined />, label: 'Выводы средств' },
      { key: '/admin/fiscal-receipts', icon: <FileDoneOutlined />, label: 'Фискальные чеки' },
    ],
  },
  {
    key: 'grp-marketing', icon: <NotificationOutlined />, label: 'Маркетинг',
    children: [
      { key: '/admin/coupons', icon: <GiftOutlined />, label: 'Купоны' },
      { key: '/admin/banners', icon: <PictureOutlined />, label: 'Баннеры' },
      { key: '/admin/gift-certificates', icon: <GiftOutlined />, label: 'Сертификаты' },
      { key: '/admin/loyalty-tiers', icon: <CrownOutlined />, label: 'Лояльность' },
      { key: '/admin/referrals', icon: <LinkOutlined />, label: 'Рефералы' },
    ],
  },
  {
    key: 'grp-platform', icon: <SettingOutlined />, label: 'Платформа',
    children: [
      { key: '/admin/plans', icon: <CreditCardOutlined />, label: 'Тарифы' },
      { key: '/admin/paid-features', icon: <RiseOutlined />, label: 'Платные возможности' },
      { key: '/admin/currencies', icon: <DollarOutlined />, label: 'Валюты' },
      { key: '/admin/reports', icon: <WarningOutlined />, label: 'Жалобы' },
      { key: '/admin/feature-flags', icon: <SettingOutlined />, label: 'Feature flags' },
      { key: '/admin/sms', icon: <MessageOutlined />, label: 'SMS (SMSC.ru)' },
      { key: '/admin/audit-log', icon: <FileSearchOutlined />, label: 'Журнал действий' },
      { key: '/admin/settings', icon: <SettingOutlined />, label: 'Настройки' },
    ],
  },
]

const leafKeys = groups.flatMap((g) => g.children.map((c) => c.key))

const menuItems = groups.map((g) => ({
  key: g.key,
  icon: g.icon,
  label: g.label,
  children: g.children.map((c) => ({
    key: c.key,
    icon: c.icon,
    label: <Link to={c.key}>{c.label}</Link>,
  })),
}))

export default function AdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const screens = useBreakpoint()
  const [collapsed, setCollapsed] = useState(false)
  // Allowed sidebar paths from the backend (driven by the user's permissions).
  // null = not loaded yet → show everything to avoid a flash of an empty menu.
  const [allowed, setAllowed] = useState<string[] | null>(null)

  useEffect(() => {
    adminApi.myMenu().then((r) => setAllowed(r.paths)).catch(() => setAllowed(null))
  }, [])

  // Filter groups/children to the permitted paths; drop emptied groups.
  const visibleMenuItems = allowed === null
    ? menuItems
    : menuItems
        .map((g) => ({ ...g, children: g.children.filter((c: any) => allowed.includes(c.key)) }))
        .filter((g) => g.children.length > 0)

  const selectedKey = leafKeys
    .filter((k) => location.pathname === k || (k !== '/admin' && location.pathname.startsWith(k)))
    .sort((a, b) => b.length - a.length)[0] || '/admin'
  const openKey = groups.find((g) => g.children.some((c) => c.key === selectedKey))?.key

  const width = 240
  const collapsedWidth = 72
  const marginLeft = collapsed ? collapsedWidth : width

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={width}
        collapsedWidth={collapsedWidth}
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        breakpoint="lg"
        trigger={null}
        style={{
          position: 'fixed', left: 0, top: 0, bottom: 0,
          background: '#fffdf9', borderRight: '1px solid #efe3d2',
          display: 'flex', flexDirection: 'column', zIndex: 100,
        }}
      >
        <div style={{ padding: collapsed ? '18px 0' : '18px 16px', borderBottom: '1px solid #efe3d2', textAlign: collapsed ? 'center' : 'left' }}>
          <Link to="/" style={{ fontSize: collapsed ? 22 : 18, fontWeight: 700, color: '#b45309' }}>
            {collapsed ? '🪵' : '🪵 Маркетплейс'}
          </Link>
          {!collapsed && <div style={{ fontSize: 12, color: '#a8957f', marginTop: 4 }}>Админ-панель</div>}
        </div>

        {/* Scrollable menu region — flex:1 so the footer never overlaps it */}
        <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            defaultOpenKeys={openKey ? [openKey] : []}
            items={visibleMenuItems}
            style={{ border: 'none', background: 'transparent', marginTop: 8 }}
          />
        </div>

        <div style={{ padding: 12, borderTop: '1px solid #efe3d2' }}>
          {!collapsed && (
            <Space style={{ marginBottom: 8 }}>
              <Avatar style={{ background: '#b45309' }}>{user?.full_name?.[0]}</Avatar>
              <div>
                <div style={{ fontSize: 12, fontWeight: 500, lineHeight: 1.2 }}>{user?.full_name}</div>
                <div style={{ fontSize: 11, color: '#a8957f' }}>{user?.role}</div>
              </div>
            </Space>
          )}
          <Button
            type="text" danger size="small" icon={<LogoutOutlined />}
            style={{ width: '100%' }}
            onClick={() => { logout(); navigate('/') }}
          >
            {!collapsed && 'Выйти'}
          </Button>
        </div>
      </Sider>

      <Layout style={{ marginLeft, transition: 'margin-left 0.2s', background: 'transparent' }}>
        <div style={{ padding: '12px 16px 0', display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button type="text" icon={<HomeOutlined />} onClick={() => setCollapsed((c) => !c)}>
            {screens.lg ? 'Свернуть меню' : 'Меню'}
          </Button>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            {(leafKeys.includes(selectedKey) && groups.find((g) => g.key === openKey)?.label) || 'Админ'}
          </Typography.Text>
        </div>
        <Content style={{ padding: screens.xs ? 14 : 24, minHeight: '100vh' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
