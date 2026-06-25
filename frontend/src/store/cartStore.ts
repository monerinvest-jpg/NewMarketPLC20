import { create } from 'zustand'
import type { CartItem } from '@/types'
import { cartApi } from '@/api'

interface CartState {
  items: CartItem[]
  loading: boolean
  fetchCart: () => Promise<void>
  addItem: (product_id: number, quantity?: number, variant_id?: number) => Promise<void>
  updateItem: (item_id: number, quantity: number) => Promise<void>
  removeItem: (item_id: number) => Promise<void>
  clearCart: () => Promise<void>
  totalItems: () => number
  totalPrice: () => number
}

export const useCartStore = create<CartState>((set, get) => ({
  items: [],
  loading: false,

  fetchCart: async () => {
    set({ loading: true })
    try {
      const items = await cartApi.get()
      set({ items })
    } finally {
      set({ loading: false })
    }
  },

  addItem: async (product_id, quantity = 1, variant_id) => {
    await cartApi.add(product_id, quantity, variant_id)
    // Refetch to keep variant lines and merged quantities accurate
    const items = await cartApi.get()
    set({ items })
  },

  updateItem: async (item_id, quantity) => {
    const updated = await cartApi.update(item_id, quantity)
    set((s) => ({
      items: s.items.map((i) => (i.id === item_id ? updated : i)),
    }))
  },

  removeItem: async (item_id) => {
    await cartApi.remove(item_id)
    set((s) => ({ items: s.items.filter((i) => i.id !== item_id) }))
  },

  clearCart: async () => {
    await cartApi.clear()
    set({ items: [] })
  },

  totalItems: () => get().items.reduce((sum, i) => sum + i.quantity, 0),

  totalPrice: () =>
    get().items.reduce((sum, i) => sum + parseFloat(i.product.price) * i.quantity, 0),
}))
