// ============================================================
// PlanningTab — Planning Intelligence tab within CellPanel
// ============================================================

import { Target, Sparkles, CheckCircle2, Clock, DollarSign, Sliders, ShieldCheck } from 'lucide-react'
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
      <div
        className="card-glow"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 14px',
          background: 'linear-gradient(135deg, rgba(8,24,52,0.6), rgba(4,14,32,0.8))',
        }}
      >
        <div>
          <span
            className={`${badgeClass} ${animClass}`}
            style={{
              fontSize: 11,
              padding: '3px 10px',
              borderRadius: 4,
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
            }}
          >
            {priority}
          </span>
          <div
            style={{
              fontSize: 9,
              color: 'var(--text-muted)',
              marginTop: 4,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.08em',
              fontWeight: 600,
            }}
          >
            PLANNING PRIORITY
          </div>
        </div>
        <div
          className="font-mono"
          style={{
            fontSize: 24,
            fontWeight: 800,
            color: 'var(--text-bright)',
            letterSpacing: '0.04em',
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
            fontSize: 12,
            color: 'var(--text-primary)',
            marginTop: 6,
            fontWeight: 500,
            display: 'flex',
            alignItems: 'flex-start',
            gap: 8,
            padding: '8px 10px',
            borderRadius: 6,
            background: 'rgba(0, 180, 255, 0.04)',
            border: '1px solid rgba(0, 180, 255, 0.1)',
          }}
        >
          <Target size={15} color="var(--glow-cyan)" style={{ flexShrink: 0, marginTop: 1 }} />
          <span>{objective}</span>
        </div>
      </div>

      {/* ── Recommended Intervention ── */}
      <div>
        <SectionLabel>Recommended Intervention</SectionLabel>
        <div
          className="card-glow"
          style={{
            fontSize: 14,
            fontWeight: 700,
            color: 'var(--glow-cyan)',
            textShadow: '0 0 10px var(--glow-cyan-dim)',
            marginTop: 6,
            padding: '10px 12px',
            borderLeft: '3px solid var(--glow-cyan)',
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
                style={{
                  fontSize: 10,
                  padding: '4px 8px',
                  borderRadius: 5,
                  color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-mono)',
                  background: 'rgba(0, 180, 255, 0.04)',
                  border: '1px solid rgba(0, 180, 255, 0.1)',
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
            {benefits.map((b) => (
              <div
                key={b}
                style={{
                  fontSize: 11,
                  color: 'var(--text-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '4px 8px',
                  borderRadius: 4,
                  background: 'rgba(0, 255, 159, 0.03)',
                  border: '1px solid rgba(0, 255, 159, 0.1)',
                }}
              >
                <CheckCircle2 size={13} color="var(--glow-green)" style={{ flexShrink: 0 }} />
                <span>{b}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Implementation Details (chips) ── */}
      <div>
        <SectionLabel>Implementation Details</SectionLabel>
        <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
          <Chip label="Cost" value={cost} icon={<DollarSign size={12} color="var(--glow-amber)" />} />
          <Chip label="Timeline" value={timeline} icon={<Clock size={12} color="var(--glow-cyan)" />} />
          <Chip label="Complexity" value={complexity} icon={<Sliders size={12} color="var(--glow-purple)" />} />
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

function Chip({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div
      className="card-glow"
      style={{
        flex: 1,
        textAlign: 'center',
        padding: '8px 4px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      {icon && <div style={{ marginBottom: 3 }}>{icon}</div>}
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
