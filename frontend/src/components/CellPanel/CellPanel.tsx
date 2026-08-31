// ============================================================
// CellPanel — Right floating detail panel with tabs
// ============================================================

import { useState } from 'react'
import { MapPin } from 'lucide-react'
import { useStore } from '@/store/useStore'
import { useCell } from '@/api/citysense'
import { EnvTab } from './EnvTab'
import { PlanningTab } from './PlanningTab'
import { RawTab } from './RawTab'

type TabKey = 'env' | 'planning' | 'raw'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'env',      label: 'Environment' },
  { key: 'planning', label: 'Planning' },
  { key: 'raw',      label: 'Raw Data' },
]

const PRIORITY_BADGE: Record<string, string> = {
  Critical: 'badge-critical',
  High: 'badge-high',
  Medium: 'badge-medium',
  Low: 'badge-low',
  'Very Low': 'badge-verylow',
}

function getMunicipalAuthority(ward?: string, locality?: string): string {
  const loc = (locality || '').toLowerCase()
  const w = (ward || '').toLowerCase()

  if (loc.includes('vashi') || loc.includes('nerul') || loc.includes('belapur') || loc.includes('kharghar') || loc.includes('panvel') || loc.includes('airoli') || loc.includes('ulwe') || loc.includes('taloja')) {
    return 'NMMC / CIDCO'
  }
  if (loc.includes('thane') || loc.includes('ghodbunder') || loc.includes('majiwada') || loc.includes('kalwa') || loc.includes('mumbra') || loc.includes('naupada')) {
    return 'TMC (Thane)'
  }
  if (loc.includes('kalyan') || loc.includes('dombivli') || loc.includes('ulhasnagar') || loc.includes('bhiwandi')) {
    return 'KDMC (Kalyan-Dombivli)'
  }
  if (loc.includes('mira') || loc.includes('bhayandar')) {
    return 'MBMC (Mira-Bhayandar)'
  }
  if (loc.includes('vasai') || loc.includes('virar')) {
    return 'VVMC (Vasai-Virar)'
  }
  return 'BMC (Brihanmumbai)'
}

