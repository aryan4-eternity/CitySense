// ============================================================
// EnvTab — Environmental Intelligence tab within CellPanel
// ============================================================

import type { CellBundle } from '@/types'

const STATUS_BADGE: Record<string, string> = {
  Critical: 'badge-critical-ehi',
  Poor: 'badge-poor',
  Moderate: 'badge-moderate',
  Good: 'badge-good',
  Excellent: 'badge-excellent',
}

const CONDITION_ICONS: Record<string, string> = {
  'Urban Heat Island': '🔥',
  'Low Vegetation': '🌿',
  'High Built-up Density': '🏗️',
  'Flood Susceptibility': '🌊',
  'Environmental Stress': '⚠️',
  'Ecological Stability': '✅',
}

interface IndicatorDef {
  key: string
  label: string
  unit: string
  rankKey: string
  deltaKey: string
  color: string
  colorDim: string
}

const INDICATORS: IndicatorDef[] = [
  {
    key: 'mean_lst',
    label: 'LST',
    unit: '°C',
    rankKey: 'city_rank_lst',
    deltaKey: 'mean_lst_vs_city_avg',
    color: '#ff3b5c',
    colorDim: 'rgba(255,59,92,0.35)',
  },
  {
    key: 'mean_ndvi',
    label: 'NDVI',
    unit: '',
    rankKey: 'city_rank_ndvi',
    deltaKey: 'mean_ndvi_vs_city_avg',
    color: '#00ff9f',
    colorDim: 'rgba(0,255,159,0.3)',
  },
  {
    key: 'mean_ndbi',
    label: 'NDBI',
    unit: '',
    rankKey: 'city_rank_ndbi',
    deltaKey: 'mean_ndbi_vs_city_avg',
    color: '#b06bff',
    colorDim: 'rgba(176,107,255,0.3)',
  },
  {
    key: 'uhi_intensity',
    label: 'UHI',
    unit: '°C',
    rankKey: 'city_rank_uhi',
    deltaKey: 'uhi_intensity_vs_city_avg',
    color: '#ffb340',
    colorDim: 'rgba(255,179,64,0.3)',
  },
]

export function EnvTab({ bundle }: { bundle: CellBundle }) {
  const env = bundle.environment
  const master = bundle.master

  const ehi = env.environmental_health ?? 0
  const status = env.environmental_status ?? 'Unknown'
  const conditions = env.detected_conditions ?? []
  const summary = env.environmental_summary ?? ''
  const statusClass = STATUS_BADGE[status] ?? 'badge-moderate'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: '14px 0' }}>
      {/* ── EHI big number + status ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          className="font-mono animate-flicker"
          style={{
            fontSize: 36,
            fontWeight: 700,
            color: ehiColor(ehi),
            textShadow: `0 0 14px ${ehiColor(ehi)}55`,
            letterSpacing: '0.05em',
            lineHeight: 1,
          }}
        >
          {ehi.toFixed(1)}
        </div>
        <div>
          <span
            className={statusClass}
            style={{
              fontSize: 11,
              padding: '2px 10px',
              borderRadius: 4,
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
            }}
          >
            {status}
          </span>
          <div
            style={{
              fontSize: 10,
              color: 'var(--text-muted)',
              marginTop: 4,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.08em',
            }}
          >
            ENVIRONMENTAL HEALTH
          </div>
        </div>
      </div>

      {/* ── Detected Conditions ── */}
      {conditions.length > 0 && (
        <div>
          <SectionLabel>Detected Conditions</SectionLabel>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
            {conditions.map((c) => (
              <span
                key={c}
                className="card-glow"
                style={{
                  fontSize: 10,
                  padding: '3px 8px',
                  borderRadius: 4,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <span style={{ fontSize: 12 }}>{CONDITION_ICONS[c] ?? '📍'}</span>
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Indicator rows ── */}
      <div>
        <SectionLabel>Indicator Analysis</SectionLabel>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 6 }}>
          {INDICATORS.map((ind) => {
            const value = (master as any)[ind.key] as number | undefined
            const rank = (env as any)[ind.rankKey] as number | undefined
            const delta = (env as any)[ind.deltaKey] as number | undefined
            return (
              <IndicatorRow
                key={ind.key}
                ind={ind}
                value={value}
                rank={rank}
                delta={delta}
              />
            )
          })}
        </div>
      </div>

      {/* ── Environmental Summary ── */}
      {summary && (
        <div>
          <SectionLabel>Environmental Summary</SectionLabel>
          <div
            className="card-glow"
            style={{
              padding: '10px 12px',
              fontSize: 12,
              lineHeight: 1.6,
              color: 'var(--text-primary)',
              marginTop: 6,
              borderLeft: '2px solid var(--glow-cyan-dim)',
            }}
          >
            {summary}
          </div>
        </div>
      )}
    </div>
  )
}

// ----------------------------------------------------------------
// Sub-components
// ----------------------------------------------------------------

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="text-cyber"
      style={{ fontSize: 9, color: 'var(--text-muted)' }}
    >
      {children}
    </div>
  )
}

function IndicatorRow({
  ind,
  value,
  rank,
  delta,
}: {
  ind: IndicatorDef
  value?: number
  rank?: number
  delta?: number
}) {
  const pct = Math.min(100, Math.max(0, rank ?? 50))

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: 3,
        }}
      >
        <span
          className="font-mono"
          style={{ fontSize: 11, color: ind.color, fontWeight: 600 }}
        >
          {ind.label}
        </span>
        <span style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
          <span
            className="font-mono"
            style={{ fontSize: 12, color: 'var(--text-bright)', fontWeight: 600 }}
          >
            {value != null ? value.toFixed(2) : '—'}
            {ind.unit}
          </span>
          {delta != null && (
            <span
              className="font-mono"
              style={{
                fontSize: 10,
                color: delta > 0 ? 'var(--glow-red)' : 'var(--glow-green)',
              }}
            >
              {delta > 0 ? '+' : ''}
              {delta.toFixed(2)}
            </span>
          )}
        </span>
      </div>
      <div className="indicator-bar-track">
        <div
          className="indicator-bar-fill"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, ${ind.colorDim}, ${ind.color})`,
            boxShadow: `0 0 6px ${ind.colorDim}`,
          }}
        />
      </div>
      {rank != null && (
        <div
          style={{
            fontSize: 9,
            color: 'var(--text-muted)',
            marginTop: 2,
            fontFamily: 'var(--font-mono)',
          }}
        >
          {rank.toFixed(0)}th percentile
        </div>
      )}
    </div>
  )
}

function ehiColor(ehi: number): string {
  if (ehi >= 80) return '#00ff9f'
  if (ehi >= 60) return '#00d4ff'
  if (ehi >= 40) return '#ffb340'
  if (ehi >= 20) return '#ff6428'
  return '#ff3b5c'
}
