import { useState } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { Layout, Menu, Button, Avatar, Typography, Space, Grid } from 'antd'
import {
  DashboardOutlined, AppstoreOutlined, ShoppingOutlined, StarOutlined,
  DatabaseOutlined, ImportOutlined, RollbackOutlined, WarningOutlined,
  GiftOutlined, ThunderboltOutlined, TagsOutlined, RiseOutlined,
  WalletOutlined, CreditCardOutlined, FileDoneOutlined, ShopOutlined,
  TeamOutlined, SafetyCertificateOutlined, MessageOutlined, ReadOutlined,
  AreaChartOutlined, LogoutOutlined, HomeOutlined, BuildOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/authStore'
import { mainOrigin } from '@/lib/sellerHost'

const { Sider, Content } = Layout
const { useBreakpoint } = Grid

// Grouped navigation mirroring the admin sider, but with seller destinations.
// Paths are root-level because the cabinet lives on its own host (seller.<domain>).
const groups = [
  {
    key: 'grp-overview', icon: <DashboardOutlined />, label: 'Обзор',
    children: [
      { key: '/', icon: <DashboardOutlined />, label: 'Дашборд' },
      { key: '/analytics', icon: <AreaChartOutlined />, label: 'Аналитика продаж' },
    ],
  },
  {
    key: 'grp-catalog', icon: <AppstoreOutlined />, label: 'Товары',
    children: [
      { key: '/products', icon: <AppstoreOutlined />, label: 'Мои товары' },
      { key: '/inventory', icon: <DatabaseOutlined />, label: 'Склад' },
      { key: '/import', icon: <ImportOutlined />, label: 'Импорт (CSV)' },
      { key: '/reviews', icon: <StarOutlined />, label: 'Отзывы на товары' },
    ],
  },
  {
    key: 'grp-sales', icon: <ShoppingOutlined />, label: 'Продажи',
    children: [
      { key: '/orders', icon: <ShoppingOutlined />, label: 'Заказы' },
      { key: '/custom-requests', icon: <BuildOutlined />, label: 'Запросы на изготовление' },
      { key: '/returns', icon: <RollbackOutlined />, label: 'Возвраты' },
      { key: '/disputes', icon: <WarningOutlined />, label: 'Споры по заказам' },
    ],
  },
  {
    key: 'grp-marketing', icon: <RiseOutlined />, label: 'Маркетинг',
    children: [
      { key: '/coupons', icon: <GiftOutlined />, label: 'Мои промокоды' },
      { key: '/flash-sales', icon: <ThunderboltOutlined />, label: 'Акции и распродажи' },
      { key: '/promo-rules', icon: <TagsOutlined />, label: 'Акции и наборы' },
      { key: '/promotion', icon: <RiseOutlined />, label: 'Продвижение' },
    ],
  },
  {
    key: 'grp-finance', icon: <WalletOutlined />, label: 'Финансы',
    children: [
      { key: '/payouts', icon: <WalletOutlined />, label: 'Вывод средств' },
      { key: '/plan', icon: <CreditCardOutlined />, label: 'Тариф и комиссия' },
      { key: '/requisites', icon: <FileDoneOutlined />, label: 'Налоговые реквизиты' },
    ],
  },
  {
    key: 'grp-shop', icon: <ShopOutlined />, label: 'Магазин',
    children: [
      { key: '/shop', icon: <ShopOutlined />, label: 'Настройки магазина' },
      { key: '/staff', icon: <TeamOutlined />, label: 'Сотрудники' },
      { key: '/trust', icon: <SafetyCertificateOutlined />, label: 'Доверие и статус (KYC/VIP)' },
      { key: '/chat-templates', icon: <MessageOutlined />, label: 'Чат: шаблоны и часы' },
      { key: '/academy', icon: <ReadOutlined />, label: 'Академия продавца' },
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

export default function SellerLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const screens = useBreakpoint()
  const [collapsed, setCollapsed] = useState(false)

  // Longest matching leaf wins; '/' only matches exactly (else it would always win).
  const selectedKey = leafKeys
    .filter((k) => location.pathname === k || (k !== '/' && location.pathname.startsWith(k)))
    .sort((a, b) => b.length - a.length)[0] || '/'
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
          {!collapsed && <div style={{ fontSize: 12, color: '#a8957f', marginTop: 4 }}>Кабинет продавца</div>}
        </div>

        {/* Scrollable menu region — flex:1 so the footer never overlaps it */}
        <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            defaultOpenKeys={openKey ? [openKey] : []}
            items={menuItems}
            style={{ border: 'none', background: 'transparent', marginTop: 8 }}
          />
        </div>

        <div style={{ padding: 12, borderTop: '1px solid #efe3d2' }}>
          {!collapsed && (
            <Space style={{ marginBottom: 8 }}>
              <Avatar style={{ background: '#b45309' }}>{user?.full_name?.[0]}</Avatar>
              <div>
                <div style={{ fontSize: 12, fontWeight: 500, lineHeight: 1.2 }}>{user?.full_name}</div>
                <div style={{ fontSize: 11, color: '#a8957f' }}>Продавец</div>
              </div>
            </Space>
          )}
          {/* Cross-origin link back to the storefront */}
          <Button
            type="text" size="small" icon={<HomeOutlined />}
            style={{ width: '100%', marginBottom: 4 }}
            href={mainOrigin() + '/'}
          >
            {!collapsed && 'На витрину'}
          </Button>
          <Button
            type="text" danger size="small" icon={<LogoutOutlined />}
            style={{ width: '100%' }}
            onClick={() => { logout(); navigate('/login') }}
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
            {(leafKeys.includes(selectedKey) && groups.find((g) => g.key === openKey)?.label) || 'Кабинет продавца'}
          </Typography.Text>
        </div>
        <Content style={{ padding: screens.xs ? 14 : 24, minHeight: '100vh' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
