import { create } from 'zustand'
import type { LayerKey } from '@/types'

interface CitySenseStore {
  // Selected cell (null = nothing selected)
  selectedCellId: string | null
  setSelectedCellId: (id: string | null) => void

  // Active map layer
  activeLayer: LayerKey
  setActiveLayer: (layer: LayerKey) => void

  // Panel visibility
  statsPanelOpen: boolean
  setStatsPanelOpen: (open: boolean) => void

  // Chat panel visibility
  chatOpen: boolean
  setChatOpen: (open: boolean) => void

  // API health
  apiConnected: boolean
  setApiConnected: (connected: boolean) => void
}

export const useStore = create<CitySenseStore>((set) => ({
  selectedCellId: null,
  setSelectedCellId: (id) => set({ selectedCellId: id }),

  activeLayer: 'environmental_health',
  setActiveLayer: (layer) => set({ activeLayer: layer }),

  statsPanelOpen: true,
  setStatsPanelOpen: (open) => set({ statsPanelOpen: open }),

  chatOpen: false,
  setChatOpen: (open) => set({ chatOpen: open }),

  apiConnected: false,
  setApiConnected: (connected) => set({ apiConnected: connected }),
}))
