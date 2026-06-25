import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Product } from '@/types'

interface CompareState {
  items: Product[]
  toggle: (product: Product) => void
  remove: (id: number) => void
  clear: () => void
  has: (id: number) => boolean
}

// Persisted to localStorage so the comparison list survives navigation.
// (This is a normal Vite app, not a sandboxed artifact, so localStorage is fine.)
export const useCompareStore = create<CompareState>()(
  persist(
    (set, get) => ({
      items: [],
      toggle: (product) => {
        const exists = get().items.find((p) => p.id === product.id)
        if (exists) {
          set({ items: get().items.filter((p) => p.id !== product.id) })
        } else {
          if (get().items.length >= 4) return // cap at 4 for a readable table
          set({ items: [...get().items, product] })
        }
      },
      remove: (id) => set({ items: get().items.filter((p) => p.id !== id) }),
      clear: () => set({ items: [] }),
      has: (id) => !!get().items.find((p) => p.id === id),
    }),
    { name: 'compare-storage' }
  )
)
