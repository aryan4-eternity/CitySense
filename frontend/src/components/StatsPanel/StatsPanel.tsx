// ============================================================
// StatsPanel — Left floating command-center statistics panel
// ============================================================

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
// Component
// ----------------------------------------------------------------

export function StatsPanel() {
  const { data: stats, isLoading: statsLoading } = useCityStats()
  const { data: rankings } = useRankings()
  const setSelectedCellId = useStore((s) => s.setSelectedCellId)

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
      <div style={{ padding: '14px 14px 0' }}>
        <div
          className="text-cyber"
          style={{
            fontSize: 10,
            color: 'var(--text-muted)',
            marginBottom: 10,
          }}
        >
          City Overview
        </div>

        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          <BigNumber value={totalCells} label="CELLS" color="var(--glow-cyan)" />
          <BigNumber value={avgEhi.toFixed(1)} label="AVG EHI" color="var(--glow-green)" />
          <BigNumber value={highPriorityCount} label="HIGH PRI" color="var(--glow-red)" />
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
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
      <div style={{ padding: '0 14px 14px' }}>
        <SectionTitle>Priority Cells</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {top5.map((row, i) => {
            const priorityColor = PRIORITY_COLORS[row.planning_priority] ?? 'var(--text-secondary)'
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
                  padding: '6px 8px',
                  borderRadius: 4,
                  border: 'none',
                  background:
                    i === 0 ? 'rgba(255,59,92,0.08)' : 'transparent',
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = 'var(--bg-card-hover)')
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background =
                    i === 0 ? 'rgba(255,59,92,0.08)' : 'transparent')
                }
              >
                <span
                  className="font-mono"
                  style={{
                    fontSize: 10,
                    color: 'var(--text-muted)',
                    width: 14,
                    flexShrink: 0,
                  }}
                >
                  {i + 1}.
                </span>
                <span
                  className="font-mono"
                  style={{
                    fontSize: 11,
                    color: 'var(--text-primary)',
                    flex: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {row.cell_id}
                </span>
                <span
                  className={badgeClass}
                  style={{
                    fontSize: 9,
                    padding: '1px 6px',
                    borderRadius: 3,
                    fontFamily: 'var(--font-mono)',
                    letterSpacing: '0.05em',
                    fontWeight: 600,
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
  value,
  label,
  color,
}: {
  value: string | number
  label: string
  color: string
}) {
  return (
    <div
      className="card-glow animate-flicker"
      style={{
        flex: 1,
        padding: '8px 6px',
        textAlign: 'center',
      }}
    >
      <div
        className="font-mono"
        style={{
          fontSize: 20,
          fontWeight: 700,
          color,
          textShadow: `0 0 10px ${color}55`,
          letterSpacing: '0.05em',
          lineHeight: 1.2,
        }}
      >
        {value}
      </div>
      <div
        className="font-mono"
        style={{
          fontSize: 8,
          color: 'var(--text-muted)',
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          marginTop: 2,
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