export function CellPanel() {
  const selectedCellId = useStore((s) => s.selectedCellId)
  const setSelectedCellId = useStore((s) => s.setSelectedCellId)
  const { data: bundle, isLoading, error } = useCell(selectedCellId)
  const [activeTab, setActiveTab] = useState<TabKey>('env')

  if (!selectedCellId) return null

  const locality = bundle?.geographic?.primary_locality || (bundle?.master as any)?.primary_locality
  const ward = bundle?.geographic?.ward || (bundle?.master as any)?.ward
  const authority = getMunicipalAuthority(ward, locality)

  return (
    <aside
      id="cell-panel"
      className="panel cell-panel-container animate-slide-right"
      style={{
        position: 'fixed',
        right: 16,
        top: 64,
        bottom: 64,
        width: 350,
        zIndex: 100,
        borderRadius: 10,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        border: '1px solid rgba(0, 200, 255, 0.22)',
        boxShadow: '0 16px 48px rgba(0, 4, 16, 0.7), 0 0 24px rgba(0, 212, 255, 0.08)',
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          padding: '14px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
          background: 'rgba(0, 180, 255, 0.03)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              padding: '3px 8px',
              borderRadius: 5,
              background: 'rgba(0, 212, 255, 0.1)',
              border: '1px solid rgba(0, 212, 255, 0.3)',
            }}
          >
            <span
              className="font-mono"
              style={{
                fontSize: 13,
                fontWeight: 800,
                color: 'var(--glow-cyan)',
                letterSpacing: '0.06em',
                textShadow: '0 0 8px var(--glow-cyan-dim)',
              }}
            >
              {selectedCellId}
            </span>
          </div>
          {bundle?.environment?.environmental_status && (
            <span
              className={
                bundle.environment.environmental_status === 'Critical'
                  ? 'badge-critical-ehi'
                  : bundle.environment.environmental_status === 'Poor'
                    ? 'badge-poor'
                    : bundle.environment.environmental_status === 'Moderate'
                      ? 'badge-moderate'
                      : bundle.environment.environmental_status === 'Good'
                        ? 'badge-good'
                        : 'badge-excellent'
              }
              style={{
                fontSize: 9,
                padding: '2px 7px',
                borderRadius: 4,
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}
            >
              {bundle.environment.environmental_status}
            </span>
          )}
          {bundle?.planning?.planning_priority && (
            <span
              className={`${PRIORITY_BADGE[bundle.planning.planning_priority] ?? 'badge-medium'} ${
                bundle.planning.planning_priority === 'Critical'
                  ? 'animate-pulse-red'
                  : ''
              }`}
              style={{
                fontSize: 9,
                padding: '2px 7px',
                borderRadius: 4,
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}
            >
              {bundle.planning.planning_priority}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => setSelectedCellId(null)}
          aria-label="Close cell panel"
          style={{
            width: 24,
            height: 24,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '1px solid var(--border)',
            borderRadius: 5,
            background: 'rgba(0, 180, 255, 0.04)',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            fontSize: 14,
            fontWeight: 400,
            transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--glow-red)'
            e.currentTarget.style.color = 'var(--glow-red)'
            e.currentTarget.style.background = 'rgba(255, 59, 92, 0.1)'
            e.currentTarget.style.transform = 'scale(1.05)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)'
            e.currentTarget.style.color = 'var(--text-secondary)'
            e.currentTarget.style.background = 'rgba(0, 180, 255, 0.04)'
            e.currentTarget.style.transform = 'scale(1)'
          }}
        >
          ×
        </button>
      </div>

      {/* ── Locality, Ward & Municipal Authority Sub-header ── */}
      {locality && (
        <div
          style={{
            padding: '7px 14px',
            background: 'linear-gradient(90deg, rgba(0, 212, 255, 0.08) 0%, rgba(0, 212, 255, 0.02) 100%)',
            borderBottom: '1px solid rgba(0, 200, 255, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <MapPin size={12} color="var(--glow-cyan)" />
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)' }}>
              {locality}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span
              className="font-mono"
              style={{
                fontSize: 9,
                fontWeight: 700,
                color: 'var(--glow-cyan)',
                background: 'rgba(0, 212, 255, 0.12)',
                padding: '1px 5px',
                borderRadius: 4,
                border: '1px solid rgba(0, 212, 255, 0.25)',
                textTransform: 'uppercase',
              }}
            >
              {authority}
            </span>
            {ward && (
              <span
                className="font-mono"
                style={{
                  fontSize: 9,
                  color: 'var(--text-secondary)',
                  background: 'rgba(0, 212, 255, 0.05)',
                  padding: '1px 5px',
                  borderRadius: 4,
                  border: '1px solid rgba(0, 212, 255, 0.12)',
                }}
              >
                {ward}
              </span>
            )}
          </div>
        </div>
      )}

      {/* ── Tabs ── */}
      <div className="tab-list" style={{ flexShrink: 0, padding: '0 8px', background: 'rgba(2, 8, 20, 0.4)' }}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className="tab-trigger"
            data-state={activeTab === tab.key ? 'active' : 'inactive'}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: '9px 16px',
              fontSize: 11,
              fontWeight: activeTab === tab.key ? 700 : 500,
              letterSpacing: '0.08em',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Content ── */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0 16px 16px' }}>
        {isLoading && (
          <div
            className="font-mono text-glow"
            style={{
              padding: 30,
              textAlign: 'center',
              fontSize: 12,
              letterSpacing: '0.1em',
            }}
          >
            Loading cell data…
          </div>
        )}

        {error && (
          <div
            style={{
              padding: 20,
              fontSize: 12,
              color: 'var(--glow-red)',
              textAlign: 'center',
            }}
          >
            Failed to load cell data.
          </div>
        )}

        {bundle && !isLoading && (
          <div className="animate-fade-in" key={activeTab}>
            {activeTab === 'env'      && <EnvTab bundle={bundle} />}
            {activeTab === 'planning' && <PlanningTab bundle={bundle} />}
            {activeTab === 'raw'      && <RawTab bundle={bundle} />}
          </div>
        )}
      </div>
    </aside>
  )
}
