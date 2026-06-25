// ─── Enums ────────────────────────────────────────────────────────────────────
export type UserRole = 'buyer' | 'seller' | 'support' | 'moderator' | 'superadmin'
export type ProductStatus = 'pending' | 'active' | 'rejected' | 'blocked'
export type OrderStatus =
  | 'pending_payment'
  | 'paid'
  | 'processing'
  | 'shipped'
  | 'delivered'
  | 'completed'
  | 'cancelled'
  | 'refunded'
export type PaymentStatus = 'pending' | 'succeeded' | 'cancelled' | 'refunded'
export type ReferralType = 'buyer' | 'seller'
export type ReportStatus = 'open' | 'in_review' | 'resolved' | 'dismissed'
export type DiscountType = 'percent' | 'fixed'
export type ReviewStatus = 'pending' | 'approved' | 'rejected'

// ─── Entities ─────────────────────────────────────────────────────────────────
export interface User {
  id: number
  email: string
  full_name: string
  phone?: string
  role: UserRole
  referral_code?: string
  balance: string
  bonus_balance: string
  is_active: boolean
  is_staff: boolean
  is_superuser: boolean
  email_verified?: boolean
  phone_verified?: boolean
  created_at: string
}

export interface Shop {
  id: number
  owner_id: number
  name: string
  description?: string
  logo_url?: string
  banner_url?: string
  accent_color: string
  tagline?: string
  contact_email?: string
  contact_phone?: string
  commission_percent?: string
  is_active: boolean
  status?: string
  moderation_reason?: string
  business_hours?: string
  rating: string
  reviews_count?: number
  total_sales: number
  created_at: string
}

export interface SellerPlan {
  id: number
  name: string
  description?: string
  monthly_price: string
  commission_percent: string
  trial_days: number
  is_active: boolean
  is_default: boolean
  sort_order: number
}

export interface SellerSubscription {
  id: number
  shop_id: number
  plan_id: number
  status: 'active' | 'trial' | 'expired' | 'cancelled'
  current_period_end?: string
  trial_used: boolean
  auto_renew: boolean
  plan: SellerPlan
}

export interface DeliveryService {
  code: string
  name: string
}

export interface DeliveryQuote {
  code: string
  name: string
  cost: string
  estimated_days: number
}

export interface Category {
  id: number
  parent_id?: number
  name: string
  slug: string
  image?: string
  sort_order: number
  children: Category[]
}

export interface ProductImage {
  id: number
  url: string
  is_main: boolean
  sort_order: number
}

export interface Product {
  id: number
  shop_id: number
  category_id: number
  title: string
  description?: string
  price: string
  compare_at_price?: string
  quantity: number
  weight_g: number
  status: ProductStatus
  moderation_reason?: string
  rating: string
  reviews_count: number
  views_count: number
  images: ProductImage[]
  created_at: string
  slug?: string
  flash_price?: string
  flash_discount_percent?: string
  flash_ends_at?: string
}

export interface CartItem {
  id: number
  product_id: number
  quantity: number
  product: Product
}

export interface OrderItem {
  id: number
  product_id: number
  variant_id?: number
  variant_name?: string
  shop_id: number
  quantity: number
  price_at_time: string
  commission_percent_used: string
  platform_fee: string
  seller_net: string
  payout_status: string
  product: Product
}

export interface DeliveryInfo {
  id: number
  delivery_service: string
  tracking_number?: string
  cost: string
  estimated_days: number
  city_from: string
  city_to: string
  address: string
  shipped_at?: string
  delivered_at?: string
}

export interface Payment {
  id: number
  order_id: number
  gateway: string
  gateway_payment_id?: string
  amount: string
  status: PaymentStatus
  confirmation_url?: string
  paid_at?: string
}

export interface Order {
  id: number
  buyer_id: number
  total_price: string
  subtotal: string
  delivery_cost: string
  platform_fee: string
  seller_net: string
  commission_percent_used: string
  bonus_used: string
  coupon_discount: string
  status: OrderStatus
  delivery_address: string
  items: OrderItem[]
  payment?: Payment
  delivery_info?: DeliveryInfo
  created_at: string
  updated_at: string
}

export interface ReviewReply {
  id: number
  review_id: number
  seller_id: number
  text: string
  created_at: string
  updated_at: string
}

export interface Review {
  id: number
  user_id: number
  product_id: number
  rating: number
  text?: string
  status: ReviewStatus
  moderation_reason?: string
  helpful_count: number
  is_verified_purchase?: boolean
  created_at: string
  user: User
  reply?: ReviewReply
  voted_by_me: boolean
  photos?: ReviewPhoto[]
}

