import { create } from 'zustand'
import type { LayerKey, TooltipInfo } from '@/types'

interface CitySenseStore {
  // Selected cell (null = nothing selected)
  selectedCellId: string | null
  setSelectedCellId: (id: string | null) => void

  // Active map layer
  activeLayer: LayerKey
  setActiveLayer: (layer: LayerKey) => void

  // Hover tooltip
  tooltip: TooltipInfo | null
  setTooltip: (info: TooltipInfo | null) => void

  // Panel visibility
  statsPanelOpen: boolean
  setStatsPanelOpen: (open: boolean) => void

  // API health
  apiConnected: boolean
  setApiConnected: (connected: boolean) => void
}

export const useStore = create<CitySenseStore>((set) => ({
  selectedCellId: null,
  setSelectedCellId: (id) => set({ selectedCellId: id }),

  activeLayer: 'environmental_health',
  setActiveLayer: (layer) => set({ activeLayer: layer }),

  tooltip: null,
  setTooltip: (info) => set({ tooltip: info }),

  statsPanelOpen: true,
  setStatsPanelOpen: (open) => set({ statsPanelOpen: open }),

  apiConnected: false,
  setApiConnected: (connected) => set({ apiConnected: connected }),
}))
