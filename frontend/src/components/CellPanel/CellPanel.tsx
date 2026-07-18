// ============================================================
// CellPanel — Right floating detail panel with tabs
// ============================================================

import { useState } from 'react'
import { useStore } from '@/store/useStore'
import { useCell } from '@/api/citysense'
import { EnvTab } from './EnvTab'
import { PlanningTab } from './PlanningTab'
import { RawTab } from './RawTab'

type TabKey = 'env' | 'planning' | 'raw'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'env', label: 'Environment' },
  { key: 'planning', label: 'Planning' },
  { key: 'raw', label: 'Raw Data' },
]

const PRIORITY_BADGE: Record<string, string> = {
  Critical: 'badge-critical',
  High: 'badge-high',
  Medium: 'badge-medium',
  Low: 'badge-low',
  'Very Low': 'badge-verylow',
}

export function CellPanel() {
  const selectedCellId = useStore((s) => s.selectedCellId)
  const setSelectedCellId = useStore((s) => s.setSelectedCellId)
  const { data: bundle, isLoading, error } = useCell(selectedCellId)
  const [activeTab, setActiveTab] = useState<TabKey>('env')

  if (!selectedCellId) return null

  return (
    <aside
      id="cell-panel"
      className="panel animate-slide-right"
      style={{
        position: 'fixed',
        right: 16,
        top: 64,
        bottom: 64,
        width: 340,
        zIndex: 100,
        borderRadius: 8,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          padding: '12px 14px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            className="font-mono"
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: 'var(--glow-cyan)',
              letterSpacing: '0.06em',
              textShadow: '0 0 8px var(--glow-cyan-dim)',
            }}
          >
            {selectedCellId}
          </span>
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
                padding: '1px 6px',
                borderRadius: 3,
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
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
                padding: '1px 6px',
                borderRadius: 3,
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
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
            borderRadius: 4,
            background: 'transparent',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            fontSize: 14,
            fontWeight: 300,
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--glow-red)'
            e.currentTarget.style.color = 'var(--glow-red)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)'
            e.currentTarget.style.color = 'var(--text-secondary)'
          }}
        >
          ×
        </button>
      </div>

      {/* ── Tabs ── */}
      <div className="tab-list" style={{ flexShrink: 0 }}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className="tab-trigger"
            data-state={activeTab === tab.key ? 'active' : 'inactive'}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Content ── */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0 14px' }}>
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
          <div className="animate-fade-in">
            {activeTab === 'env' && <EnvTab bundle={bundle} />}
            {activeTab === 'planning' && <PlanningTab bundle={bundle} />}
            {activeTab === 'raw' && <RawTab bundle={bundle} />}
          </div>
        )}
      </div>
    </aside>
  )
}
