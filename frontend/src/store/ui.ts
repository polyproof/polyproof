import { create } from 'zustand'

interface UIStore {
  treeCollapsed: Set<string>
  toggleCollapse: (id: string) => void
}

export const useUIStore = create<UIStore>()((set) => ({
  treeCollapsed: new Set<string>(),

  toggleCollapse: (id) =>
    set((state) => {
      const next = new Set(state.treeCollapsed)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return { treeCollapsed: next }
    }),
}))
