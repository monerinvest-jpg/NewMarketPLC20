import { useEffect, Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider, Spin } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import enUS from 'antd/locale/en_US'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from './store/authStore'
import MainLayout from './components/layout/MainLayout'
import AdminLayout from './components/layout/AdminLayout'
import ProtectedRoute from './components/common/ProtectedRoute'

// Public pages
const HomePage = lazy(() => import('./pages/catalog/HomePage'))
const CatalogPage = lazy(() => import('./pages/catalog/CatalogPage'))
const ProductPage = lazy(() => import('./pages/catalog/ProductPage'))
const ShopPage = lazy(() => import('./pages/catalog/ShopPage'))
const LoginPage = lazy(() => import('./pages/auth/LoginPage'))
const RegisterPage = lazy(() => import('./pages/auth/RegisterPage'))
const ForgotPasswordPage = lazy(() => import('./pages/auth/ForgotPasswordPage'))
const ResetPasswordPage = lazy(() => import('./pages/auth/ResetPasswordPage'))
const VerifyEmailPage = lazy(() => import('./pages/auth/VerifyEmailPage'))
const CartPage = lazy(() => import('./pages/buyer/CartPage'))
const CheckoutPage = lazy(() => import('./pages/buyer/CheckoutPage'))
const OrdersPage = lazy(() => import('./pages/buyer/OrdersPage'))
const OrderDetailPage = lazy(() => import('./pages/buyer/OrderDetailPage'))
const FavoritesPage = lazy(() => import('./pages/buyer/FavoritesPage'))
const ProfilePage = lazy(() => import('./pages/buyer/ProfilePage'))
const ReferralPage = lazy(() => import('./pages/buyer/ReferralPage'))
const MyDownloadsPage = lazy(() => import('./pages/buyer/MyDownloadsPage'))
const LearningPage = lazy(() => import('./pages/buyer/LearningPage'))
const CoursePlayerPage = lazy(() => import('./pages/buyer/CoursePlayerPage'))
const SellerCourseBuilder = lazy(() => import('./pages/seller/SellerCourseBuilder'))
const CertificateVerifyPage = lazy(() => import('./pages/catalog/CertificateVerifyPage'))

// Seller pages
const SellerDashboard = lazy(() => import('./pages/seller/SellerDashboard'))
const SellerProducts = lazy(() => import('./pages/seller/SellerProducts'))
const SellerOrders = lazy(() => import('./pages/seller/SellerOrders'))
const SellerShopSettings = lazy(() => import('./pages/seller/SellerShopSettings'))
const SellerReviews = lazy(() => import('./pages/seller/SellerReviews'))
const SellerPlanPage = lazy(() => import('./pages/seller/SellerPlanPage'))
const SellerCoupons = lazy(() => import('./pages/seller/SellerCoupons'))
const SellerPayouts = lazy(() => import('./pages/seller/SellerPayouts'))
const SellerAnalytics = lazy(() => import('./pages/seller/SellerAnalytics'))
const ChatPage = lazy(() => import('./pages/buyer/ChatPage'))
const ComparePage = lazy(() => import('./pages/catalog/ComparePage'))

