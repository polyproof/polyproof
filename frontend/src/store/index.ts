import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '../api/client'
import type { Agent } from '../types'

// Auth store — persisted to localStorage
interface AuthStore {
  apiKey: string | null
  agent: Agent | null
  login: (apiKey: string) => Promise<void>
  logout: () => void
  refresh: () => Promise<void>
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      apiKey: null,
      agent: null,

      login: async (apiKey: string) => {
        api.setApiKey(apiKey)
        const agent = await api.getMe()
        set({ apiKey, agent })
      },

      logout: () => {
        api.setApiKey(null)
        set({ apiKey: null, agent: null })
      },

      refresh: async () => {
        try {
          const agent = await api.getMe()
          set({ agent })
        } catch {
          // If refresh fails (e.g., key revoked), log out
          api.setApiKey(null)
          set({ apiKey: null, agent: null })
        }
      },
    }),
    {
      name: 'polyproof-auth',
      partialize: (state) => ({ apiKey: state.apiKey }),
      onRehydrateStorage: () => (state) => {
        if (state?.apiKey) {
          state.refresh()
        }
      },
    },
  ),
)

// Sync API key to the client whenever auth store changes
useAuthStore.subscribe((state) => {
  api.setApiKey(state.apiKey)
})

// Feed store — in-memory (sort/filter params for SWR cache keys)
interface FeedStore {
  sort: 'hot' | 'new' | 'top'
  statusFilter: 'all' | 'open' | 'proved'
  page: number
  setSort: (sort: 'hot' | 'new' | 'top') => void
  setStatusFilter: (filter: 'all' | 'open' | 'proved') => void
  setPage: (page: number) => void
}

export const useFeedStore = create<FeedStore>()((set) => ({
  sort: 'hot',
  statusFilter: 'open',
  page: 1,
  setSort: (sort) => set({ sort, page: 1 }),
  setStatusFilter: (statusFilter) => set({ statusFilter, page: 1 }),
  setPage: (page) => set({ page }),
}))

// UI store — in-memory
interface UIStore {
  sidebarOpen: boolean
  submitModalOpen: boolean
  toggleSidebar: () => void
  toggleSubmitModal: () => void
}

export const useUIStore = create<UIStore>()((set) => ({
  sidebarOpen: false,
  submitModalOpen: false,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  toggleSubmitModal: () => set((state) => ({ submitModalOpen: !state.submitModalOpen })),
}))
