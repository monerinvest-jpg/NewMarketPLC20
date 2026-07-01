import { create } from 'zustand'
import type { CartItem } from '@/types'
import { cartApi, productsApi } from '@/api'

// Guest cart: anonymous visitors keep a local cart (product snapshots in
// localStorage) so "add to cart" never demands a login. On login/register the
// local items are merged into the server cart (mergeGuestCart) and the local
// copy is dropped. Server stays the source of truth for authenticated users.
const GUEST_KEY = 'guest_cart'

const isGuest = () => !localStorage.getItem('access_token')

function readGuestCart(): CartItem[] {
  try {
    return JSON.parse(localStorage.getItem(GUEST_KEY) || '[]')
  } catch {
    return []
  }
}

function writeGuestCart(items: CartItem[]) {
  localStorage.setItem(GUEST_KEY, JSON.stringify(items))
}

// Deterministic negative id so guest lines never collide with server ids.
const guestLineId = (product_id: number, variant_id?: number) =>
  -(product_id * 100000 + (variant_id || 0))

interface CartState {
  items: CartItem[]
  loading: boolean
  fetchCart: () => Promise<void>
  addItem: (product_id: number, quantity?: number, variant_id?: number) => Promise<void>
  updateItem: (item_id: number, quantity: number) => Promise<void>
  removeItem: (item_id: number) => Promise<void>
  clearCart: () => Promise<void>
  mergeGuestCart: () => Promise<void>
  totalItems: () => number
  totalPrice: () => number
}

export const useCartStore = create<CartState>((set, get) => ({
  items: [],
  loading: false,

  fetchCart: async () => {
    if (isGuest()) {
      set({ items: readGuestCart() })
      return
    }
    set({ loading: true })
    try {
      const items = await cartApi.get()
      set({ items })
    } finally {
      set({ loading: false })
    }
  },

  addItem: async (product_id, quantity = 1, variant_id) => {
    if (isGuest()) {
      const items = readGuestCart()
      const lineId = guestLineId(product_id, variant_id)
      const existing = items.find((i) => i.id === lineId)
      if (existing) {
        existing.quantity = Math.min(existing.quantity + quantity, existing.product.quantity || 99)
      } else {
        // Snapshot the product so the cart renders offline from localStorage.
        const product = await productsApi.get(product_id)
        items.push({
          id: lineId, product_id, variant_id,
          quantity: Math.min(quantity, product.quantity || 99), product,
        } as unknown as CartItem)
      }
      writeGuestCart(items)
      set({ items })
      return
    }
    await cartApi.add(product_id, quantity, variant_id)
    // Refetch to keep variant lines and merged quantities accurate
    const items = await cartApi.get()
    set({ items })
  },

  updateItem: async (item_id, quantity) => {
    if (isGuest()) {
      const items = readGuestCart().map((i) => (i.id === item_id ? { ...i, quantity } : i))
      writeGuestCart(items)
      set({ items })
      return
    }
    const updated = await cartApi.update(item_id, quantity)
    set((s) => ({
      items: s.items.map((i) => (i.id === item_id ? updated : i)),
    }))
  },

  removeItem: async (item_id) => {
    if (isGuest()) {
      const items = readGuestCart().filter((i) => i.id !== item_id)
      writeGuestCart(items)
      set({ items })
      return
    }
    await cartApi.remove(item_id)
    set((s) => ({ items: s.items.filter((i) => i.id !== item_id) }))
  },

  clearCart: async () => {
    if (isGuest()) {
      writeGuestCart([])
      set({ items: [] })
      return
    }
    await cartApi.clear()
    set({ items: [] })
  },

  // Push locally collected guest items into the server cart (after login).
  // Idempotent: clears the local copy first so repeated calls are no-ops.
  mergeGuestCart: async () => {
    if (isGuest()) return
    const guestItems = readGuestCart()
    if (guestItems.length === 0) return
    localStorage.removeItem(GUEST_KEY)
    for (const item of guestItems) {
      try {
        await cartApi.add(item.product_id, item.quantity, (item as any).variant_id || undefined)
      } catch {
        // Item may be out of stock / gone — skip it rather than fail the login.
      }
    }
    const items = await cartApi.get()
    set({ items })
  },

  totalItems: () => get().items.reduce((sum, i) => sum + i.quantity, 0),

  totalPrice: () =>
    get().items.reduce((sum, i) => sum + parseFloat(i.product.price) * i.quantity, 0),
}))