// Admin pages
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'))
const AdminUsers = lazy(() => import('./pages/admin/AdminUsers'))
const AdminUserDetail = lazy(() => import('./pages/admin/AdminUserDetail'))
const AdminShops = lazy(() => import('./pages/admin/AdminShops'))
const AdminShopDetail = lazy(() => import('./pages/admin/AdminShopDetail'))
const AdminProducts = lazy(() => import('./pages/admin/AdminProducts'))
const AdminOrders = lazy(() => import('./pages/admin/AdminOrders'))
const AdminCategories = lazy(() => import('./pages/admin/AdminCategories'))
const AdminReports = lazy(() => import('./pages/admin/AdminReports'))
const AdminReviews = lazy(() => import('./pages/admin/AdminReviews'))
const AdminSettings = lazy(() => import('./pages/admin/AdminSettings'))
const AdminCoupons = lazy(() => import('./pages/admin/AdminCoupons'))
const AdminModerators = lazy(() => import('./pages/admin/AdminModerators'))
const AdminReferrals = lazy(() => import('./pages/admin/AdminReferrals'))
const AdminPlans = lazy(() => import('./pages/admin/AdminPlans'))
const AdminPayouts = lazy(() => import('./pages/admin/AdminPayouts'))
const AdminBanners = lazy(() => import('./pages/admin/AdminBanners'))
const AdminPlatformAnalytics = lazy(() => import('./pages/admin/AdminPlatformAnalytics'))
const AdminMetrics = lazy(() => import('./pages/admin/AdminMetrics'))
const AdminModerationQueue = lazy(() => import('./pages/admin/AdminModerationQueue'))
const AdminAuditLog = lazy(() => import('./pages/admin/AdminAuditLog'))
const AdminFiscalReceipts = lazy(() => import('./pages/admin/AdminFiscalReceipts'))
const AdminCohortAnalytics = lazy(() => import('./pages/admin/AdminCohortAnalytics'))
const AdminReconciliation = lazy(() => import('./pages/admin/AdminReconciliation'))
const AdminFeatureFlags = lazy(() => import('./pages/admin/AdminFeatureFlags'))
const AdminSms = lazy(() => import('./pages/admin/AdminSms'))
const AdminCurrencies = lazy(() => import('./pages/admin/AdminCurrencies'))
const ReturnsPage = lazy(() => import('./pages/buyer/ReturnsPage'))
const TwoFactorPage = lazy(() => import('./pages/buyer/TwoFactorPage'))
const SupportPage = lazy(() => import('./pages/buyer/SupportPage'))
const FollowedShopsPage = lazy(() => import('./pages/buyer/FollowedShopsPage'))
const DisputesPage = lazy(() => import('./pages/buyer/DisputesPage'))
const GiftCertificatesPage = lazy(() => import('./pages/buyer/GiftCertificatesPage'))
const LoyaltyPage = lazy(() => import('./pages/buyer/LoyaltyPage'))
const AdminGiftCertificates = lazy(() => import('./pages/admin/AdminGiftCertificates'))
const AdminLoyaltyTiers = lazy(() => import('./pages/admin/AdminLoyaltyTiers'))
const SellerDisputes = lazy(() => import('./pages/seller/SellerDisputes'))
const DisputeDesk = lazy(() => import('./pages/support/DisputeDesk'))
const SupportDesk = lazy(() => import('./pages/support/SupportDesk'))
const SellerPromotion = lazy(() => import('./pages/seller/SellerPromotion'))
const SellerPromoRules = lazy(() => import('./pages/seller/SellerPromoRules'))
const AdminPaidFeatures = lazy(() => import('./pages/admin/AdminPaidFeatures'))
const ProductSubscriptionsPage = lazy(() => import('./pages/buyer/ProductSubscriptionsPage'))
const AddressBookPage = lazy(() => import('./pages/buyer/AddressBookPage'))
const WishlistsPage = lazy(() => import('./pages/buyer/WishlistsPage'))
const SellerReturns = lazy(() => import('./pages/seller/SellerReturns'))
const SellerImport = lazy(() => import('./pages/seller/SellerImport'))
const SellerInventory = lazy(() => import('./pages/seller/SellerInventory'))
const SellerFlashSales = lazy(() => import('./pages/seller/SellerFlashSales'))
const SellerChatTemplates = lazy(() => import('./pages/seller/SellerChatTemplates'))
const SellerRequisitesPage = lazy(() => import('./pages/seller/SellerRequisitesPage'))
const SellerStaff = lazy(() => import('./pages/seller/SellerStaff'))
const SellerTrust = lazy(() => import('./pages/seller/SellerTrust'))
const AdminVerifications = lazy(() => import('./pages/admin/AdminVerifications'))

// Craft / wood theme: warm amber-terracotta accents on parchment, walnut text,
// softer radii. Evokes handmade goods rather than a cold marketplace.
const antdTheme = {
  token: {
    colorPrimary: '#b45309',          // warm amber / terracotta
    colorLink: '#b45309',
    colorInfo: '#b45309',
    colorSuccess: '#4d7c0f',          // moss green
    borderRadius: 10,
    colorBgLayout: '#f7f1e8',         // warm parchment
    colorTextHeading: '#5b3a1e',      // walnut
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  },
  components: {
    Layout: { headerBg: '#fffdf9', bodyBg: '#f7f1e8', footerBg: '#fffdf9' },
    Menu: {
      itemSelectedBg: '#f3e3cf', itemSelectedColor: '#7c4a21',
      itemHoverBg: '#f7eede', itemHoverColor: '#7c4a21',
      subMenuItemBg: 'transparent',
    },
    Card: { borderRadiusLG: 14 },
    Button: { borderRadius: 10, fontWeight: 500 },
  },
}

