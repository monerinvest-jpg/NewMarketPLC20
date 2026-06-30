// Host-aware split between the buyer/admin app and the seller cabinet.
//
// The same SPA bundle is served on both the main domain and `seller.<domain>`.
// On boot the app inspects the hostname and renders the seller cabinet
// (dedicated login + sider layout) instead of the main storefront.
//
// This is the "Variant 1" (single bundle, host-aware) approach. It is kept
// deliberately self-contained — `SellerApp` is a standalone <Routes> tree —
// so a future move to a separate Vite entry / container (Variant 2) is a
// build/deploy change, not a rewrite.

const SELLER_PREFIX = 'seller.'

// `VITE_APP_TARGET=seller` forces the seller app even on a bare host
// (localhost has no subdomain), so the cabinet can be run/tested locally.
const FORCED = (import.meta.env.VITE_APP_TARGET as string | undefined) === 'seller'

export function isSellerHost(): boolean {
  if (FORCED) return true
  const h = window.location.hostname
  return h === 'seller' || h.startsWith(SELLER_PREFIX)
}

// Origin of the seller cabinet for the current environment, e.g.
// https://example.com -> https://seller.example.com (port preserved for dev).
export function sellerOrigin(): string {
  const { protocol, hostname, port } = window.location
  const host = hostname.startsWith(SELLER_PREFIX) ? hostname : `${SELLER_PREFIX}${hostname}`
  return `${protocol}//${host}${port ? `:${port}` : ''}`
}

// Origin of the main storefront, e.g.
// https://seller.example.com -> https://example.com.
export function mainOrigin(): string {
  const { protocol, hostname, port } = window.location
  const host = hostname.startsWith(SELLER_PREFIX) ? hostname.slice(SELLER_PREFIX.length) : hostname
  return `${protocol}//${host}${port ? `:${port}` : ''}`
}
