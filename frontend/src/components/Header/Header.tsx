// ============================================================
// Header — Top bar with project title, live clock, status
// ============================================================

import { useEffect, useState } from 'react'
import { Activity, ShieldCheck, Wifi, WifiOff } from 'lucide-react'
import { useStore } from '@/store/useStore'
import { checkHealth, useCityStats } from '@/api/citysense'

export function Header() {
  const apiConnected = useStore((s) => s.apiConnected)
  const setApiConnected = useStore((s) => s.setApiConnected)
  const { data: stats } = useCityStats()

  // Live clock (IST)
  const [clock, setClock] = useState('')
  useEffect(() => {
    const update = () => {
      const now = new Date()
      setClock(
        now.toLocaleTimeString('en-IN', {
          timeZone: 'Asia/Kolkata',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        }),
      )
    }
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [])

  // Health check polling
  useEffect(() => {
    const poll = async () => {
      const ok = await checkHealth()
      setApiConnected(ok)
    }
    poll()
    const id = setInterval(poll, 15000)
    return () => clearInterval(id)
  }, [setApiConnected])

  const cellCount = stats?.total_cells ?? '—'

  return (
    <header
      id="header-bar"
      className="panel"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: 52,
        zIndex: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        borderBottom: '1px solid var(--border)',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.45), 0 1px 0 rgba(0, 212, 255, 0.15)',
        backdropFilter: 'blur(20px) saturate(1.6)',
      }}
    >
      {/* Left — Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '5px 12px',
            borderRadius: 6,
            background: 'linear-gradient(135deg, rgba(0, 212, 255, 0.12), rgba(0, 180, 255, 0.04))',
            border: '1px solid rgba(0, 212, 255, 0.3)',
            boxShadow: 'inset 0 0 12px rgba(0, 212, 255, 0.08)',
          }}
        >
          <Activity size={17} color="var(--glow-cyan)" />
          <span
            className="font-mono text-glow"
            style={{
              fontSize: 15,
              fontWeight: 800,
              letterSpacing: '0.12em',
              color: 'var(--glow-cyan)',
            }}
          >
            CITYSENSE
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: '0.04em',
              color: 'var(--text-primary)',
            }}
          >
            Mumbai Environmental Intelligence
          </span>
          <span
            className="font-mono"
            style={{
              fontSize: 9,
              letterSpacing: '0.06em',
              color: 'var(--text-muted)',
            }}
          >
            836 Grid Cells • 1 km² Resolution
          </span>
        </div>
      </div>

      {/* Centre — Clock */}
      <div
        className="font-mono"
        style={{
          fontSize: 13,
          letterSpacing: '0.18em',
          color: 'var(--text-primary)',
          position: 'absolute',
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '4px 14px',
          borderRadius: 20,
          background: 'rgba(0, 180, 255, 0.04)',
          border: '1px solid rgba(0, 180, 255, 0.15)',
          boxShadow: '0 0 12px rgba(0, 212, 255, 0.04)',
        }}
      >
        <span style={{ color: 'var(--glow-cyan)', textShadow: '0 0 8px var(--glow-cyan-dim)', fontWeight: 600 }}>
          {clock}
        </span>
        <span
          style={{
            fontSize: 9,
            color: 'var(--text-muted)',
            letterSpacing: '0.12em',
            fontWeight: 500,
          }}
        >
          IST
        </span>
      </div>

      {/* Right — Status */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
        }}
      >
        {/* Connection pill */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            padding: '3px 10px',
            borderRadius: 16,
            background: apiConnected ? 'rgba(0, 255, 159, 0.08)' : 'rgba(255, 59, 92, 0.08)',
            border: apiConnected ? '1px solid rgba(0, 255, 159, 0.3)' : '1px solid rgba(255, 59, 92, 0.3)',
          }}
        >
          <span
            className={apiConnected ? 'animate-dot-blink' : ''}
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: apiConnected ? '#00ff9f' : '#ff3b5c',
              boxShadow: apiConnected
                ? '0 0 10px rgba(0,255,159,0.8)'
                : '0 0 10px rgba(255,59,92,0.8)',
              display: 'inline-block',
            }}
          />
          <span style={{ color: apiConnected ? 'var(--glow-green)' : 'var(--glow-red)', fontWeight: 600 }}>
            {apiConnected ? 'ONLINE' : 'OFFLINE'}
          </span>
        </div>

        {/* Cell count pill */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '3px 10px',
            borderRadius: 16,
            background: 'rgba(0, 180, 255, 0.05)',
            border: '1px solid rgba(0, 180, 255, 0.18)',
            color: 'var(--text-secondary)',
          }}
        >
          <span style={{ color: 'var(--glow-cyan)', fontWeight: 700 }}>
            {cellCount}
          </span>
          <span>CELLS</span>
        </div>
      </div>
    </header>
  )
}
