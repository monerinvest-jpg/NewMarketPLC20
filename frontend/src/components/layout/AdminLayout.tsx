import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { Layout, Menu, Button, Avatar, Typography, Space } from 'antd'
import {
  DashboardOutlined, UserOutlined, ShopOutlined, AppstoreOutlined,
  ShoppingOutlined, TagsOutlined, WarningOutlined, SettingOutlined,
  GiftOutlined, TeamOutlined, LinkOutlined, LogoutOutlined, StarOutlined, CreditCardOutlined,
  WalletOutlined, PictureOutlined, AreaChartOutlined, DollarOutlined,
  SafetyCertificateOutlined, FileSearchOutlined, MessageOutlined, FileDoneOutlined, RiseOutlined, GiftOutlined, CrownOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/authStore'

const { Sider, Content, Header } = Layout

const menuItems = [
  { key: '/admin', icon: <DashboardOutlined />, label: <Link to="/admin">Дашборд</Link> },
  { key: '/admin/users', icon: <UserOutlined />, label: <Link to="/admin/users">Пользователи</Link> },
  { key: '/admin/shops', icon: <ShopOutlined />, label: <Link to="/admin/shops">Магазины</Link> },
  { key: '/admin/products', icon: <AppstoreOutlined />, label: <Link to="/admin/products">Товары</Link> },
  { key: '/admin/moderation-queue', icon: <SafetyCertificateOutlined />, label: <Link to="/admin/moderation-queue">Очередь модерации</Link> },
  { key: '/admin/orders', icon: <ShoppingOutlined />, label: <Link to="/admin/orders">Заказы</Link> },
  { key: '/admin/categories', icon: <TagsOutlined />, label: <Link to="/admin/categories">Категории</Link> },
  { key: '/admin/reports', icon: <WarningOutlined />, label: <Link to="/admin/reports">Жалобы</Link> },
  { key: '/admin/reviews', icon: <StarOutlined />, label: <Link to="/admin/reviews">Отзывы</Link> },
  { key: '/admin/coupons', icon: <GiftOutlined />, label: <Link to="/admin/coupons">Купоны</Link> },
  { key: '/admin/plans', icon: <CreditCardOutlined />, label: <Link to="/admin/plans">Тарифы</Link> },
  { key: '/admin/payouts', icon: <WalletOutlined />, label: <Link to="/admin/payouts">Выводы средств</Link> },
  { key: '/admin/banners', icon: <PictureOutlined />, label: <Link to="/admin/banners">Баннеры</Link> },
  { key: '/admin/platform-analytics', icon: <AreaChartOutlined />, label: <Link to="/admin/platform-analytics">Аналитика платформы</Link> },
  { key: '/admin/cohorts', icon: <AreaChartOutlined />, label: <Link to="/admin/cohorts">Когорты и LTV</Link> },
  { key: '/admin/reconciliation', icon: <WalletOutlined />, label: <Link to="/admin/reconciliation">Реконсиляция</Link> },
  { key: '/admin/fiscal-receipts', icon: <FileDoneOutlined />, label: <Link to="/admin/fiscal-receipts">Фискальные чеки</Link> },
  { key: '/admin/paid-features', icon: <RiseOutlined />, label: <Link to="/admin/paid-features">Платные возможности</Link> },
  { key: '/admin/gift-certificates', icon: <GiftOutlined />, label: <Link to="/admin/gift-certificates">Сертификаты</Link> },
  { key: '/admin/loyalty-tiers', icon: <CrownOutlined />, label: <Link to="/admin/loyalty-tiers">Лояльность</Link> },
  { key: '/admin/feature-flags', icon: <SettingOutlined />, label: <Link to="/admin/feature-flags">Feature flags</Link> },
  { key: '/admin/sms', icon: <MessageOutlined />, label: <Link to="/admin/sms">SMS (SMSC.ru)</Link> },
  { key: '/admin/currencies', icon: <DollarOutlined />, label: <Link to="/admin/currencies">Валюты</Link> },
  { key: '/admin/referrals', icon: <LinkOutlined />, label: <Link to="/admin/referrals">Рефералы</Link> },
  { key: '/admin/moderators', icon: <TeamOutlined />, label: <Link to="/admin/moderators">Модераторы</Link> },
  { key: '/admin/audit-log', icon: <FileSearchOutlined />, label: <Link to="/admin/audit-log">Журнал действий</Link> },
  { key: '/admin/settings', icon: <SettingOutlined />, label: <Link to="/admin/settings">Настройки</Link> },
]

export default function AdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const selectedKey = menuItems
    .map((i) => i.key)
    .filter((k) => location.pathname === k || (k !== '/admin' && location.pathname.startsWith(k)))
    .sort((a, b) => b.length - a.length)[0] || '/admin'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={220}
        style={{
          position: 'fixed', left: 0, top: 0, bottom: 0,
          background: '#fff', borderRight: '1px solid #f0f0f0',
          overflow: 'auto', zIndex: 100,
        }}
      >
        <div style={{ padding: '20px 16px', borderBottom: '1px solid #f0f0f0' }}>
          <Link to="/" style={{ fontSize: 18, fontWeight: 700, color: '#f97316' }}>
            🛍️ Marketplace
          </Link>
          <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>Админ-панель</div>
        </div>

        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          style={{ border: 'none', marginTop: 8 }}
        />

        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: 16, borderTop: '1px solid #f0f0f0' }}>
          <Space>
            <Avatar style={{ background: '#f97316' }}>{user?.full_name[0]}</Avatar>
            <div>
              <div style={{ fontSize: 12, fontWeight: 500, lineHeight: 1.2 }}>{user?.full_name}</div>
              <div style={{ fontSize: 11, color: '#999' }}>{user?.role}</div>
            </div>
          </Space>
          <Button
            type="text" danger size="small" icon={<LogoutOutlined />}
            style={{ marginTop: 8, width: '100%' }}
            onClick={() => { logout(); navigate('/') }}
          >
            Выйти
          </Button>
        </div>
      </Sider>

      <Layout style={{ marginLeft: 220 }}>
        <Content style={{ padding: 24, minHeight: '100vh', background: '#f5f5f5' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