function App() {
  const { fetchMe, accessToken } = useAuthStore()
  const { i18n } = useTranslation()

  useEffect(() => {
    if (accessToken) {
      fetchMe()
    }
  }, [])

  return (
    <ConfigProvider locale={i18n.language === 'en' ? enUS : ruRU} theme={antdTheme}>
      <BrowserRouter>
        <Suspense fallback={<div className="flex items-center justify-center h-screen"><Spin size="large" /></div>}>
          <Routes>
            {/* Public routes */}
            <Route element={<MainLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/catalog" element={<CatalogPage />} />
              <Route path="/products/:id" element={<ProductPage />} />
              <Route path="/shops/:id" element={<ShopPage />} />
              <Route path="/compare" element={<ComparePage />} />
              <Route path="/verify/:code" element={<CertificateVerifyPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/verify-email" element={<VerifyEmailPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />

              {/* Buyer protected */}
              <Route element={<ProtectedRoute />}>
                <Route path="/cart" element={<CartPage />} />
                <Route path="/checkout" element={<CheckoutPage />} />
                <Route path="/orders" element={<OrdersPage />} />
                <Route path="/orders/:id" element={<OrderDetailPage />} />
                <Route path="/my/downloads" element={<MyDownloadsPage />} />
                <Route path="/learning" element={<LearningPage />} />
                <Route path="/learn/:productId" element={<CoursePlayerPage />} />
                <Route path="/favorites" element={<FavoritesPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/referral" element={<ReferralPage />} />
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/returns" element={<ReturnsPage />} />
                <Route path="/security" element={<TwoFactorPage />} />
                <Route path="/my-subscriptions" element={<ProductSubscriptionsPage />} />
                <Route path="/addresses" element={<AddressBookPage />} />
                <Route path="/wishlists" element={<WishlistsPage />} />
                <Route path="/support" element={<SupportPage />} />
                <Route path="/following" element={<FollowedShopsPage />} />
                <Route path="/disputes" element={<DisputesPage />} />
                <Route path="/gift-certificates" element={<GiftCertificatesPage />} />
                <Route path="/loyalty" element={<LoyaltyPage />} />
                <Route path="/support/:id" element={<SupportPage />} />
              </Route>

              {/* Support staff desk */}
              <Route element={<ProtectedRoute roles={['support', 'moderator', 'superadmin']} />}>
                <Route path="/support-desk" element={<SupportDesk />} />
                <Route path="/dispute-desk" element={<DisputeDesk />} />
              </Route>

              {/* Seller protected */}
              <Route element={<ProtectedRoute roles={['seller', 'superadmin']} />}>
                <Route path="/seller" element={<SellerDashboard />} />
                <Route path="/seller/products" element={<SellerProducts />} />
                <Route path="/seller/courses/:productId" element={<SellerCourseBuilder />} />
                <Route path="/seller/orders" element={<SellerOrders />} />
                <Route path="/seller/shop" element={<SellerShopSettings />} />
                <Route path="/seller/reviews" element={<SellerReviews />} />
                <Route path="/seller/plan" element={<SellerPlanPage />} />
                <Route path="/seller/promotion" element={<SellerPromotion />} />
                <Route path="/seller/promo-rules" element={<SellerPromoRules />} />
                <Route path="/seller/disputes" element={<SellerDisputes />} />
                <Route path="/seller/coupons" element={<SellerCoupons />} />
                <Route path="/seller/payouts" element={<SellerPayouts />} />
                <Route path="/seller/analytics" element={<SellerAnalytics />} />
                <Route path="/seller/returns" element={<SellerReturns />} />
                <Route path="/seller/import" element={<SellerImport />} />
                <Route path="/seller/inventory" element={<SellerInventory />} />
                <Route path="/seller/flash-sales" element={<SellerFlashSales />} />
                <Route path="/seller/chat-templates" element={<SellerChatTemplates />} />
                <Route path="/seller/requisites" element={<SellerRequisitesPage />} />
                <Route path="/seller/staff" element={<SellerStaff />} />
                <Route path="/seller/trust" element={<SellerTrust />} />
              </Route>
            </Route>

            {/* Admin routes */}
            <Route
              path="/admin"
              element={
                <ProtectedRoute roles={['moderator', 'superadmin']}>
                  <AdminLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<AdminDashboard />} />
              <Route path="users" element={<AdminUsers />} />
              <Route path="users/:id" element={<AdminUserDetail />} />
              <Route path="shops" element={<AdminShops />} />
              <Route path="shops/:id" element={<AdminShopDetail />} />
              <Route path="verifications" element={<AdminVerifications />} />
              <Route path="products" element={<AdminProducts />} />
              <Route path="orders" element={<AdminOrders />} />
              <Route path="categories" element={<AdminCategories />} />
              <Route path="reports" element={<AdminReports />} />
              <Route path="reviews" element={<AdminReviews />} />
              <Route path="settings" element={<AdminSettings />} />
              <Route path="coupons" element={<AdminCoupons />} />
              <Route path="moderators" element={<AdminModerators />} />
              <Route path="referrals" element={<AdminReferrals />} />
              <Route path="plans" element={<AdminPlans />} />
              <Route path="payouts" element={<AdminPayouts />} />
              <Route path="banners" element={<AdminBanners />} />
              <Route path="platform-analytics" element={<AdminPlatformAnalytics />} />
              <Route path="metrics" element={<AdminMetrics />} />
              <Route path="moderation-queue" element={<AdminModerationQueue />} />
              <Route path="audit-log" element={<AdminAuditLog />} />
              <Route path="fiscal-receipts" element={<AdminFiscalReceipts />} />
              <Route path="paid-features" element={<AdminPaidFeatures />} />
              <Route path="gift-certificates" element={<AdminGiftCertificates />} />
              <Route path="loyalty-tiers" element={<AdminLoyaltyTiers />} />
              <Route path="cohorts" element={<AdminCohortAnalytics />} />
              <Route path="reconciliation" element={<AdminReconciliation />} />
              <Route path="feature-flags" element={<AdminFeatureFlags />} />
              <Route path="sms" element={<AdminSms />} />
              <Route path="currencies" element={<AdminCurrencies />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ConfigProvider>
  )
}

export default App
