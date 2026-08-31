import { create } from 'zustand'
import type { LayerKey, BasemapKey, MMRRegionKey } from '@/types'

interface CitySenseStore {
  // Selected cell (null = nothing selected)
  selectedCellId: string | null
  setSelectedCellId: (id: string | null) => void

  // Active MMR Region filter / zoom focus
  selectedRegion: MMRRegionKey
  setSelectedRegion: (region: MMRRegionKey) => void

  // Active map layer
  activeLayer: LayerKey
  setActiveLayer: (layer: LayerKey) => void

  // Active Basemap Style
  basemapStyle: BasemapKey
  setBasemapStyle: (style: BasemapKey) => void

  // Panel visibility
  statsPanelOpen: boolean
  setStatsPanelOpen: (open: boolean) => void

  // Chat panel visibility
  chatOpen: boolean
  setChatOpen: (open: boolean) => void

  // Satellite telemetry modal
  satelliteModalOpen: boolean
  setSatelliteModalOpen: (open: boolean) => void

  // 3D Extrusion Mode
  is3D: boolean
  setIs3D: (is3D: boolean) => void

  // API health
  apiConnected: boolean
  setApiConnected: (connected: boolean) => void
}

export const useStore = create<CitySenseStore>((set) => ({
  selectedCellId: null,
  setSelectedCellId: (id) => set({ selectedCellId: id }),

  selectedRegion: 'all',
  setSelectedRegion: (region) => set({ selectedRegion: region }),

  activeLayer: 'environmental_health',
  setActiveLayer: (layer) => set({ activeLayer: layer }),

  basemapStyle: 'satellite',
  setBasemapStyle: (style) => set({ basemapStyle: style }),

  statsPanelOpen: true,
  setStatsPanelOpen: (open) => set({ statsPanelOpen: open }),

  chatOpen: false,
  setChatOpen: (open) => set({ chatOpen: open }),

  satelliteModalOpen: false,
  setSatelliteModalOpen: (open) => set({ satelliteModalOpen: open }),

  is3D: false,
  setIs3D: (is3D) => set({ is3D }),

  apiConnected: false,
  setApiConnected: (connected) => set({ apiConnected: connected }),
}))
