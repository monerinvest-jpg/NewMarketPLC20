import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Currency } from '@/types'

interface CurrencyState {
  current: string
  rates: Currency[]
  setCurrent: (code: string) => void
  setRates: (rates: Currency[]) => void
  format: (amountRub: number | string) => string
}

// Persisted currency selection. Prices are stored in RUB; the selected currency
// converts for display only. (Normal Vite app, not a sandboxed artifact.)
export const useCurrencyStore = create<CurrencyState>()(
  persist(
    (set, get) => ({
      current: 'RUB',
      rates: [{ code: 'RUB', rate: '1', symbol: '₽' }],
      setCurrent: (code) => set({ current: code }),
      setRates: (rates) => set({ rates }),
      format: (amountRub) => {
        const amount = typeof amountRub === 'string' ? parseFloat(amountRub) : amountRub
        const { current, rates } = get()
        const cur = rates.find((r) => r.code === current) || rates[0]
        const converted = amount * parseFloat(cur?.rate || '1')
        const formatted = converted.toLocaleString('ru', { maximumFractionDigits: 2 })
        return `${formatted} ${cur?.symbol || '₽'}`
      },
    }),
    { name: 'currency-storage' }
  )
)
