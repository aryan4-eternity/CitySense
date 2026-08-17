// ============================================================
// StatsPanel — Left floating command-center statistics panel
// ============================================================

import { useEffect, useState } from 'react'
import { useCityStats, useRankings } from '@/api/citysense'
import { useStore } from '@/store/useStore'

// ----------------------------------------------------------------
// Priority colour map
// ----------------------------------------------------------------

const PRIORITY_COLORS: Record<string, string> = {
  Critical: '#ff3b5c',
  High: '#ff6428',
  Medium: '#ffb340',
  Low: '#00ff9f',
  'Very Low': '#00d4ff',
}

const PRIORITY_ORDER = ['Critical', 'High', 'Medium', 'Low', 'Very Low']

// ----------------------------------------------------------------
// Issue icons
// ----------------------------------------------------------------

const ISSUE_ICONS: Record<string, string> = {
  'Urban Heat Island': '🔥',
  'Low Vegetation': '🌿',
  'High Built-up Density': '🏗️',
  'Flood Susceptibility': '🌊',
  'Environmental Stress': '⚠️',
  'Ecological Stability': '✅',
}

// ----------------------------------------------------------------
// Count-Up Animation Hook
// ----------------------------------------------------------------

function useAnimatedCount(target: number, durationMs = 800, decimals = 0): string {
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    let startTimestamp: number | null = null
    const startVal = 0

    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp
      const progress = Math.min((timestamp - startTimestamp) / durationMs, 1)
      const easeOut = 1 - Math.pow(1 - progress, 3) // cubic ease-out
      const current = startVal + (target - startVal) * easeOut
      setDisplay(current)
      if (progress < 1) {
        window.requestAnimationFrame(step)
      }
    }

    const animId = window.requestAnimationFrame(step)
    return () => window.cancelAnimationFrame(animId)
  }, [target, durationMs])

  return display.toFixed(decimals)
}

// ----------------------------------------------------------------
// Component
// ----------------------------------------------------------------

