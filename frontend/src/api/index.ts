import { api } from './client'
import type {
  Token, User, Shop, Category, Product, CartItem, Order,
  Review, ReviewReply, Coupon, Report, Referral, Setting, DashboardStats,
  PaginatedResponse, DeliveryCalculation, ReferralStats, PickupPoint,
  SellerPlan, SellerSubscription, DeliveryService, DeliveryQuote,
  ProductVariant, Attribute, ProductAttributeValue, ProductQuestion,
  Notification, ChatThreadSummary, ChatMessage, SellerCoupon, PayoutRequest,
  HomepageBanner, SellerAnalytics,
  ReturnRequest, SubOrder, ProductSubscription, Currency,
  PlatformAnalytics, CatalogFacet,
  Address, WishlistCollectionBrief, WishlistCollection,
  StockMovement, LowStockItem, FlashSale, SellerRequisites, FiscalReceipt, ShopRatingSummary,
  SupportTicket, SupportMessage, SupportStats, SupportUserView,
  PaidFeature, Promotion, AuctionStanding, AdWallet,
  PromoRule, Bundle, ProductBundle, CartPromoSummary,
  Dispute, DisputeMessage, GiftCertificate, PromoOverview, LoyaltyTier, LoyaltyStatus,
  DigitalAsset, Entitlement, CourseDetail, MyCourse, QuizResult, Certificate,
} from '@/types'

// ─── Auth ─────────────────────────────────────────────────────────────────────
export const authApi = {
  register: (data: {
    email: string; password: string; full_name: string;
    phone?: string; role?: string; referral_code?: string
  }) => api.post<User>('/auth/register', data).then(r => r.data),

  login: (email: string, password: string) =>
    api.post<Token>('/auth/login', { email, password }).then(r => r.data),

  refresh: (refresh_token: string) =>
    api.post<Token>('/auth/refresh', { refresh_token }).then(r => r.data),

  me: () => api.get<User>('/auth/me').then(r => r.data),

  forgotPassword: (email: string) =>
    api.post<{ message: string }>('/auth/forgot-password', { email }).then(r => r.data),

  resetPassword: (token: string, new_password: string) =>
    api.post<{ message: string }>('/auth/reset-password', { token, new_password }).then(r => r.data),

  verifyEmail: (email: string, code: string) =>
    api.post<{ status: string }>('/auth/verify-email', { email, code }).then(r => r.data),

  resendCode: (email: string) =>
    api.post<{ status: string }>('/auth/resend-code', { email }).then(r => r.data),

  sendPhoneCode: () => api.post<{ status: string }>('/auth/send-phone-code').then(r => r.data),
  verifyPhone: (code: string) => api.post<{ status: string }>('/auth/verify-phone', { code }).then(r => r.data),
}

// ─── Users ────────────────────────────────────────────────────────────────────
export const usersApi = {
  updateProfile: (data: { full_name?: string; phone?: string; password?: string }) =>
    api.patch<User>('/users/me', data).then(r => r.data),

  getReferralStats: () => api.get<ReferralStats>('/users/me/referral-stats').then(r => r.data),

  getBalanceHistory: () => api.get('/users/me/balance-history').then(r => r.data),

  // Referral withdrawal (account requisites + payout requests)
  getWithdrawalAccount: () =>
    api.get<{ referral_balance: string; account: { tax_regime: string; legal_name: string; inn: string; account_details: string } | null }>('/users/me/withdrawal-account').then(r => r.data),
  setWithdrawalAccount: (data: { tax_regime: string; legal_name: string; inn: string; account_details: string }) =>
    api.put('/users/me/withdrawal-account', data).then(r => r.data),
  listReferralWithdrawals: () =>
    api.get<Array<{ id: number; amount: string; status: string; created_at: string; admin_comment?: string }>>('/users/me/referral-withdrawals').then(r => r.data),
  requestReferralWithdrawal: (amount: number) =>
    api.post('/users/me/referral-withdrawals', { amount }).then(r => r.data),
}

