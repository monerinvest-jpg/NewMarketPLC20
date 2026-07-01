import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'
import { authApi } from '@/api'
import { useCartStore } from './cartStore'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
  setTokens: (access: string, refresh: string) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isLoading: false,

      setTokens: (access, refresh) => {
        localStorage.setItem('access_token', access)
        localStorage.setItem('refresh_token', refresh)
        set({ accessToken: access, refreshToken: refresh })
        // Carry over anything the visitor collected before signing in.
        useCartStore.getState().mergeGuestCart().catch(() => {})
      },

      login: async (email, password) => {
        set({ isLoading: true })
        try {
          const tokens = await authApi.login(email, password)
          localStorage.setItem('access_token', tokens.access_token)
          localStorage.setItem('refresh_token', tokens.refresh_token)
          set({
            accessToken: tokens.access_token,
            refreshToken: tokens.refresh_token,
          })
          const user = await authApi.me()
          set({ user })
          // Merge the guest cart into the server cart (idempotent, never throws).
          await useCartStore.getState().mergeGuestCart().catch(() => {})
        } finally {
          set({ isLoading: false })
        }
      },

      logout: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({ user: null, accessToken: null, refreshToken: null })
      },

      fetchMe: async () => {
        try {
          const user = await authApi.me()
          set({ user })
        } catch {
          get().logout()
        }
      },
    }),
    {
      name: 'auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
    }
  )
)
