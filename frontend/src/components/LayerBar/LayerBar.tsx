// ============================================================
// LayerBar — Bottom floating layer switcher
// ============================================================

import { useStore } from '@/store/useStore'
import type { LayerKey } from '@/types'
import { LAYER_CONFIGS } from '@/components/Map/layers'

// ----------------------------------------------------------------
// Layer buttons in display order
// ----------------------------------------------------------------

const LAYERS: { key: LayerKey; label: string; gradient: string }[] = [
  {
    key: 'environmental_health',
    label: 'EHI',
    gradient: 'linear-gradient(90deg, #ff3b5c, #ffb340, #00ff9f)',
  },
  {
    key: 'risk_score',
    label: 'Risk',
    gradient: 'linear-gradient(90deg, #00ff9f, #ffb340, #ff3b5c)',
  },
  {
    key: 'mean_lst',
    label: 'LST',
    gradient: 'linear-gradient(90deg, #1e78dc, #ff3b5c)',
  },
  {
    key: 'mean_ndvi',
    label: 'NDVI',
    gradient: 'linear-gradient(90deg, #8b5a2b, #14c83c)',
  },
  {
    key: 'mean_ndbi',
    label: 'NDBI',
    gradient: 'linear-gradient(90deg, #00ff9f, #b06bff)',
  },
  {
    key: 'uhi_intensity',
    label: 'UHI',
    gradient: 'linear-gradient(90deg, #1464dc, #ff9614)',
  },
  {
    key: 'cluster',
    label: 'Clusters',
    gradient: 'linear-gradient(90deg, #00b4ff, #00dc78, #ff5038, #b464ff, #ffb428)',
  },
  {
    key: 'planning_priority_score',
    label: 'Priority',
    gradient: 'linear-gradient(90deg, #00ff9f, #ffb340, #ff3b5c)',
  },
  {
    key: 'flood_susceptibility_score',
    label: 'Flood',
    gradient: 'linear-gradient(90deg, #1e78dc, #b06bff, #ff3b5c)',
  },
  {
    key: 'iai_score',
    label: 'Access',
    gradient: 'linear-gradient(90deg, #ff3b5c, #ffb340, #00ff9f)',
  },
  {
    key: 'burden_score',
    label: 'Burden',
    gradient: 'linear-gradient(90deg, #00ff9f, #ffb340, #ff3b5c)',
  },
]

// ----------------------------------------------------------------
// Component
// ----------------------------------------------------------------

export function LayerBar() {
  const activeLayer = useStore((s) => s.activeLayer)
  const setActiveLayer = useStore((s) => s.setActiveLayer)

  return (
    <nav
      id="layer-bar"
      className="panel animate-slide-bottom"
      style={{
        position: 'fixed',
        bottom: 18,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 150,
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        padding: '5px 8px',
        borderRadius: 12,
        background: 'rgba(4, 14, 32, 0.88)',
        border: '1px solid rgba(0, 200, 255, 0.22)',
        boxShadow: '0 12px 40px rgba(0, 4, 16, 0.7), 0 0 20px rgba(0, 212, 255, 0.08)',
        backdropFilter: 'blur(20px) saturate(1.6)',
        maxWidth: 'calc(100vw - 140px)',
        overflowX: 'auto',
        scrollbarWidth: 'none',
      }}
    >
      {LAYERS.map(({ key, label, gradient }) => {
        const isActive = activeLayer === key
        return (
          <button
            key={key}
            type="button"
            title={LAYER_CONFIGS[key]?.description ?? label}
            onClick={() => setActiveLayer(key)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '5px 11px',
              borderRadius: 6,
              border: isActive
                ? '1px solid var(--glow-cyan)'
                : '1px solid transparent',
              background: isActive
                ? 'linear-gradient(180deg, rgba(0, 212, 255, 0.16) 0%, rgba(0, 180, 255, 0.06) 100%)'
                : 'transparent',
              cursor: 'pointer',
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              fontWeight: isActive ? 700 : 500,
              letterSpacing: '0.08em',
              color: isActive ? 'var(--glow-cyan)' : 'var(--text-secondary)',
              textShadow: isActive ? '0 0 10px var(--glow-cyan-dim)' : 'none',
              boxShadow: isActive
                ? '0 0 14px rgba(0, 212, 255, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.2)'
                : 'none',
              transform: isActive ? 'scale(1.03)' : 'scale(1)',
              transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
              textTransform: 'uppercase',
              flexShrink: 0,
              whiteSpace: 'nowrap',
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = 'rgba(10, 28, 58, 0.65)'
                e.currentTarget.style.transform = 'translateY(-1px)'
                e.currentTarget.style.color = 'var(--text-primary)'
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.transform = 'scale(1)'
                e.currentTarget.style.color = 'var(--text-secondary)'
              }
            }}
          >
            {/* Colour swatch */}
            <span
              style={{
                width: 10,
                height: 6,
                borderRadius: 2,
                background: gradient,
                flexShrink: 0,
                boxShadow: isActive ? '0 0 6px rgba(0, 212, 255, 0.5)' : 'none',
                opacity: isActive ? 1 : 0.65,
                border: '1px solid rgba(255, 255, 255, 0.15)',
              }}
            />
            {label}
          </button>
        )
      })}
    </nav>
  )
}
