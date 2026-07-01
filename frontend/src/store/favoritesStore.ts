import { create } from 'zustand'
import { favoritesApi } from '@/api'

// Lightweight favorite-ids cache so product cards can render (and toggle) the
// heart without each card fetching the favorites list. Loaded once per session
// for authenticated users.
interface FavoritesState {
  ids: number[]
  loaded: boolean
  load: () => Promise<void>
  toggle: (productId: number) => Promise<boolean> // returns the new state
  has: (productId: number) => boolean
}

export const useFavoritesStore = create<FavoritesState>((set, get) => ({
  ids: [],
  loaded: false,

  load: async () => {
    if (get().loaded) return
    try {
      const favs = await favoritesApi.list()
      set({ ids: favs.map((f: any) => f.product_id ?? f.id), loaded: true })
    } catch {
      set({ loaded: true })
    }
  },

  toggle: async (productId) => {
    const isFav = get().ids.includes(productId)
    if (isFav) {
      set({ ids: get().ids.filter((id) => id !== productId) })
      await favoritesApi.remove(productId).catch(() => {})
      return false
    }
    set({ ids: [...get().ids, productId] })
    await favoritesApi.add(productId).catch(() => {})
    return true
  },

  has: (productId) => get().ids.includes(productId),
}))