export interface ShopRatingSummary {
  shop_id: number
  rating: number
  reviews_count: number
  verified_count: number
  distribution: Record<string, number>
}

export interface Coupon {
  id: number
  code: string
  discount_type: DiscountType
  discount_value: string
  valid_from: string
  valid_until: string
  max_uses: number
  used_count: number
  min_order_amount: string
  is_active: boolean
}

export interface Report {
  id: number
  reporter_id: number
  target_type: string
  target_id: number
  reason: string
  status: ReportStatus
  moderator_id?: number
  resolution?: string
  created_at: string
}

export interface Referral {
  id: number
  referrer_id: number
  referred_user_id: number
  type: ReferralType
  code: string
  reward_paid: boolean
  created_at: string
}

export interface Setting {
  key: string
  value: string
  description?: string
  updated_at: string
}

export interface DashboardStats {
  total_orders: number
  orders_today: number
  total_revenue: string
  revenue_today: string
  total_users: number
  new_users_today: number
  total_products: number
  pending_moderation: number
  open_reports: number
}

// ─── API Response wrappers ────────────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface DeliveryCalculation {
  cost: string
  estimated_days: number
  service: string
}

export interface PickupPoint {
  code: string
  name: string
  address: string
  city: string
  latitude?: number
  longitude?: number
  work_time?: string
}

export interface ReferralStats {
  referral_code: string
  referral_link: string
  total_referred: number
  paid_rewards: number
  bonus_balance: string
  balance: string
}

export interface Token {
  access_token: string
  refresh_token: string
  token_type: string
}

// ─── Block 1: variants, attributes, questions, review photos ───────────────────
export interface ProductVariant {
  id: number
  product_id: number
  sku?: string
  name: string
  price?: string
  quantity: number
  is_active: boolean
  sort_order: number
}

export interface Attribute {
  id: number
  name: string
  slug: string
  is_filterable: boolean
  sort_order: number
}

export interface ProductAttributeValue {
  id: number
  attribute_id: number
  value: string
  attribute: Attribute
}

export interface ProductQuestion {
  id: number
  product_id: number
  user_id: number
  question: string
  answer?: string
  answered_at?: string
  created_at: string
  user: User
}

export interface ReviewPhoto {
  id: number
  url: string
  sort_order: number
}

// ─── Block 2: notifications & chat ─────────────────────────────────────────────
export interface Notification {
  id: number
  type: string
  title: string
  body?: string
  link?: string
  is_read: boolean
  created_at: string
}

export interface ChatThreadSummary {
  id: number
  shop_id: number
  buyer_id: number
  other_name: string
  is_seller_view: boolean
  last_message?: string
  updated_at: string
  unread: number
}

export interface ChatMessage {
  id: number
  thread_id: number
  sender_id: number
  text: string
  is_read: boolean
  created_at: string
}

// ─── Block 3: seller coupons & payouts ─────────────────────────────────────────
export interface SellerCoupon {
  id: number
  shop_id: number
  code: string
  discount_type: 'percent' | 'fixed'
  discount_value: string
  min_order_amount: string
  usage_limit?: number
  used_count: number
  is_active: boolean
  expires_at?: string
}

export interface PayoutRequest {
  id: number
  user_id: number
  amount: string
  status: string
  payout_details: string
  admin_comment?: string
  processed_at?: string
  created_at: string
}

// ─── Block 5: homepage banners ─────────────────────────────────────────────────
export interface HomepageBanner {
  id: number
  title: string
  subtitle?: string
  image_url: string
  link?: string
  is_active: boolean
  sort_order: number
}

// ─── Seller analytics ──────────────────────────────────────────────────────────
export interface SellerAnalytics {
  items_sold: number
  total_earned: number
  current_balance: number
  revenue_by_day: { day: string; revenue: number }[]
  top_products: { title: string; qty: number; revenue: number }[]
}

// ─── Items 1-3: returns & sub-orders ───────────────────────────────────────────
export interface ReturnRequest {
  id: number
  order_item_id: number
  buyer_id: number
  shop_id: number
  quantity: number
  reason: string
  status: 'requested' | 'approved' | 'rejected' | 'in_transit' | 'refunded'
  refund_amount: string
  resolution_comment?: string
  processed_at?: string
  created_at: string
}

export interface SubOrder {
  id: number
  order_id: number
  shop_id: number
  status: 'processing' | 'shipped' | 'delivered' | 'completed' | 'cancelled'
  tracking_number?: string
  delivery_service?: string
}