export function StatsPanel() {
  const { data: stats, isLoading: statsLoading } = useCityStats()
  const { data: rankings } = useRankings()
  const setSelectedCellId = useStore((s) => s.setSelectedCellId)
  const selectedCellId = useStore((s) => s.selectedCellId)

  if (statsLoading || !stats) {
    return (
      <aside
        className="panel animate-slide-left"
        style={panelStyle}
      >
        <div
          className="font-mono text-glow"
          style={{ fontSize: 12, letterSpacing: '0.1em', padding: 20, textAlign: 'center' }}
        >
          Loading statistics…
        </div>
      </aside>
    )
  }

  const totalCells = stats.total_cells
  const avgEhi = stats.avg_ehi
  const highPriorityCount =
    (stats.priority_counts?.['Critical'] ?? 0) + (stats.priority_counts?.['High'] ?? 0)

  const top5 = rankings?.slice(0, 5) ?? []

  return (
    <aside
      id="stats-panel"
      className="panel animate-slide-left"
      style={panelStyle}
    >
      {/* ── Big numbers ── */}
      <div style={{ padding: '16px 14px 0' }}>
        <div
          className="text-cyber"
          style={{
            fontSize: 9,
            color: 'var(--text-muted)',
            marginBottom: 10,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <span style={{ color: 'var(--glow-cyan)' }}>◈</span> City Overview
        </div>

        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          <BigNumber target={totalCells} label="CELLS" color="var(--glow-cyan)" decimals={0} />
          <BigNumber target={avgEhi} label="AVG EHI" color="var(--glow-green)" decimals={1} />
          <BigNumber target={highPriorityCount} label="HIGH PRI" color="var(--glow-red)" decimals={0} />
        </div>
      </div>

      <div className="divider" />

      {/* ── Priority breakdown ── */}
      <div style={{ padding: '0 14px' }}>
        <SectionTitle>Priority Distribution</SectionTitle>
        <PriorityBreakdown counts={stats.priority_counts} total={totalCells} />
      </div>

      <div className="divider" />

      {/* ── Top Issues ── */}
      <div style={{ padding: '0 14px' }}>
        <SectionTitle>Top Issues</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          {stats.top_issues.slice(0, 5).map((item) => {
            const maxCount = stats.top_issues[0]?.count ?? 1
            return (
              <IssueRow
                key={item.issue}
                issue={item.issue}
                count={item.count}
                maxCount={maxCount}
              />
            )
          })}
        </div>
      </div>

      <div className="divider" />

      {/* ── Top 5 Priority Cells ── */}
      <div style={{ padding: '0 14px 16px' }}>
        <SectionTitle>Priority Action Cells</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {top5.map((row, i) => {
            const isSelected = selectedCellId === row.cell_id
            const badgeClass = `badge-${row.planning_priority.toLowerCase().replace(/\s+/g, '')}`
            return (
              <button
                key={row.cell_id}
                type="button"
                onClick={() => setSelectedCellId(row.cell_id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '7px 10px',
                  borderRadius: 6,
                  border: isSelected
                    ? '1px solid var(--glow-cyan)'
                    : '1px solid rgba(0, 180, 255, 0.08)',
                  background: isSelected
                    ? 'rgba(0, 212, 255, 0.12)'
                    : i === 0
                      ? 'rgba(255,59,92,0.06)'
                      : 'rgba(5, 16, 35, 0.4)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                  transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                  boxShadow: isSelected ? '0 0 12px rgba(0, 212, 255, 0.2)' : 'none',
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = 'var(--bg-card-hover)'
                    e.currentTarget.style.borderColor = 'rgba(0, 212, 255, 0.25)'
                    e.currentTarget.style.transform = 'translateX(2px)'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background =
                      i === 0 ? 'rgba(255,59,92,0.06)' : 'rgba(5, 16, 35, 0.4)'
                    e.currentTarget.style.borderColor = 'rgba(0, 180, 255, 0.08)'
                    e.currentTarget.style.transform = 'translateX(0)'
                  }
                }}
              >
                <span
                  className="font-mono"
                  style={{
                    fontSize: 10,
                    color: isSelected ? 'var(--glow-cyan)' : 'var(--text-muted)',
                    width: 14,
                    flexShrink: 0,
                    fontWeight: 600,
                  }}
                >
                  {i + 1}.
                </span>
                <span
                  className="font-mono"
                  style={{
                    fontSize: 11,
                    color: isSelected ? 'var(--text-bright)' : 'var(--text-primary)',
                    flex: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    fontWeight: isSelected ? 600 : 400,
                  }}
                >
                  {row.cell_id}
                </span>
                <span
                  className={badgeClass}
                  style={{
                    fontSize: 9,
                    padding: '2px 7px',
                    borderRadius: 4,
                    fontFamily: 'var(--font-mono)',
                    letterSpacing: '0.05em',
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  {row.priority_score.toFixed(0)}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </aside>
  )
}

// ----------------------------------------------------------------
// Sub-components
// ----------------------------------------------------------------

function BigNumber({
  target,
  label,
  color,
  decimals = 0,
}: {
  target: number
  label: string
  color: string
  decimals?: number
}) {
  const animatedValue = useAnimatedCount(target, 700, decimals)

  return (
    <div
      className="card-glow"
      style={{
        flex: 1,
        padding: '10px 6px',
        textAlign: 'center',
      }}
    >
      <div
        className="font-mono"
        style={{
          fontSize: 19,
          fontWeight: 800,
          color,
          textShadow: `0 0 12px ${color}66`,
          letterSpacing: '0.04em',
          lineHeight: 1.15,
        }}
      >
        {animatedValue}
      </div>
      <div
        className="font-mono"
        style={{
          fontSize: 8,
          color: 'var(--text-muted)',
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          marginTop: 4,
          fontWeight: 600,
        }}
      >
        {label}
      </div>
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="text-cyber"
      style={{
        fontSize: 9,
        color: 'var(--text-muted)',
        marginBottom: 8,
      }}
    >
      {children}
    </div>
  )
}

function PriorityBreakdown({
  counts,
  total,
}: {
  counts: Record<string, number>
  total: number
}) {
  return (
    <div style={{ marginBottom: 4 }}>
      {/* Stacked bar */}
      <div
        style={{
          display: 'flex',
          height: 10,
          borderRadius: 5,
          overflow: 'hidden',
          background: 'rgba(0,180,255,0.06)',
          marginBottom: 6,
        }}
      >
        {PRIORITY_ORDER.map((key) => {
          const count = counts[key] ?? 0
          if (count === 0) return null
          const pct = (count / total) * 100
          return (
            <div
              key={key}
              title={`${key}: ${count}`}
              style={{
                width: `${pct}%`,
                background: PRIORITY_COLORS[key],
                opacity: 0.85,
                transition: 'width 0.6s ease',
              }}
            />
          )
        })}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 10px' }}>
        {PRIORITY_ORDER.map((key) => {
          const count = counts[key] ?? 0
          if (count === 0) return null
          return (
            <span
              key={key}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 9,
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-secondary)',
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 2,
                  background: PRIORITY_COLORS[key],
                  display: 'inline-block',
                }}
              />
              {count}
            </span>
          )
        })}
      </div>
    </div>
  )
}

function IssueRow({
  issue,
  count,
  maxCount,
}: {
  issue: string
  count: number
  maxCount: number
}) {
  const icon = ISSUE_ICONS[issue] ?? '📍'
  const pct = (count / maxCount) * 100

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 11,
      }}
    >
      <span style={{ fontSize: 13, flexShrink: 0 }}>{icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: 2,
          }}
        >
          <span
            style={{
              color: 'var(--text-primary)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              fontSize: 11,
            }}
          >
            {issue}
          </span>
          <span
            className="font-mono"
            style={{
              color: 'var(--text-secondary)',
              fontSize: 10,
              flexShrink: 0,
              marginLeft: 6,
            }}
          >
            {count}
          </span>
        </div>
        <div className="indicator-bar-track">
          <div
            className="indicator-bar-fill"
            style={{
              width: `${pct}%`,
              background: 'linear-gradient(90deg, var(--glow-cyan-dim), var(--glow-cyan))',
              boxShadow: '0 0 6px var(--glow-cyan-dim)',
            }}
          />
        </div>
      </div>
    </div>
  )
}

// ----------------------------------------------------------------
// Style constants
// ----------------------------------------------------------------

const panelStyle: React.CSSProperties = {
  position: 'fixed',
  left: 16,
  top: 64,
  bottom: 64,
  width: 260,
  zIndex: 100,
  borderRadius: 8,
  overflow: 'hidden auto',
  display: 'flex',
  flexDirection: 'column',
}
