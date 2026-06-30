import { lazy } from 'react'
import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { Result, Button, Space } from 'antd'
import { useAuthStore } from '@/store/authStore'
import SellerLayout from '@/components/layout/SellerLayout'
import SellerLoginPage from './SellerLoginPage'
import { mainOrigin } from '@/lib/sellerHost'

// Seller cabinet pages — same components as before, now mounted at root-level
// paths on the seller host (seller.<domain>/products, /orders, ...).
const SellerDashboard = lazy(() => import('@/pages/seller/SellerDashboard'))
const SellerProducts = lazy(() => import('@/pages/seller/SellerProducts'))
const SellerCourseBuilder = lazy(() => import('@/pages/seller/SellerCourseBuilder'))
const SellerOrders = lazy(() => import('@/pages/seller/SellerOrders'))
const SellerShopSettings = lazy(() => import('@/pages/seller/SellerShopSettings'))
const SellerReviews = lazy(() => import('@/pages/seller/SellerReviews'))
const SellerPlanPage = lazy(() => import('@/pages/seller/SellerPlanPage'))
const SellerPromotion = lazy(() => import('@/pages/seller/SellerPromotion'))
const SellerPromoRules = lazy(() => import('@/pages/seller/SellerPromoRules'))
const SellerDisputes = lazy(() => import('@/pages/seller/SellerDisputes'))
const SellerCoupons = lazy(() => import('@/pages/seller/SellerCoupons'))
const SellerPayouts = lazy(() => import('@/pages/seller/SellerPayouts'))
const SellerAnalytics = lazy(() => import('@/pages/seller/SellerAnalytics'))
const SellerReturns = lazy(() => import('@/pages/seller/SellerReturns'))
const SellerImport = lazy(() => import('@/pages/seller/SellerImport'))
const SellerInventory = lazy(() => import('@/pages/seller/SellerInventory'))
const SellerFlashSales = lazy(() => import('@/pages/seller/SellerFlashSales'))
const SellerChatTemplates = lazy(() => import('@/pages/seller/SellerChatTemplates'))
const SellerRequisitesPage = lazy(() => import('@/pages/seller/SellerRequisitesPage'))
const SellerStaff = lazy(() => import('@/pages/seller/SellerStaff'))
const SellerTrust = lazy(() => import('@/pages/seller/SellerTrust'))
const SellerAcademy = lazy(() => import('@/pages/seller/SellerAcademy'))
const SellerCustomRequests = lazy(() => import('@/pages/seller/SellerCustomRequests'))

const SELLER_ROLES = ['seller', 'superadmin']

// Guard for the seller host: unauthenticated -> seller login; authenticated
// but not a seller -> an access-denied screen (NOT a redirect to "/", which
// would loop because "/" is itself guarded).
function SellerGuard() {
  const user = useAuthStore((s) => s.user)
  const accessToken = useAuthStore((s) => s.accessToken)
  const logout = useAuthStore((s) => s.logout)

  if (!accessToken || !user) {
    return <Navigate to="/login" replace />
  }

  if (!SELLER_ROLES.includes(user.role)) {
    return (
      <Result
        status="403"
        title="Доступ только для продавцов"
        subTitle="Этот раздел доступен только продавцам маркетплейса."
        extra={
          <Space>
            <Button type="primary" href={mainOrigin() + '/'}>На витрину</Button>
            <Button onClick={logout}>Сменить аккаунт</Button>
          </Space>
        }
      />
    )
  }

  return <Outlet />
}

export default function SellerApp() {
  return (
    <Routes>
      <Route path="/login" element={<SellerLoginPage />} />
      <Route element={<SellerGuard />}>
        <Route element={<SellerLayout />}>
          <Route path="/" element={<SellerDashboard />} />
          <Route path="/products" element={<SellerProducts />} />
          <Route path="/courses/:productId" element={<SellerCourseBuilder />} />
          <Route path="/orders" element={<SellerOrders />} />
          <Route path="/custom-requests" element={<SellerCustomRequests />} />
          <Route path="/analytics" element={<SellerAnalytics />} />
          <Route path="/reviews" element={<SellerReviews />} />
          <Route path="/returns" element={<SellerReturns />} />
          <Route path="/inventory" element={<SellerInventory />} />
          <Route path="/import" element={<SellerImport />} />
          <Route path="/coupons" element={<SellerCoupons />} />
          <Route path="/flash-sales" element={<SellerFlashSales />} />
          <Route path="/promo-rules" element={<SellerPromoRules />} />
          <Route path="/promotion" element={<SellerPromotion />} />
          <Route path="/payouts" element={<SellerPayouts />} />
          <Route path="/plan" element={<SellerPlanPage />} />
          <Route path="/requisites" element={<SellerRequisitesPage />} />
          <Route path="/shop" element={<SellerShopSettings />} />
          <Route path="/staff" element={<SellerStaff />} />
          <Route path="/trust" element={<SellerTrust />} />
          <Route path="/chat-templates" element={<SellerChatTemplates />} />
          <Route path="/disputes" element={<SellerDisputes />} />
          <Route path="/academy" element={<SellerAcademy />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