// ─── Item 7: product subscriptions ─────────────────────────────────────────────
export interface ProductSubscription {
  id: number
  product_id: number
  kind: 'back_in_stock' | 'price_drop'
  target_price?: string
  is_notified: boolean
  created_at: string
}

// ─── Item 11: currencies ───────────────────────────────────────────────────────
export interface Currency {
  code: string
  rate: string
  symbol: string
}

// ─── Item 12: platform analytics ───────────────────────────────────────────────
export interface PlatformAnalytics {
  gmv: number
  platform_revenue: number
  trend: { day: string; orders: number; revenue: number }[]
  top_shops: { name: string; net: number; items: number }[]
  user_growth: { day: string; count: number }[]
}

// ─── Item 5: catalog facets ────────────────────────────────────────────────────
export interface CatalogFacet {
  id: number
  name: string
  slug: string
  values: string[]
}

// ─── Block 2: addresses, wishlists, browsing history ───────────────────────────
export interface Address {
  id: number
  label: string
  full_name: string
  phone: string
  city: string
  street: string
  building?: string
  apartment?: string
  postal_code?: string
  is_default: boolean
  created_at: string
}

export interface WishlistCollectionBrief {
  id: number
  name: string
  is_public: boolean
  created_at: string
  item_count: number
}

export interface WishlistItem {
  id: number
  product_id: number
  added_at: string
  product: Product
}

export interface WishlistCollection {
  id: number
  name: string
  is_public: boolean
  created_at: string
  items: WishlistItem[]
}

// ─── Block 3: stock, flash sales ───────────────────────────────────────────────
export interface StockMovement {
  id: number
  product_id: number
  variant_id?: number
  change: number
  reason: string
  quantity_after: number
  note?: string
  created_at: string
}

export interface LowStockItem {
  product_id: number
  title: string
  quantity: number
  threshold: number
}

export interface FlashSale {
  id: number
  product_id: number
  shop_id: number
  discount_percent: string
  starts_at: string
  ends_at: string
  is_active: boolean
  created_at: string
  product_title?: string
  base_price?: string
  effective_price?: string
  is_running?: boolean
}

// ─── Block B: seller tax regime & requisites ──────────────────────────────────
export type TaxRegime = 'self_employed' | 'individual' | 'company'

export interface SellerRequisites {
  id: number
  shop_id: number
  tax_regime: TaxRegime
  legal_name: string
  inn: string
  ogrn?: string
  kpp?: string
  legal_address?: string
  bank_account?: string
  bank_name?: string
  bik?: string
  corr_account?: string
  vat_code?: number | null
  tax_system_code?: number | null
  created_at: string
}

export type FiscalReceiptType = 'income' | 'income_refund'
export type FiscalReceiptStatus = 'pending' | 'succeeded' | 'canceled' | 'failed'

export interface FiscalReceiptItem {
  description: string
  quantity: string
  amount: { value: string; currency: string }
  vat_code: number
  payment_subject?: string
  payment_mode?: string
}

export interface FiscalReceipt {
  id: number
  order_id: number
  payment_id?: number | null
  type: FiscalReceiptType
  status: FiscalReceiptStatus
  customer_contact: string
  total: string
  tax_system_code?: number | null
  items: FiscalReceiptItem[]
  fiscal_document_number?: string | null
  fiscal_storage_number?: string | null
  fiscal_attribute?: string | null
  registered_at?: string | null
  error?: string | null
  created_at: string
}

// ─── Support (tickets & chat) ──────────────────────────────────────────────
export type SupportTicketStatus = 'open' | 'in_progress' | 'pending_user' | 'resolved' | 'closed'
export type SupportTicketPriority = 'low' | 'normal' | 'high' | 'urgent'

export interface SupportMessage {
  id: number
  ticket_id: number
  sender_id: number
  is_staff: boolean
  text: string
  attachment_url?: string | null
  created_at: string
}

export interface SupportTicket {
  id: number
  user_id: number
  subject: string
  category?: string | null
  status: SupportTicketStatus
  priority: SupportTicketPriority
  assigned_to_id?: number | null
  is_overdue?: boolean
  last_message_at: string
  created_at: string
  user?: UserProfileLite
  assigned_to?: UserProfileLite | null
  messages?: SupportMessage[]
}

export interface UserProfileLite {
  id: number
  email: string
  full_name: string
  phone?: string | null
  role: UserRole
}

export interface SupportStats {
  open: number
  in_progress: number
  pending_user: number
  resolved_today: number
  closed: number
  unassigned: number
  overdue: number
  avg_first_response_minutes?: number | null
  by_priority: Record<string, number>
}

