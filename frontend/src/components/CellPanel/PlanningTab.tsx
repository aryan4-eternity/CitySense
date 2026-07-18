// ============================================================
// PlanningTab — Planning Intelligence tab within CellPanel
// ============================================================

import type { CellBundle } from '@/types'

const PRIORITY_BADGE: Record<string, string> = {
  Critical: 'badge-critical',
  High: 'badge-high',
  Medium: 'badge-medium',
  Low: 'badge-low',
  'Very Low': 'badge-verylow',
}

const PRIORITY_ANIM: Record<string, string> = {
  Critical: 'animate-pulse-red',
  High: 'animate-pulse-red',
}

export function PlanningTab({ bundle }: { bundle: CellBundle }) {
  const plan = bundle.planning

  const priority = plan.planning_priority ?? 'Unknown'
  const score = plan.priority_score ?? 0
  const objective = plan.primary_objective ?? '—'
  const intervention = plan.recommended_intervention ?? '—'
  const secondary = plan.secondary_interventions ?? []
  const benefits = plan.expected_benefits ?? []
  const cost = plan.implementation_cost ?? '—'
  const timeline = plan.implementation_timeline ?? '—'
  const complexity = plan.implementation_complexity ?? '—'
  const evidence = plan.evidence ?? ''
  const confidence = plan.confidence ?? 0

  const badgeClass = PRIORITY_BADGE[priority] ?? 'badge-medium'
  const animClass = PRIORITY_ANIM[priority] ?? ''

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: '14px 0' }}>
      {/* ── Priority Badge + Score ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          className={`${badgeClass} ${animClass}`}
          style={{
            fontSize: 13,
            padding: '4px 14px',
            borderRadius: 5,
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
          }}
        >
          {priority}
        </div>
        <div
          className="font-mono"
          style={{
            fontSize: 22,
            fontWeight: 700,
            color: 'var(--text-bright)',
            letterSpacing: '0.05em',
          }}
        >
          {score.toFixed(1)}
          <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 3 }}>
            /100
          </span>
        </div>
      </div>

      {/* ── Primary Objective ── */}
      <div>
        <SectionLabel>Primary Objective</SectionLabel>
        <div
          style={{
            fontSize: 13,
            color: 'var(--text-primary)',
            marginTop: 4,
            fontWeight: 500,
          }}
        >
          🎯 {objective}
        </div>
      </div>

      {/* ── Recommended Intervention ── */}
      <div>
        <SectionLabel>Recommended Intervention</SectionLabel>
        <div
          style={{
            fontSize: 16,
            fontWeight: 700,
            color: 'var(--glow-cyan)',
            textShadow: '0 0 8px var(--glow-cyan-dim)',
            marginTop: 4,
            borderBottom: '2px solid var(--glow-cyan-dim)',
            paddingBottom: 4,
            display: 'inline-block',
          }}
        >
          {intervention}
        </div>
      </div>

      {/* ── Secondary Interventions ── */}
      {secondary.length > 0 && (
        <div>
          <SectionLabel>Secondary Interventions</SectionLabel>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
            {secondary.map((s) => (
              <span
                key={s}
                className="card"
                style={{
                  fontSize: 10,
                  padding: '3px 8px',
                  borderRadius: 4,
                  color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Expected Benefits ── */}
      {benefits.length > 0 && (
        <div>
          <SectionLabel>Expected Benefits</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
            {benefits.map((b) => (
              <div
                key={b}
                style={{
                  fontSize: 11,
                  color: 'var(--text-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <span style={{ color: 'var(--glow-green)', fontSize: 13 }}>✓</span>
                {b}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Implementation Details (chips) ── */}
      <div>
        <SectionLabel>Implementation Details</SectionLabel>
        <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
          <Chip label="Cost" value={cost} />
          <Chip label="Timeline" value={timeline} />
          <Chip label="Complexity" value={complexity} />
        </div>
      </div>

      {/* ── Evidence ── */}
      {evidence && (
        <div>
          <SectionLabel>Why this recommendation?</SectionLabel>
          <div
            style={{
              fontSize: 11,
              lineHeight: 1.65,
              color: 'var(--text-primary)',
              marginTop: 6,
              padding: '10px 12px',
              borderLeft: '3px solid var(--glow-cyan)',
              background: 'rgba(0,180,255,0.04)',
              borderRadius: '0 4px 4px 0',
            }}
          >
            {evidence}
          </div>
        </div>
      )}

      {/* ── Confidence Gauge ── */}
      <div>
        <SectionLabel>Confidence</SectionLabel>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            marginTop: 6,
          }}
        >
          <ConfidenceGauge value={confidence} />
          <div>
            <div
              className="font-mono"
              style={{
                fontSize: 20,
                fontWeight: 700,
                color: 'var(--text-bright)',
              }}
            >
              {(confidence * 100).toFixed(0)}%
            </div>
            <div
              style={{
                fontSize: 9,
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.08em',
              }}
            >
              RECOMMENDATION CONFIDENCE
            </div>
          </div>
        </div>
      </div>
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

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="card-glow"
      style={{
        flex: 1,
        textAlign: 'center',
        padding: '6px 4px',
      }}
    >
      <div
        className="font-mono"
        style={{ fontSize: 11, color: 'var(--text-bright)', fontWeight: 600 }}
      >
        {value}
      </div>
      <div
        style={{
          fontSize: 8,
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          marginTop: 2,
        }}
      >
        {label}
      </div>
    </div>
  )
}

function ConfidenceGauge({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value))
  const radius = 28
  const stroke = 4
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference * (1 - pct)

  // Color based on confidence
  const color =
    pct >= 0.8
      ? 'var(--glow-green)'
      : pct >= 0.5
        ? 'var(--glow-cyan)'
        : 'var(--glow-amber)'

  return (
    <svg
      width={72}
      height={72}
      viewBox="0 0 72 72"
      style={{ flexShrink: 0 }}
    >
      {/* Background ring */}
      <circle
        cx={36}
        cy={36}
        r={radius}
        fill="none"
        stroke="rgba(0,180,255,0.1)"
        strokeWidth={stroke}
      />
      {/* Filled arc */}
      <circle
        cx={36}
        cy={36}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={dashOffset}
        transform="rotate(-90 36 36)"
        style={{
          transition: 'stroke-dashoffset 1s ease',
          filter: `drop-shadow(0 0 4px ${color})`,
        }}
      />
    </svg>
  )
}
