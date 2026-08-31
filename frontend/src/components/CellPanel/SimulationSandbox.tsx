// ============================================================
// SimulationSandbox.tsx — Real-Time 'What-If' Policy & Intervention Simulator
// Deterministic microclimate & EHI recalculation engine
// ============================================================

import { useState, useMemo } from 'react'
import { Sliders, RotateCcw, Trees, Sparkles, TrendingUp, Sun, Droplets, ShieldAlert, ArrowRight } from 'lucide-react'
import type { CellBundle } from '@/types'

interface SimulationSandboxProps {
  bundle: CellBundle
}

export function SimulationSandbox({ bundle }: SimulationSandboxProps) {
  const master = bundle.master
  const env = bundle.environment

  // Baseline values
  const baseLst = typeof master.mean_lst === 'number' ? master.mean_lst : 37.0
  const baseNdvi = typeof master.mean_ndvi === 'number' ? master.mean_ndvi : 0.18
  const baseUhi = typeof master.uhi_intensity === 'number' ? master.uhi_intensity : 3.0
  const baseNdbi = typeof master.mean_ndbi === 'number' ? master.mean_ndbi : 0.05
  const baseDem = typeof master.mean_dem === 'number' ? master.mean_dem : 15.0
  const baseEhi = env.environmental_health ?? 50.0

  // Simulation Sliders State
  const [deltaNdvi, setDeltaNdvi] = useState<number>(0.0) // 0 to +0.30 (Tree Canopy)
  const [deltaLstCoolRoof, setDeltaLstCoolRoof] = useState<number>(0.0) // 0 to -5.0°C (Cool Roofs)
  const [deltaNdbi, setDeltaNdbi] = useState<number>(0.0) // 0 to -0.20 (Permeable Paving)

  const isSimulated = deltaNdvi > 0 || deltaLstCoolRoof < 0 || deltaNdbi < 0

  // Recalculate microclimate & EHI deterministically
  const simResult = useMemo(() => {
    // Evapotranspiration cooling from tree canopy
    const lstDropCanopy = -3.8 * deltaNdvi
    const uhiDropCanopy = -3.8 * deltaNdvi

    // Permeable paving cooling contribution
    const lstDropPaving = 2.2 * deltaNdbi // deltaNdbi is negative, so this drops LST

    // Simulated raw values
    const simLst = Math.max(28, Math.min(50, baseLst + deltaLstCoolRoof + lstDropCanopy + lstDropPaving))
    const simNdvi = Math.max(-0.15, Math.min(0.70, baseNdvi + deltaNdvi))
    const simUhi = Math.max(-6, Math.min(10, baseUhi + deltaLstCoolRoof + uhiDropCanopy))
    const simNdbi = Math.max(-0.30, Math.min(0.40, baseNdbi + deltaNdbi))
    const simDem = baseDem

    // Normalized components [0, 1] where 1 = worst risk
    const normLst = Math.max(0, Math.min(1, (simLst - 28) / (48 - 28)))
    const normNdvi = Math.max(0, Math.min(1, 1 - (simNdvi - (-0.15)) / (0.65 - (-0.15))))
    const normUhi = Math.max(0, Math.min(1, (simUhi - (-6)) / (8 - (-6))))
    const normNdbi = Math.max(0, Math.min(1, (simNdbi - (-0.25)) / (0.35 - (-0.25))))
    const normDem = Math.max(0, Math.min(1, 1 - simDem / 100))

    // Weighted composite using authoritative EHI weights (LST: 0.30, NDVI: 0.25, UHI: 0.20, NDBI: 0.15, DEM: 0.10)
    const compositeRisk =
      0.30 * normLst +
      0.25 * normNdvi +
      0.20 * normUhi +
      0.15 * normNdbi +
      0.10 * normDem

    const simEhi = Math.max(0, Math.min(100, (1 - compositeRisk) * 100))
    const ehiGain = simEhi - baseEhi
    const netCooling = baseLst - simLst

    const getStatus = (score: number) => {
      if (score >= 75) return { label: 'Excellent', color: 'var(--glow-green)' }
      if (score >= 60) return { label: 'Good', color: '#00ff9f' }
      if (score >= 45) return { label: 'Moderate', color: 'var(--glow-amber)' }
      if (score >= 30) return { label: 'Poor', color: '#ff8c38' }
      return { label: 'Critical', color: 'var(--glow-red)' }
    }

    return {
      simEhi,
      ehiGain,
      netCooling,
      baseStatus: getStatus(baseEhi),
      simStatus: getStatus(simEhi),
      simLst,
      simNdvi,
      simUhi,
    }
  }, [baseLst, baseNdvi, baseUhi, baseNdbi, baseDem, baseEhi, deltaNdvi, deltaLstCoolRoof, deltaNdbi])

  const handleReset = () => {
    setDeltaNdvi(0.0)
    setDeltaLstCoolRoof(0.0)
    setDeltaNdbi(0.0)
  }

  const applyPreset = (type: 'greening' | 'coolroof' | 'sponge') => {
    if (type === 'greening') {
      setDeltaNdvi(0.20)
      setDeltaLstCoolRoof(-1.0)
      setDeltaNdbi(-0.05)
    } else if (type === 'coolroof') {
      setDeltaNdvi(0.05)
      setDeltaLstCoolRoof(-4.0)
      setDeltaNdbi(0.0)
    } else if (type === 'sponge') {
      setDeltaNdvi(0.18)
      setDeltaLstCoolRoof(-3.0)
      setDeltaNdbi(-0.15)
    }
  }

  return (
    <div
      style={{
        borderRadius: 10,
        background: 'rgba(5, 16, 38, 0.7)',
        border: '1px solid rgba(0, 212, 255, 0.25)',
        padding: '14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <Sliders size={15} color="var(--glow-cyan)" />
          <span
            className="text-cyber"
            style={{ fontSize: 11, color: 'var(--glow-cyan)', letterSpacing: '0.08em' }}
          >
            'WHAT-IF' POLICY IMPACT SIMULATOR
          </span>
        </div>

        {isSimulated && (
          <button
            type="button"
            onClick={handleReset}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '2px 8px',
              borderRadius: 4,
              background: 'rgba(255, 59, 92, 0.1)',
              border: '1px solid rgba(255, 59, 92, 0.3)',
              color: 'var(--glow-red)',
              fontSize: 10,
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
            }}
          >
            <RotateCcw size={11} />
            <span>RESET</span>
          </button>
        )}
      </div>

      {/* Live Projection Scorecard */}
      <div
        style={{
          padding: '10px 12px',
          borderRadius: 8,
          background: isSimulated
            ? 'linear-gradient(135deg, rgba(0, 212, 255, 0.12) 0%, rgba(0, 255, 159, 0.08) 100%)'
            : 'rgba(0, 180, 255, 0.05)',
          border: isSimulated
            ? '1px solid var(--glow-cyan)'
            : '1px solid rgba(0, 200, 255, 0.12)',
          boxShadow: isSimulated ? '0 0 16px rgba(0, 212, 255, 0.15)' : 'none',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          transition: 'all 0.3s ease',
        }}
      >
        {/* Top Row: EHI Projection + Delta Pill */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              HEALTH INDEX PROJECTION
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 2 }}>
              <span
                className="font-mono"
                style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-secondary)' }}
              >
                {baseEhi.toFixed(1)}
              </span>
              <ArrowRight size={13} color="var(--glow-cyan)" />
              <span
                className="font-mono animate-flicker"
                style={{
                  fontSize: 22,
                  fontWeight: 800,
                  color: simResult.simStatus.color,
                  textShadow: `0 0 12px ${simResult.simStatus.color}66`,
                }}
              >
                {simResult.simEhi.toFixed(1)}
              </span>
            </div>
          </div>

          {simResult.ehiGain > 0 ? (
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                fontFamily: 'var(--font-mono)',
                color: 'var(--glow-green)',
                background: 'rgba(0, 255, 159, 0.12)',
                padding: '3px 8px',
                borderRadius: 4,
                border: '1px solid rgba(0, 255, 159, 0.35)',
              }}
            >
              +{simResult.ehiGain.toFixed(1)} pts
            </span>
          ) : (
            <span
              style={{
                fontSize: 9,
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-muted)',
                background: 'rgba(0, 180, 255, 0.05)',
                padding: '2px 6px',
                borderRadius: 4,
              }}
            >
              Baseline
            </span>
          )}
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: 'rgba(0, 200, 255, 0.1)', width: '100%' }} />

        {/* Bottom Row: Status Transition & Thermal Relief */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>STATUS:</span>
            <span
              style={{
                fontSize: 10,
                color: simResult.baseStatus.color,
                fontWeight: 700,
                fontFamily: 'var(--font-mono)',
              }}
            >
              {simResult.baseStatus.label}
            </span>
            <span style={{ color: 'var(--text-muted)', fontSize: 9 }}>➔</span>
            <span
              style={{
                fontSize: 11,
                color: simResult.simStatus.color,
                fontWeight: 800,
                fontFamily: 'var(--font-mono)',
                textTransform: 'uppercase',
              }}
            >
              {simResult.simStatus.label}
            </span>
          </div>

          {simResult.netCooling > 0 && (
            <div
              className="font-mono"
              style={{
                fontSize: 10,
                color: 'var(--glow-cyan)',
                fontWeight: 600,
                background: 'rgba(0, 212, 255, 0.08)',
                padding: '1px 6px',
                borderRadius: 4,
              }}
            >
              ❄️ -{simResult.netCooling.toFixed(1)}°C Relief
            </div>
          )}
        </div>
      </div>

      {/* Preset Action Buttons in 3-column grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 5 }}>
        <button
          type="button"
          onClick={() => applyPreset('greening')}
          style={{
            padding: '5px 4px',
            borderRadius: 6,
            background: 'rgba(0, 255, 159, 0.08)',
            border: '1px solid rgba(0, 255, 159, 0.25)',
            color: 'var(--glow-green)',
            fontSize: 9,
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            cursor: 'pointer',
            textAlign: 'center',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          🌿 +Canopy
        </button>

        <button
          type="button"
          onClick={() => applyPreset('coolroof')}
          style={{
            padding: '5px 4px',
            borderRadius: 6,
            background: 'rgba(0, 212, 255, 0.08)',
            border: '1px solid rgba(0, 212, 255, 0.25)',
            color: 'var(--glow-cyan)',
            fontSize: 9,
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            cursor: 'pointer',
            textAlign: 'center',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          ⚪ Cool Roof
        </button>

        <button
          type="button"
          onClick={() => applyPreset('sponge')}
          style={{
            padding: '5px 4px',
            borderRadius: 6,
            background: 'rgba(176, 107, 255, 0.08)',
            border: '1px solid rgba(176, 107, 255, 0.25)',
            color: '#c48eff',
            fontSize: 9,
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            cursor: 'pointer',
            textAlign: 'center',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          🏙️ Sponge City
        </button>
      </div>

      {/* Policy Sliders */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Slider 1: Urban Tree Canopy */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
            <span style={{ color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 5 }}>
              <Trees size={13} color="var(--glow-green)" />
              Urban Afforestation / Miyawaki Greenery
            </span>
            <span className="font-mono" style={{ color: 'var(--glow-green)', fontWeight: 700 }}>
              +{deltaNdvi.toFixed(2)} NDVI
            </span>
          </div>
          <input
            type="range"
            min="0.0"
            max="0.30"
            step="0.02"
            value={deltaNdvi}
            onChange={(e) => setDeltaNdvi(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--glow-green)', cursor: 'pointer' }}
          />
        </div>

        {/* Slider 2: Cool Roof Coatings */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
            <span style={{ color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 5 }}>
              <Sun size={13} color="var(--glow-cyan)" />
              Cool Roof Reflective Coatings & White Tops
            </span>
            <span className="font-mono" style={{ color: 'var(--glow-cyan)', fontWeight: 700 }}>
              {deltaLstCoolRoof.toFixed(1)}°C LST
            </span>
          </div>
          <input
            type="range"
            min="-5.0"
            max="0.0"
            step="0.5"
            value={deltaLstCoolRoof}
            onChange={(e) => setDeltaLstCoolRoof(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--glow-cyan)', cursor: 'pointer' }}
          />
        </div>

        {/* Slider 3: Permeable Paving */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
            <span style={{ color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 5 }}>
              <Droplets size={13} color="#c48eff" />
              Permeable Paving & Bioswale Drainage
            </span>
            <span className="font-mono" style={{ color: '#c48eff', fontWeight: 700 }}>
              {deltaNdbi.toFixed(2)} NDBI
            </span>
          </div>
          <input
            type="range"
            min="-0.20"
            max="0.0"
            step="0.02"
            value={deltaNdbi}
            onChange={(e) => setDeltaNdbi(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: '#b06bff', cursor: 'pointer' }}
          />
        </div>
      </div>
    </div>
  )
}