export interface SupportUserView {
  id: number
  email: string
  full_name: string
  phone?: string | null
  role: UserRole
  is_active: boolean
  balance: string
  bonus_balance: string
  created_at: string
  orders_count: number
  tickets_count: number
  is_seller: boolean
  shop_id?: number | null
  shop_name?: string | null
}

// ─── Paid features & promotion (auction) ───────────────────────────────────
export type PromotionStatus = 'pending' | 'active' | 'outbid' | 'expired' | 'cancelled'
export type PaidFeaturePricing = 'fixed' | 'auction'

export interface PaidFeature {
  id: number
  key: string
  name: string
  description?: string | null
  placement: string
  pricing_mode: PaidFeaturePricing
  price: string
  billing_period: string
  slots: number
  is_enabled: boolean
}

export interface Promotion {
  id: number
  shop_id: number
  product_id?: number | null
  feature_key: string
  placement: string
  bid_amount: string
  status: PromotionStatus
  starts_at?: string | null
  ends_at?: string | null
  total_spent: string
  created_at: string
}

export interface AuctionStanding {
  feature_key: string
  slots: number
  bidders: number
  reserve: string
  min_winning_bid: string
}

// ─── Ad wallet ─────────────────────────────────────────────────────────────
export interface AdPackage { id: string; amount: string; bonus: string; total: string }
export interface AdWalletTxn {
  id: number; change: string; kind: string; description?: string | null
  balance_after: string; created_at: string
}
export interface AdWallet {
  ad_balance: string
  packages: AdPackage[]
  transactions: AdWalletTxn[]
}

// ─── Advanced promotions (rules & bundles) ─────────────────────────────────
export type PromoType = 'nplus' | 'volume'
export interface PromoTier { min_qty: number; percent: number }
export interface PromoRule {
  id: number
  shop_id: number
  title: string
  type: PromoType
  is_active: boolean
  starts_at?: string | null
  ends_at?: string | null
  product_id?: number | null
  category_id?: number | null
  buy_quantity: number
  free_quantity: number
  tiers: PromoTier[]
  created_at: string
}
export interface BundleItemT { id: number; product_id: number; quantity: number }
export interface Bundle {
  id: number
  shop_id: number
  title: string
  description?: string | null
  bundle_price: string
  is_active: boolean
  items: BundleItemT[]
  created_at: string
}
export interface ProductBundle {
  id: number
  title: string
  description?: string | null
  bundle_price: string
  list_price: string
  saving: string
  items: { product_id: number; title: string; quantity: number; price: string }[]
}
export interface CartPromoSummary {
  subtotal: string
  promo_discount: string
  breakdown: { label: string; amount: string }[]
  estimated_total: string
}

// ─── Disputes (arbitration) ────────────────────────────────────────────────
export type DisputeStatus = 'open' | 'in_mediation' | 'resolved' | 'cancelled'
export type DisputeResolution = 'none' | 'buyer_favor' | 'seller_favor' | 'partial'

export interface DisputeMessage {
  id: number
  sender_id: number
  sender_role: string
  text: string
  created_at: string
}
export interface Dispute {
  id: number
  order_id: number
  order_item_id?: number | null
  buyer_id: number
  shop_id: number
  opened_by: string
  subject: string
  reason?: string
  status: DisputeStatus
  resolution: DisputeResolution
  refund_amount?: string | null
  resolution_note?: string | null
  mediator_id?: number | null
  last_message_at: string
  created_at: string
  buyer?: UserProfileLite
  messages?: DisputeMessage[]
}

// ─── Gift certificates & promo balance ─────────────────────────────────────
export type GiftStatus = 'active' | 'redeemed' | 'cancelled' | 'expired'
export interface GiftCertificate {
  id: number
  code: string
  amount: string
  status: GiftStatus
  recipient_email?: string | null
  message?: string | null
  created_at: string
}
export interface PromoTxn {
  id: number; change: string; kind: string; description?: string | null
  balance_after: string; created_at: string
}
export interface PromoOverview {
  promo_balance: string
  transactions: PromoTxn[]
  purchased: { id: number; code: string; amount: string; status: string; recipient_email?: string | null; created_at: string }[]
}

// ─── Loyalty program ───────────────────────────────────────────────────────
export interface LoyaltyTier {
  id: number
  key: string
  name: string
  level: number
  min_spend: string
  cashback_percent: string
  free_shipping: boolean
  perks?: string | null
  color?: string | null
  retention_days: number
  is_active: boolean
}
export interface LoyaltyStatus {
  qualifying_spend: string
  current: any | null
  next: any | null
  to_next_amount: string
  downgrade_at?: string | null
  days_to_downgrade?: number | null
  all_tiers: any[]
}
