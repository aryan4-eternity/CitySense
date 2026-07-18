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
        bottom: 16,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 150,
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        padding: '5px 8px',
        borderRadius: 10,
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
              gap: 6,
              padding: '6px 12px',
              borderRadius: 6,
              border: isActive
                ? '1px solid var(--glow-cyan)'
                : '1px solid transparent',
              background: isActive ? 'var(--bg-card)' : 'transparent',
              cursor: 'pointer',
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              fontWeight: isActive ? 700 : 400,
              letterSpacing: '0.06em',
              color: isActive ? 'var(--glow-cyan)' : 'var(--text-secondary)',
              textShadow: isActive ? '0 0 8px var(--glow-cyan-dim)' : 'none',
              boxShadow: isActive
                ? '0 0 10px rgba(0, 212, 255, 0.15), inset 0 0 8px rgba(0, 212, 255, 0.06)'
                : 'none',
              transition: 'all 0.2s ease',
              textTransform: 'uppercase',
            }}
            onMouseEnter={(e) => {
              if (!isActive)
                e.currentTarget.style.background = 'var(--bg-card-hover)'
            }}
            onMouseLeave={(e) => {
              if (!isActive) e.currentTarget.style.background = 'transparent'
            }}
          >
            {/* Colour swatch */}
            <span
              style={{
                width: 14,
                height: 8,
                borderRadius: 2,
                background: gradient,
                flexShrink: 0,
                opacity: isActive ? 1 : 0.6,
              }}
            />
            {label}
          </button>
        )
      })}
    </nav>
  )
}