// ─── Products ─────────────────────────────────────────────────────────────────
export const productsApi = {
  list: (params?: {
    page?: number; page_size?: number; category_id?: number;
    q?: string; min_price?: number; max_price?: number;
    min_rating?: number; sort?: string; attrs?: string
  }) => api.get<PaginatedResponse<Product>>('/products', { params }).then(r => r.data),

  get: (id: number) => api.get<Product>(`/products/${id}`).then(r => r.data),

  importCsv: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post<{ created: number; errors: string[]; total_rows: number }>(
      '/products/import-csv', fd, { headers: { 'Content-Type': 'multipart/form-data' } }
    ).then(r => r.data)
  },

  create: (data: {
    category_id: number; title: string; description?: string;
    price: number; compare_at_price?: number; quantity?: number; weight_g?: number;
    product_type?: 'physical' | 'digital' | 'course'
  }) => api.post<Product>('/products', data).then(r => r.data),

  update: (id: number, data: Partial<{
    category_id: number; title: string; description: string;
    price: number; compare_at_price: number; quantity: number; weight_g: number;
    product_type: 'physical' | 'digital' | 'course'
  }>) => api.put<Product>(`/products/${id}`, data).then(r => r.data),

  delete: (id: number) => api.delete(`/products/${id}`),

  uploadImage: (productId: number, file: File, isMain = false) => {
    const form = new FormData()
    form.append('file', file)
    form.append('is_main', String(isMain))
    return api.post(`/products/${productId}/images`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },

  // Digital files of a digital/course product (seller-managed).
  listDigitalAssets: (productId: number) =>
    api.get<DigitalAsset[]>(`/products/${productId}/digital-assets`).then(r => r.data),
  uploadDigitalAsset: (productId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<DigitalAsset>(`/products/${productId}/digital-assets`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },
  deleteDigitalAsset: (productId: number, assetId: number) =>
    api.delete(`/products/${productId}/digital-assets/${assetId}`),

  myProducts: (params?: { page?: number; page_size?: number; status?: string }) =>
    api.get<PaginatedResponse<Product>>('/products/seller/my', { params }).then(r => r.data),
}

// ─── Digital library (buyer's purchased digital products / courses) ─────────────
export const libraryApi = {
  list: () => api.get<Entitlement[]>('/library').then(r => r.data),
  // Authenticated download endpoint; returns a Blob (Bearer token attached by interceptor).
  download: (productId: number, assetId: number) =>
    api.get(`/library/${productId}/files/${assetId}`, { responseType: 'blob' }),
}

// ─── Courses / LMS ──────────────────────────────────────────────────────────────
export const coursesApi = {
  // Public/buyer course detail + curriculum (gated)
  get: (productId: number) => api.get<CourseDetail>(`/courses/${productId}`).then(r => r.data),
  // Lesson content: text → JSON; video/pdf → Blob (Bearer attached by interceptor)
  lessonContent: (productId: number, lessonId: number) =>
    api.get(`/courses/${productId}/lessons/${lessonId}/content`, { responseType: 'blob' }),
  completeLesson: (productId: number, lessonId: number) =>
    api.post<{ completed: boolean; progress_percent: number }>(`/courses/${productId}/lessons/${lessonId}/complete`).then(r => r.data),
  submitQuiz: (productId: number, lessonId: number, answers: number[]) =>
    api.post<QuizResult>(`/courses/${productId}/lessons/${lessonId}/quiz`, { answers }).then(r => r.data),

  // Full URL of the encrypted-HLS playlist for hls.js (Bearer added via xhrSetup).
  hlsPlaylistUrl: (productId: number, lessonId: number) =>
    `${import.meta.env.VITE_API_URL || ''}/api/v1/courses/${productId}/lessons/${lessonId}/hls/index.m3u8`,

  // Certificates
  issueCertificate: (productId: number, recipient_name: string) =>
    api.post<Certificate>(`/courses/${productId}/certificate`, { recipient_name }).then(r => r.data),
  certificatePdf: (productId: number) =>
    api.get(`/courses/${productId}/certificate/pdf`, { responseType: 'blob' }),
  verifyCertificate: (code: string) =>
    api.get<Certificate>(`/courses/certificates/${code}`).then(r => r.data),

  // Seller course builder
  builder: (productId: number) => api.get<CourseDetail>(`/courses/${productId}/builder`).then(r => r.data),
  updateSettings: (productId: number, data: { level?: string; language?: string; cert_instructor?: string }) =>
    api.put<CourseDetail>(`/courses/${productId}/settings`, data).then(r => r.data),
  uploadCertLogo: (productId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/courses/${productId}/certificate/logo`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },
  addModule: (productId: number, data: { title: string; sort_order?: number }) =>
    api.post(`/courses/${productId}/modules`, data).then(r => r.data),
  updateModule: (productId: number, moduleId: number, data: { title?: string; sort_order?: number }) =>
    api.put(`/courses/${productId}/modules/${moduleId}`, data).then(r => r.data),
  deleteModule: (productId: number, moduleId: number) =>
    api.delete(`/courses/${productId}/modules/${moduleId}`),
  addLesson: (productId: number, moduleId: number, data: { title: string; lesson_type: string; text_body?: string; is_preview?: boolean; sort_order?: number; duration_seconds?: number }) =>
    api.post(`/courses/${productId}/modules/${moduleId}/lessons`, data).then(r => r.data),
  updateLesson: (productId: number, lessonId: number, data: Partial<{ title: string; text_body: string; is_preview: boolean; sort_order: number; duration_seconds: number }>) =>
    api.put(`/courses/${productId}/lessons/${lessonId}`, data).then(r => r.data),
  deleteLesson: (productId: number, lessonId: number) =>
    api.delete(`/courses/${productId}/lessons/${lessonId}`),
  uploadLessonFile: (productId: number, lessonId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/courses/${productId}/lessons/${lessonId}/file`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },
}

export const learningApi = {
  myCourses: () => api.get<MyCourse[]>('/learning').then(r => r.data),
}

// ─── Shops ────────────────────────────────────────────────────────────────────
export const shopsApi = {
  create: (data: { name: string; description?: string; requisites: Partial<SellerRequisites> }) =>
    api.post<Shop>('/shops', data).then(r => r.data),

  // Following
  follow: (shopId: number) =>
    api.post<{ following: boolean; followers: number }>(`/shops/${shopId}/follow`).then(r => r.data),
  unfollow: (shopId: number) =>
    api.delete<{ following: boolean; followers: number }>(`/shops/${shopId}/follow`).then(r => r.data),
  followStatus: (shopId: number) =>
    api.get<{ following: boolean; followers: number }>(`/shops/${shopId}/follow-status`).then(r => r.data),
  following: () => api.get<Shop[]>('/shops/following').then(r => r.data),
  feed: () => api.get<Product[]>('/shops/feed').then(r => r.data),

  getMy: () => api.get<Shop>('/shops/my').then(r => r.data),

  getMyRequisites: () => api.get<SellerRequisites>('/shops/my/requisites').then(r => r.data),
  updateMyRequisites: (data: Partial<SellerRequisites>) =>
    api.put<SellerRequisites>('/shops/my/requisites', data).then(r => r.data),

  updateMy: (data: {
    name?: string; description?: string; logo_url?: string;
    banner_url?: string; accent_color?: string; tagline?: string;
    contact_email?: string; contact_phone?: string
  }) => api.put<Shop>('/shops/my', data).then(r => r.data),

  get: (id: number) => api.get<Shop>(`/shops/${id}`).then(r => r.data),

  // Shop staff (multi-user accounts)
  staffCatalog: () => api.get<any>('/shops/my/staff-catalog').then(r => r.data),
  myAccess: () => api.get<{ paths: string[]; permissions: string[]; is_owner: boolean }>('/shops/my/access').then(r => r.data),
  members: () => api.get<any[]>('/shops/my/members').then(r => r.data),
  addMember: (email: string, role: string, permissions: string[]) =>
    api.post('/shops/my/members', { email, role, permissions }).then(r => r.data),
  updateMember: (userId: number, data: { role?: string; permissions?: string[] }) =>
    api.patch(`/shops/my/members/${userId}`, data).then(r => r.data),
  removeMember: (userId: number) => api.delete(`/shops/my/members/${userId}`),
}

// ─── Cart ─────────────────────────────────────────────────────────────────────
export const cartApi = {
  get: () => api.get<CartItem[]>('/cart').then(r => r.data),

  add: (product_id: number, quantity = 1, variant_id?: number) =>
    api.post<CartItem>('/cart', { product_id, quantity, variant_id }).then(r => r.data),

  update: (item_id: number, quantity: number) =>
    api.patch<CartItem>(`/cart/${item_id}`, { quantity }).then(r => r.data),

  remove: (item_id: number) => api.delete(`/cart/${item_id}`),

  clear: () => api.delete('/cart'),
}

// ─── Orders ───────────────────────────────────────────────────────────────────
export const ordersApi = {
  create: (data: {
    delivery_address: string; city_to: string;
    coupon_code?: string; bonus_to_use?: number; referral_to_use?: number
  }) => api.post<Order>('/orders', data).then(r => r.data),

  list: (params?: { page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Order>>('/orders', { params }).then(r => r.data),

  listForSeller: (params?: { page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Order>>('/orders/seller/my', { params }).then(r => r.data),

  get: (id: number) => api.get<Order>(`/orders/${id}`).then(r => r.data),

  receipts: (id: number) =>
    api.get<FiscalReceipt[]>(`/orders/${id}/receipts`).then(r => r.data),

  updateStatus: (id: number, status: string, tracking_number?: string) =>
    api.patch<Order>(`/orders/${id}/status`, { status, tracking_number }).then(r => r.data),
}

// ─── Categories ───────────────────────────────────────────────────────────────
export const categoriesApi = {
  list: () => api.get<Category[]>('/categories').then(r => r.data),
  get: (slug: string) => api.get<Category>(`/categories/${slug}`).then(r => r.data),
}

// ─── Reviews ──────────────────────────────────────────────────────────────────
export const reviewsApi = {
  list: (product_id: number, params?: { page?: number; verified_only?: boolean }) =>
    api.get<PaginatedResponse<Review>>(`/reviews/product/${product_id}`, { params }).then(r => r.data),

  shopSummary: (shop_id: number) =>
    api.get<ShopRatingSummary>(`/reviews/shop/${shop_id}/summary`).then(r => r.data),

  create: (product_id: number, data: { rating: number; text?: string; photos?: string[] }) =>
    api.post<Review>(`/reviews/product/${product_id}`, data).then(r => r.data),

  myReviews: () => api.get<Review[]>('/reviews/my').then(r => r.data),

  vote: (review_id: number) =>
    api.post<{ voted: boolean; helpful_count: number }>(`/reviews/${review_id}/vote`).then(r => r.data),

  reply: (review_id: number, text: string) =>
    api.post<ReviewReply>(`/reviews/${review_id}/reply`, { text }).then(r => r.data),

  deleteReply: (review_id: number) => api.delete(`/reviews/${review_id}/reply`),
}

// ─── Favorites ────────────────────────────────────────────────────────────────
export const favoritesApi = {
  list: () => api.get<Product[]>('/favorites').then(r => r.data),
  add: (product_id: number) => api.post(`/favorites/${product_id}`),
  remove: (product_id: number) => api.delete(`/favorites/${product_id}`),
}

// ─── Delivery ─────────────────────────────────────────────────────────────────
export const deliveryApi = {
  listServices: () => api.get<DeliveryService[]>('/delivery/services').then(r => r.data),

  calculate: (data: { city_from?: string; city_to: string; weight_g?: number; service?: string }) =>
    api.post<DeliveryCalculation>('/delivery/calculate', data).then(r => r.data),

  quoteAll: (data: { city_from?: string; city_to: string; weight_g?: number }) =>
    api.post<DeliveryQuote[]>('/delivery/quote-all', data).then(r => r.data),

  getPickupPoints: (city: string, service = 'cdek') =>
    api.get<PickupPoint[]>('/delivery/pickup-points', { params: { city, service } }).then(r => r.data),
}

// ─── Seller subscription ───────────────────────────────────────────────────────
export const subscriptionApi = {
  status: () => api.get<{ paid_placement_enabled: boolean }>('/subscription/status').then(r => r.data),
  plans: () => api.get<SellerPlan[]>('/subscription/plans').then(r => r.data),
  me: () => api.get<SellerSubscription | null>('/subscription/me').then(r => r.data),
  subscribe: (plan_id: number, pay_from_balance: boolean) =>
    api.post<any>('/subscription/subscribe', { plan_id, pay_from_balance }).then(r => r.data),
}

// ─── Reports ──────────────────────────────────────────────────────────────────
export const reportsApi = {
  create: (data: { target_type: string; target_id: number; reason: string }) =>
    api.post<Report>('/reports', data).then(r => r.data),
}

// ─── Admin ────────────────────────────────────────────────────────────────────
export const adminApi = {
  dashboard: () => api.get<DashboardStats>('/admin/dashboard').then(r => r.data),

  // Users
  listUsers: (params?: { page?: number; q?: string; role?: string; is_active?: boolean }) =>
    api.get<PaginatedResponse<User>>('/admin/users', { params }).then(r => r.data),
  updateUser: (id: number, data: { is_active?: boolean; role?: string; is_staff?: boolean }) =>
    api.patch<User>(`/admin/users/${id}`, data).then(r => r.data),
  userDetail: (id: number) => api.get<any>(`/admin/users/${id}`).then(r => r.data),

  // Shops
  listShops: (params?: { page?: number; q?: string; is_active?: boolean; status?: string }) =>
    api.get<PaginatedResponse<Shop>>('/admin/shops', { params }).then(r => r.data),
  updateShop: (id: number, data: {
    is_active?: boolean; commission_percent?: number | null;
    name?: string; description?: string; tagline?: string;
    contact_email?: string; contact_phone?: string; accent_color?: string;
  }) => api.patch<Shop>(`/admin/shops/${id}`, data).then(r => r.data),
  moderateShop: (id: number, status: string, moderation_reason?: string) =>
    api.post<Shop>(`/admin/shops/${id}/moderate`, { status, moderation_reason }).then(r => r.data),
  shopRequisites: (id: number) =>
    api.get<any>(`/admin/shops/${id}/requisites`).then(r => r.data),
  shopDetail: (id: number) =>
    api.get<any>(`/admin/shops/${id}/detail`).then(r => r.data),
  // Block D: SMS (SMSC.ru) section
  smsStatus: () => api.get<any>('/admin/sms/status').then(r => r.data),
  smsUpdateSettings: (data: Record<string, any>) =>
    api.put('/admin/sms/settings', data).then(r => r.data),
  smsTest: (phone: string, text?: string) =>
    api.post<any>('/admin/sms/test', { phone, text }).then(r => r.data),
  smsBalance: () => api.get<any>('/admin/sms/balance').then(r => r.data),
  smsStats: (days = 30) => api.get<any>('/admin/sms/stats', { params: { days } }).then(r => r.data),
  smsLog: (params?: { page?: number; status?: string }) =>
    api.get<any>('/admin/sms/log', { params }).then(r => r.data),

  // Products
  listProducts: (params?: { page?: number; status?: string; q?: string }) =>
    api.get<PaginatedResponse<Product>>('/admin/products', { params }).then(r => r.data),
  moderateProduct: (id: number, data: { status: string; moderation_reason?: string }) =>
    api.patch<Product>(`/admin/products/${id}/moderate`, data).then(r => r.data),
  bulkModerate: (product_ids: number[], new_status: string, reason?: string) =>
    api.post('/admin/products/bulk-moderate', product_ids, { params: { new_status, reason } }).then(r => r.data),
  moderationQueue: () =>
    api.get<any[]>('/admin/moderation/queue').then(r => r.data),
  auditLog: (params?: { entity_type?: string; action?: string; page?: number }) =>
    api.get<any>('/admin/audit-log', { params }).then(r => r.data),
  // Block 5: cohort analytics, RBAC, reconciliation, feature flags
  cohorts: (months = 6) => api.get<any>('/admin/analytics/cohorts', { params: { months } }).then(r => r.data),
  ltv: () => api.get<any>('/admin/analytics/ltv').then(r => r.data),
  funnel: (days = 30) => api.get<any>('/admin/analytics/funnel', { params: { days } }).then(r => r.data),
  reconciliation: () => api.get<any>('/admin/analytics/reconciliation').then(r => r.data),
  listFeatureFlags: () => api.get<any[]>('/admin/feature-flags').then(r => r.data),
  upsertFeatureFlag: (data: { key: string; description?: string; is_enabled: boolean; rollout_percent: number }) =>
    api.put('/admin/feature-flags', data).then(r => r.data),
  deleteFeatureFlag: (id: number) => api.delete(`/admin/feature-flags/${id}`),
  permissionsCatalog: () => api.get<any>('/admin/permissions/catalog').then(r => r.data),
  getUserPermissions: (userId: number) => api.get<any>(`/admin/users/${userId}/permissions`).then(r => r.data),
  setUserPermissions: (userId: number, permissions: string[]) =>
    api.put(`/admin/users/${userId}/permissions`, { permissions }).then(r => r.data),
  myMenu: () => api.get<{ paths: string[]; permissions: string[]; is_superadmin: boolean }>('/admin/my-menu').then(r => r.data),
  adjustBalance: (userId: number, field: string, amount: number, reason: string) =>
    api.post<User>(`/admin/users/${userId}/adjust-balance`, { field, amount, reason }).then(r => r.data),

  // Orders
  listOrders: (params?: { page?: number; status?: string }) =>
    api.get<PaginatedResponse<Order>>('/admin/orders', { params }).then(r => r.data),
  updateOrderStatus: (id: number, status: string, tracking_number?: string, delivery_address?: string) =>
    api.patch<Order>(`/admin/orders/${id}/status`, { status, tracking_number, delivery_address }).then(r => r.data),
  refundOrder: (id: number) =>
    api.post(`/admin/orders/${id}/refund`).then(r => r.data),

  // Categories (full tree)
  listCategories: () => api.get<Category[]>('/admin/categories').then(r => r.data),
  createCategory: (data: { name: string; slug?: string; parent_id?: number; image?: string; sort_order?: number; kind?: 'physical' | 'digital' | 'course' | null }) =>
    api.post<Category>('/admin/categories', data).then(r => r.data),
  updateCategory: (id: number, data: Partial<{ name: string; slug: string; parent_id: number | null; sort_order: number; kind: 'physical' | 'digital' | 'course' | null }>) =>
    api.put<Category>(`/admin/categories/${id}`, data).then(r => r.data),
  deleteCategory: (id: number, reassignTo?: number) =>
    api.delete(`/admin/categories/${id}`, { params: reassignTo ? { reassign_to: reassignTo } : undefined }),

  // Reports
  listReports: (params?: { page?: number; status?: string }) =>
    api.get<PaginatedResponse<Report>>('/admin/reports', { params }).then(r => r.data),
  updateReport: (id: number, data: { status: string; resolution?: string; moderator_id?: number }) =>
    api.patch<Report>(`/admin/reports/${id}`, data).then(r => r.data),

  // Reviews
  listReviews: (params?: { page?: number; status?: string }) =>
    api.get<PaginatedResponse<Review>>('/admin/reviews', { params }).then(r => r.data),
  moderateReview: (id: number, data: { status: string; moderation_reason?: string }) =>
    api.patch<Review>(`/admin/reviews/${id}/moderate`, data).then(r => r.data),
  deleteReview: (id: number) => api.delete(`/admin/reviews/${id}`),

  // Seller plans (paid placement)
  listPlans: () => api.get<SellerPlan[]>('/admin/plans').then(r => r.data),
  createPlan: (data: Partial<SellerPlan>) => api.post<SellerPlan>('/admin/plans', data).then(r => r.data),
  updatePlan: (id: number, data: Partial<SellerPlan>) => api.put<SellerPlan>(`/admin/plans/${id}`, data).then(r => r.data),
  deletePlan: (id: number) => api.delete(`/admin/plans/${id}`),

  // Payout requests
  listPayouts: (status?: string) =>
    api.get<PayoutRequest[]>('/admin/payouts', { params: { status } }).then(r => r.data),
  processPayout: (id: number, status: string, admin_comment?: string) =>
    api.post<PayoutRequest>(`/admin/payouts/${id}/process`, { status, admin_comment }).then(r => r.data),

  // Homepage banners
  listBanners: () => api.get<HomepageBanner[]>('/admin/banners').then(r => r.data),
  createBanner: (data: Partial<HomepageBanner>) => api.post<HomepageBanner>('/admin/banners', data).then(r => r.data),
  deleteBanner: (id: number) => api.delete(`/admin/banners/${id}`),

  // Seller analytics
  sellerAnalytics: () => api.get<SellerAnalytics>('/admin/seller-analytics').then(r => r.data),

  // Platform analytics (item 12)
  platformAnalytics: () => api.get<PlatformAnalytics>('/admin/platform-analytics').then(r => r.data),

  // Currency management (item 11)
  listCurrencies: () => api.get<Currency[]>('/admin/currencies').then(r => r.data),
  upsertCurrency: (code: string, rate: number, symbol: string) =>
    api.put('/admin/currencies', { code, rate, symbol }).then(r => r.data),

  // Returns oversight (item 1)
  listReturns: (status?: string) =>
    api.get<ReturnRequest[]>('/admin/returns', { params: { status } }).then(r => r.data),

  // Settings
  getSettings: () => api.get<Setting[]>('/admin/settings').then(r => r.data),
  updateSetting: (key: string, value: string) =>
    api.patch<Setting>(`/admin/settings/${key}`, { value }).then(r => r.data),
  bulkUpdateSettings: (settings: Record<string, string>) =>
    api.patch('/admin/settings', { settings }).then(r => r.data),

  // Fiscalization (54-ФЗ)
  listFiscalReceipts: (params?: { status?: string; type?: string; order_id?: number; page?: number; page_size?: number }) =>
    api.get<{ items: FiscalReceipt[]; total: number; page: number; page_size: number; pages: number; counts: Record<string, number> }>(
      '/admin/fiscal/receipts', { params }
    ).then(r => r.data),
  getFiscalReceipt: (id: number) =>
    api.get<FiscalReceipt>(`/admin/fiscal/receipts/${id}`).then(r => r.data),
  retryFiscalReceipt: (id: number) =>
    api.post<{ status: string }>(`/admin/fiscal/receipts/${id}/retry`).then(r => r.data),

  // Coupons
  listCoupons: () => api.get<Coupon[]>('/admin/coupons').then(r => r.data),
  createCoupon: (data: Partial<Coupon>) => api.post<Coupon>('/admin/coupons', data).then(r => r.data),
  deleteCoupon: (id: number) => api.delete(`/admin/coupons/${id}`),

  // Moderators
  listModerators: () => api.get<User[]>('/admin/moderators').then(r => r.data),
  assignModerator: (user_id: number) =>
    api.post<User>(`/admin/moderators/${user_id}/assign`).then(r => r.data),
  removeModerator: (user_id: number) =>
    api.post<User>(`/admin/moderators/${user_id}/remove`).then(r => r.data),

  // Referrals
  listReferrals: (params?: { page?: number }) =>
    api.get<PaginatedResponse<Referral>>('/admin/referrals', { params }).then(r => r.data),
  manualBonus: (user_id: number, amount: number, is_cash = false) =>
    api.post('/admin/referrals/manual-bonus', null, { params: { user_id, amount, is_cash } }).then(r => r.data),
}

// ─── Block 1: variants, attributes, questions ──────────────────────────────────
export const variantsApi = {
  list: (productId: number) =>
    api.get<ProductVariant[]>(`/products/${productId}/variants`).then(r => r.data),
  create: (productId: number, data: Partial<ProductVariant>) =>
    api.post<ProductVariant>(`/products/${productId}/variants`, data).then(r => r.data),
  update: (variantId: number, data: Partial<ProductVariant>) =>
    api.put<ProductVariant>(`/variants/${variantId}`, data).then(r => r.data),
  remove: (variantId: number) => api.delete(`/variants/${variantId}`),
}

export const attributesApi = {
  list: () => api.get<Attribute[]>('/attributes').then(r => r.data),
  create: (data: Partial<Attribute>) => api.post<Attribute>('/attributes', data).then(r => r.data),
  remove: (id: number) => api.delete(`/attributes/${id}`),
  getForProduct: (productId: number) =>
    api.get<ProductAttributeValue[]>(`/products/${productId}/attributes`).then(r => r.data),
  setForProduct: (productId: number, values: { attribute_id: number; value: string }[]) =>
    api.put<ProductAttributeValue[]>(`/products/${productId}/attributes`, values).then(r => r.data),
}

export const questionsApi = {
  list: (productId: number) =>
    api.get<ProductQuestion[]>(`/products/${productId}/questions`).then(r => r.data),
  ask: (productId: number, question: string) =>
    api.post<ProductQuestion>(`/products/${productId}/questions`, { question }).then(r => r.data),
  answer: (questionId: number, answer: string) =>
    api.post<ProductQuestion>(`/questions/${questionId}/answer`, { answer }).then(r => r.data),
}

export const recommendationsApi = {
  forProduct: (productId: number) =>
    api.get<Product[]>(`/products/${productId}/recommendations`).then(r => r.data),
  forMe: () =>
    api.get<Product[]>('/recommendations/for-me').then(r => r.data),
  forCart: (productIds: number[]) =>
    api.post<Product[]>('/recommendations/cart', { product_ids: productIds }).then(r => r.data),
}

// ─── Block 2: notifications & chat ─────────────────────────────────────────────
export const notificationsApi = {
  list: (unreadOnly = false) =>
    api.get<Notification[]>('/notifications', { params: { unread_only: unreadOnly } }).then(r => r.data),
  unreadCount: () => api.get<{ count: number }>('/notifications/unread-count').then(r => r.data),
  markRead: (id: number) => api.post(`/notifications/${id}/read`),
  markAllRead: () => api.post('/notifications/read-all'),
}

export const chatApi = {
  threads: () => api.get<ChatThreadSummary[]>('/chat/threads').then(r => r.data),
  messages: (threadId: number) =>
    api.get<ChatMessage[]>(`/chat/threads/${threadId}/messages`).then(r => r.data),
  start: (shopId: number, text: string) =>
    api.post('/chat/start', { shop_id: shopId, text }).then(r => r.data),
  send: (threadId: number, text: string) =>
    api.post<ChatMessage>(`/chat/threads/${threadId}/messages`, { text }).then(r => r.data),
}

// ─── Block 3: seller coupons & payouts ─────────────────────────────────────────
export const sellerToolsApi = {
  listCoupons: () => api.get<SellerCoupon[]>('/seller/coupons').then(r => r.data),
  createCoupon: (data: Partial<SellerCoupon>) =>
    api.post<SellerCoupon>('/seller/coupons', data).then(r => r.data),
  deleteCoupon: (id: number) => api.delete(`/seller/coupons/${id}`),
  listPayouts: () => api.get<PayoutRequest[]>('/seller/payouts').then(r => r.data),
  requestPayout: (amount: number, payout_details: string) =>
    api.post<PayoutRequest>('/seller/payouts', { amount, payout_details }).then(r => r.data),
}

// ─── Block 5: homepage banners (public) ────────────────────────────────────────
export const homeApi = {
  banners: () => api.get<HomepageBanner[]>('/home/banners').then(r => r.data),
}

// ─── Items 1,3,7: returns, sub-orders, product subscriptions ───────────────────
export const returnsApi = {
  create: (order_item_id: number, quantity: number, reason: string) =>
    api.post<ReturnRequest>('/returns', { order_item_id, quantity, reason }).then(r => r.data),
  my: () => api.get<ReturnRequest[]>('/returns/my').then(r => r.data),
  seller: () => api.get<ReturnRequest[]>('/returns/seller').then(r => r.data),
  process: (id: number, status: string, resolution_comment?: string, refund_amount?: number) =>
    api.post<ReturnRequest>(`/returns/${id}/process`, { status, resolution_comment, refund_amount }).then(r => r.data),
}

export interface SellerSubOrder {
  id: number
  order_id: number
  status: string
  tracking_number?: string
  delivery_service?: string
  created_at?: string
  net_total: number
  items: { title: string; variant_name?: string; quantity: number; price_at_time: number }[]
}

export interface BuyerSubOrder {
  id: number
  shop_id: number
  shop_name?: string
  status: string
  tracking_number?: string
  delivery_service?: string
  tracking_url?: string
  items: { title: string; variant_name?: string; quantity: number }[]
}

export const subOrdersApi = {
  forOrder: (orderId: number) => api.get<BuyerSubOrder[]>(`/orders/${orderId}/sub-orders`).then(r => r.data),
  mySeller: () => api.get<SellerSubOrder[]>('/seller/sub-orders').then(r => r.data),
  updateStatus: (subOrderId: number, status: string, tracking_number?: string) =>
    api.patch<SubOrder>(`/sub-orders/${subOrderId}/status`, { status, tracking_number }).then(r => r.data),
  createShipment: (subOrderId: number, data: Record<string, any>) =>
    api.post<any>(`/sub-orders/${subOrderId}/shipment`, data).then(r => r.data),
  labelUrl: (subOrderId: number) => `/api/v1/sub-orders/${subOrderId}/label`,
}

export const productSubsApi = {
  subscribe: (product_id: number, kind: string, target_price?: number) =>
    api.post<ProductSubscription>('/product-subscriptions', { product_id, kind, target_price }).then(r => r.data),
  my: () => api.get<ProductSubscription[]>('/product-subscriptions/my').then(r => r.data),
  remove: (id: number) => api.delete(`/product-subscriptions/${id}`),
}

// ─── Item 8: 2FA ───────────────────────────────────────────────────────────────
export const twoFAApi = {
  status: () => api.get<{ enabled: boolean }>('/2fa/status').then(r => r.data),
  setup: () => api.post<{ secret: string; otpauth_url: string; backup_codes: string[] }>('/2fa/setup').then(r => r.data),
  verify: (code: string) => api.post('/2fa/verify', { code }).then(r => r.data),
  disable: (code: string) => api.post('/2fa/disable', { code }).then(r => r.data),
}

// ─── Item 11: currencies ───────────────────────────────────────────────────────
export const currencyApi = {
  list: () => api.get<Currency[]>('/currencies').then(r => r.data),
}

// ─── Item 5: catalog facets ────────────────────────────────────────────────────
export const facetsApi = {
  get: (category_id?: number) =>
    api.get<CatalogFacet[]>('/catalog/facets', { params: { category_id } }).then(r => r.data),
}

// ─── Block 2: addresses, wishlists, recently viewed ────────────────────────────
export const addressApi = {
  list: () => api.get<Address[]>('/addresses').then(r => r.data),
  create: (data: Partial<Address>) => api.post<Address>('/addresses', data).then(r => r.data),
  update: (id: number, data: Partial<Address>) => api.put<Address>(`/addresses/${id}`, data).then(r => r.data),
  remove: (id: number) => api.delete(`/addresses/${id}`),
}

export const wishlistApi = {
  list: () => api.get<WishlistCollectionBrief[]>('/wishlists').then(r => r.data),
  create: (name: string, is_public = false) =>
    api.post<WishlistCollectionBrief>('/wishlists', { name, is_public }).then(r => r.data),
  get: (id: number) => api.get<WishlistCollection>(`/wishlists/${id}`).then(r => r.data),
  remove: (id: number) => api.delete(`/wishlists/${id}`),
  addItem: (collectionId: number, productId: number) =>
    api.post(`/wishlists/${collectionId}/items/${productId}`).then(r => r.data),
  removeItem: (collectionId: number, productId: number) =>
    api.delete(`/wishlists/${collectionId}/items/${productId}`),
}

export const historyApi = {
  recentlyViewed: () => api.get<Product[]>('/recently-viewed').then(r => r.data),
}

// ─── Block 3: seller inventory, flash sales, bulk ops ──────────────────────────
export const inventoryApi = {
  adjustStock: (product_id: number, change: number, note?: string, variant_id?: number) =>
    api.post<StockMovement>('/seller/stock/adjust', { product_id, change, note, variant_id }).then(r => r.data),
  movements: (product_id: number) =>
    api.get<StockMovement[]>('/seller/stock/movements', { params: { product_id } }).then(r => r.data),
  lowStock: (threshold = 5) =>
    api.get<LowStockItem[]>('/seller/stock/low', { params: { threshold } }).then(r => r.data),
  listFlashSales: () => api.get<FlashSale[]>('/seller/flash-sales').then(r => r.data),
  createFlashSale: (data: { product_id: number; discount_percent: number; starts_at: string; ends_at: string }) =>
    api.post<FlashSale>('/seller/flash-sales', data).then(r => r.data),
  deleteFlashSale: (id: number) => api.delete(`/seller/flash-sales/${id}`),
  bulkPrice: (product_ids: number[], opts: { set_price?: number; change_percent?: number }) =>
    api.post('/seller/products/bulk-price', { product_ids, ...opts }).then(r => r.data),
  bulkStatus: (product_ids: number[], is_active: boolean) =>
    api.post('/seller/products/bulk-status', { product_ids, is_active }).then(r => r.data),
  exportCsvUrl: () => '/api/v1/seller/products/export-csv',
}

// ─── Block 6: file upload, chat templates, business hours, search ──────────────
export const uploadApi = {
  upload: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post<{ url: string; filename: string }>('/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },
}

export const chatTemplatesApi = {
  list: () => api.get<{ id: number; title: string; body: string; created_at: string }[]>('/seller/chat-templates').then(r => r.data),
  create: (title: string, body: string) =>
    api.post('/seller/chat-templates', { title, body }).then(r => r.data),
  remove: (id: number) => api.delete(`/seller/chat-templates/${id}`),
}

export const businessHoursApi = {
  update: (business_hours: string) =>
    api.put('/seller/business-hours', { business_hours }).then(r => r.data),
}

export const searchApi = {
  products: (q: string, page = 1, page_size = 20) =>
    api.get<any>('/products/search', { params: { q, page, page_size } }).then(r => r.data),
}

// ─── Support ───────────────────────────────────────────────────────────────
export const supportApi = {
  // user
  myTickets: () => api.get<SupportTicket[]>('/support/tickets').then(r => r.data),
  getTicket: (id: number) => api.get<SupportTicket>(`/support/tickets/${id}`).then(r => r.data),
  createTicket: (data: { subject: string; message: string; category?: string; priority?: string }) =>
    api.post<SupportTicket>('/support/tickets', data).then(r => r.data),
  addMessage: (id: number, text: string) =>
    api.post<SupportMessage>(`/support/tickets/${id}/messages`, { text }).then(r => r.data),
  closeTicket: (id: number) =>
    api.post<SupportTicket>(`/support/tickets/${id}/close`).then(r => r.data),
  // staff
  staffTickets: (params?: { status?: string; assigned?: string; priority?: string; q?: string; overdue?: boolean; page?: number }) =>
    api.get<{ items: SupportTicket[]; total: number; page: number; pages: number }>(
      '/support/staff/tickets', { params }).then(r => r.data),
  staffGetTicket: (id: number) => api.get<SupportTicket>(`/support/staff/tickets/${id}`).then(r => r.data),
  staffReply: (id: number, text: string) =>
    api.post<SupportMessage>(`/support/staff/tickets/${id}/reply`, { text }).then(r => r.data),
  staffUpdate: (id: number, data: { status?: string; priority?: string; assigned_to_id?: number }) =>
    api.patch<SupportTicket>(`/support/staff/tickets/${id}`, data).then(r => r.data),
  staffAssignMe: (id: number) =>
    api.post<SupportTicket>(`/support/staff/tickets/${id}/assign-me`).then(r => r.data),
  staffStats: () => api.get<SupportStats>('/support/staff/stats').then(r => r.data),
  staffSlaSweep: () => api.post<{ overdue: number; escalated: number; auto_assigned: number }>('/support/staff/sla-sweep').then(r => r.data),
  staffUserView: (userId: number) =>
    api.get<SupportUserView>(`/support/staff/users/${userId}`).then(r => r.data),
}

// ─── Promotion / paid features ─────────────────────────────────────────────
export const promotionsApi = {
  // seller
  features: () => api.get<PaidFeature[]>('/seller/promotions/features').then(r => r.data),
  mine: () => api.get<Promotion[]>('/seller/promotions').then(r => r.data),
  standing: (featureKey: string) =>
    api.get<AuctionStanding>(`/seller/promotions/standing/${featureKey}`).then(r => r.data),
  create: (data: { feature_key: string; bid_amount: number; product_id?: number }) =>
    api.post<Promotion>('/seller/promotions', data).then(r => r.data),
  cancel: (id: number) =>
    api.post<Promotion>(`/seller/promotions/${id}/cancel`).then(r => r.data),
  wallet: () => api.get<AdWallet>('/seller/promotions/wallet').then(r => r.data),
  topup: (package_id: string) =>
    api.post<{ ad_balance: string; credited: string }>('/seller/promotions/wallet/topup', { package_id }).then(r => r.data),
  // public
  homepage: () => api.get<{ promotion_id: number; product: Product }[]>('/promotions/homepage').then(r => r.data),
  recordEvent: (promotionId: number, type: 'impression' | 'click') =>
    api.post(`/promotions/${promotionId}/event`, { type }).catch(() => {}),
  // analytics
  analytics: () => api.get<any>('/seller/promotions/analytics').then(r => r.data),
  // admin
  adminFeatures: () => api.get<PaidFeature[]>('/admin/paid-features').then(r => r.data),
  adminUpdateFeature: (id: number, data: Partial<PaidFeature>) =>
    api.patch<PaidFeature>(`/admin/paid-features/${id}`, data).then(r => r.data),
  adminPromotions: (status?: string) =>
    api.get<{ items: Promotion[] }>('/admin/promotions', { params: { status } }).then(r => r.data),
  adminSettle: () => api.post<{ status: string; results: any[] }>('/admin/promotions/settle').then(r => r.data),
}

// ─── Advanced promotions ───────────────────────────────────────────────────
export const promoRulesApi = {
  // seller — rules
  listRules: () => api.get<PromoRule[]>('/seller/promo-rules').then(r => r.data),
  createRule: (data: Partial<PromoRule> & { type: string; title: string }) =>
    api.post<PromoRule>('/seller/promo-rules', data).then(r => r.data),
  updateRule: (id: number, data: Partial<PromoRule>) =>
    api.patch<PromoRule>(`/seller/promo-rules/${id}`, data).then(r => r.data),
  deleteRule: (id: number) => api.delete(`/seller/promo-rules/${id}`),
  // seller — bundles
  listBundles: () => api.get<Bundle[]>('/seller/bundles').then(r => r.data),
  createBundle: (data: { title: string; description?: string; bundle_price: number; items: { product_id: number; quantity: number }[] }) =>
    api.post<Bundle>('/seller/bundles', data).then(r => r.data),
  updateBundle: (id: number, data: any) => api.patch<Bundle>(`/seller/bundles/${id}`, data).then(r => r.data),
  deleteBundle: (id: number) => api.delete(`/seller/bundles/${id}`),
  // public
  productBundles: (productId: number) =>
    api.get<ProductBundle[]>(`/products/${productId}/bundles`).then(r => r.data),
  shopPromos: (shopId: number) => api.get<PromoRule[]>(`/shops/${shopId}/promos`).then(r => r.data),
  cartSummary: () => api.get<CartPromoSummary>('/cart/summary').then(r => r.data),
}

// ─── Disputes ──────────────────────────────────────────────────────────────
export const disputesApi = {
  // buyer
  open: (data: { order_id: number; subject: string; reason: string; order_item_id?: number }) =>
    api.post<Dispute>('/disputes', data).then(r => r.data),
  mine: () => api.get<Dispute[]>('/disputes').then(r => r.data),
  get: (id: number) => api.get<Dispute>(`/disputes/${id}`).then(r => r.data),
  message: (id: number, text: string) =>
    api.post<DisputeMessage>(`/disputes/${id}/messages`, { text }).then(r => r.data),
  escalate: (id: number) => api.post<Dispute>(`/disputes/${id}/escalate`).then(r => r.data),
  cancel: (id: number) => api.post<Dispute>(`/disputes/${id}/cancel`).then(r => r.data),
  concede: (id: number) => api.post<Dispute>(`/disputes/${id}/concede`).then(r => r.data),
  // seller
  sellerList: () => api.get<Dispute[]>('/seller/disputes').then(r => r.data),
  // mediator
  staffQueue: (status?: string) =>
    api.get<Dispute[]>('/disputes/staff/queue', { params: { status } }).then(r => r.data),
  staffStats: () => api.get<{ open: number; in_mediation: number; resolved: number }>('/disputes/staff/stats').then(r => r.data),
  assignMe: (id: number) => api.post<Dispute>(`/disputes/${id}/assign-me`).then(r => r.data),
  resolve: (id: number, data: { resolution: string; refund_amount?: number; note?: string }) =>
    api.post<Dispute>(`/disputes/${id}/resolve`, data).then(r => r.data),
}

// ─── Gift certificates ─────────────────────────────────────────────────────
export const giftsApi = {
  purchase: (data: { amount: number; recipient_email?: string; message?: string }) =>
    api.post<GiftCertificate>('/gift-certificates/purchase', data).then(r => r.data),
  redeem: (code: string) =>
    api.post<{ credited: string; promo_balance: string }>('/gift-certificates/redeem', { code }).then(r => r.data),
  promoBalance: () => api.get<PromoOverview>('/gift-certificates/promo-balance').then(r => r.data),
  adminIssue: (data: { amount: number; count: number; message?: string; expires_at?: string }) =>
    api.post<GiftCertificate[]>('/admin/gift-certificates', data).then(r => r.data),
  adminList: () => api.get<GiftCertificate[]>('/admin/gift-certificates').then(r => r.data),
}

// ─── Loyalty ───────────────────────────────────────────────────────────────
export const loyaltyApi = {
  me: () => api.get<LoyaltyStatus>('/loyalty/me').then(r => r.data),
  tiers: () => api.get<LoyaltyTier[]>('/loyalty/tiers').then(r => r.data),
  adminList: () => api.get<LoyaltyTier[]>('/admin/loyalty-tiers').then(r => r.data),
  adminCreate: (data: Partial<LoyaltyTier>) => api.post<LoyaltyTier>('/admin/loyalty-tiers', data).then(r => r.data),
  adminUpdate: (id: number, data: Partial<LoyaltyTier>) => api.patch<LoyaltyTier>(`/admin/loyalty-tiers/${id}`, data).then(r => r.data),
  adminDelete: (id: number) => api.delete(`/admin/loyalty-tiers/${id}`),
}
