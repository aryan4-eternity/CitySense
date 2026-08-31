// ============================================================
// RegionSelector.tsx — Multi-District MMR Regional Zone Selector
// Allows filtering & camera fly-to across 5 MMR sub-districts
// ============================================================

import { useState, useRef, useEffect } from 'react'
import { Globe, MapPin, ChevronDown, Check, Building2, Trees, Waves, Factory } from 'lucide-react'
import { useStore } from '@/store/useStore'
import { useCityStats } from '@/api/citysense'
import type { MMRRegionKey, MMRRegionOption } from '@/types'

export const MMR_REGIONS: MMRRegionOption[] = [
  {
    key: 'all',
    label: 'All MMR Region',
    shortLabel: 'All MMR',
    icon: '🌐',
    corporation: 'MMRDA Regional Scope',
    description: 'Macro-scale regional analysis spanning the full MMR grid',
    center: [72.95, 19.12],
    zoom: 10.2,
  },
  {
    key: 'island_city',
    label: 'Mumbai Island City',
    shortLabel: 'South Mumbai',
    icon: '🏛️',
    corporation: 'BMC (South Zone)',
    description: 'Colaba, Fort, Marine Drive, Malabar Hill, Dadar, Worli, Byculla',
    center: [72.825, 18.960],
    zoom: 12.6,
  },
  {
    key: 'suburban',
    label: 'Suburban Mumbai',
    shortLabel: 'Suburbs',
    icon: '🏙️',
    corporation: 'BMC (Western & Eastern)',
    description: 'Bandra, Andheri, Juhu, Malad, Borivali, Kurla, Chembur, Mulund',
    center: [72.865, 19.125],
    zoom: 11.8,
  },
  {
    key: 'navi_mumbai',
    label: 'Navi Mumbai & Panvel',
    shortLabel: 'Navi Mumbai',
    icon: '🌊',
    corporation: 'NMMC / CIDCO / PMC',
    description: 'Vashi, Nerul, Belapur, Kharghar, Panvel, Ulwe, Airoli, Taloja',
    center: [73.020, 19.040],
    zoom: 11.8,
  },
  {
    key: 'thane',
    label: 'Thane Municipal Corporation',
    shortLabel: 'Thane',
    icon: '🌲',
    corporation: 'TMC',
    description: 'Thane West, Ghodbunder Road, Majiwada, Naupada, Kalwa, Mumbra',
    center: [72.975, 19.215],
    zoom: 12.2,
  },
  {
    key: 'kalyan_dombivli',
    label: 'Kalyan-Dombivli & East',
    shortLabel: 'KDMC Belt',
    icon: '🏭',
    corporation: 'KDMC / Extended MMR',
    description: 'Kalyan, Dombivli, Ulhasnagar, Bhiwandi, Mira-Bhayandar',
    center: [73.120, 19.240],
    zoom: 11.8,
  },
]

export function RegionSelector() {
  const selectedRegion = useStore((s) => s.selectedRegion)
  const setSelectedRegion = useStore((s) => s.setSelectedRegion)
  const { data: stats } = useCityStats()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const activeOption = MMR_REGIONS.find((r) => r.key === selectedRegion) || MMR_REGIONS[0]

  // Derive the region count from live data instead of hard-coding it
  const regions = MMR_REGIONS.map((r) =>
    r.key === 'all' && stats?.total_cells
      ? { ...r, description: `Macro-scale regional analysis spanning ${stats.total_cells.toLocaleString()} grid cells` }
      : r,
  )

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = (key: MMRRegionKey) => {
    setSelectedRegion(key)
    setIsOpen(false)
  }

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      {/* Trigger Pill */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        title="Switch MMR District / Region Focus"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '4px 11px',
          borderRadius: 16,
          background: isOpen
            ? 'rgba(0, 212, 255, 0.2)'
            : 'linear-gradient(135deg, rgba(6, 20, 48, 0.9) 0%, rgba(2, 10, 26, 0.9) 100%)',
          border: isOpen ? '1px solid var(--glow-cyan)' : '1px solid rgba(0, 212, 255, 0.3)',
          boxShadow: isOpen
            ? '0 0 16px rgba(0, 212, 255, 0.3)'
            : '0 2px 8px rgba(0, 0, 0, 0.3)',
          color: 'var(--text-bright)',
          cursor: 'pointer',
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.04em',
          transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
        onMouseEnter={(e) => {
          if (!isOpen) {
            e.currentTarget.style.borderColor = 'rgba(0, 220, 255, 0.6)'
            e.currentTarget.style.boxShadow = '0 0 12px rgba(0, 212, 255, 0.2)'
          }
        }}
        onMouseLeave={(e) => {
          if (!isOpen) {
            e.currentTarget.style.borderColor = 'rgba(0, 212, 255, 0.3)'
            e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.3)'
          }
        }}
      >
        <span>{activeOption.icon}</span>
        <span style={{ color: 'var(--glow-cyan)' }}>{activeOption.shortLabel}</span>
        <ChevronDown size={12} color="var(--text-muted)" style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          className="panel animate-fade-in"
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            left: 0,
            width: 290,
            borderRadius: 12,
            background: 'linear-gradient(135deg, rgba(6, 18, 42, 0.98) 0%, rgba(2, 8, 22, 0.98) 100%)',
            border: '1px solid rgba(0, 212, 255, 0.35)',
            boxShadow: '0 16px 40px rgba(0, 4, 16, 0.85), 0 0 24px rgba(0, 212, 255, 0.18)',
            backdropFilter: 'blur(20px)',
            zIndex: 300,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: '8px 12px',
              fontSize: 9,
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)',
              borderBottom: '1px solid rgba(0, 200, 255, 0.1)',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span>MMR DISTRICT SELECTOR</span>
            <span style={{ color: 'var(--glow-cyan)' }}>5 ZONES</span>
          </div>

          <div style={{ padding: '4px 0' }}>
            {regions.map((region) => {
              const isSelected = region.key === selectedRegion

              return (
                <div
                  key={region.key}
                  onClick={() => handleSelect(region.key)}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(0, 212, 255, 0.12)' : 'transparent',
                    borderLeft: isSelected ? '3px solid var(--glow-cyan)' : '3px solid transparent',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) e.currentTarget.style.background = 'rgba(0, 212, 255, 0.06)'
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) e.currentTarget.style.background = 'transparent'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9 }}>
                    <span style={{ fontSize: 15, marginTop: 1 }}>{region.icon}</span>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)' }}>
                          {region.label}
                        </span>
                      </div>
                      <div
                        className="font-mono"
                        style={{ fontSize: 9, color: 'var(--glow-cyan)', marginTop: 1 }}
                      >
                        {region.corporation}
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 3, lineHeight: 1.3 }}>
                        {region.description}
                      </div>
                    </div>
                  </div>

                  {isSelected && (
                    <Check size={14} color="var(--glow-cyan)" style={{ marginTop: 3, flexShrink: 0 }} />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
