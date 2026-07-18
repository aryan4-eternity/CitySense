// ============================================================
// Header — Top bar with project title, live clock, status
// ============================================================

import { useEffect, useState } from 'react'
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
        height: 48,
        zIndex: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px',
        borderBottom: '1px solid var(--border)',
        boxShadow: '0 2px 16px rgba(0, 180, 255, 0.06)',
      }}
    >
      {/* Left — Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <span
          className="font-mono text-glow"
          style={{
            fontSize: 16,
            fontWeight: 700,
            letterSpacing: '0.12em',
            color: 'var(--glow-cyan)',
          }}
        >
          🌆 CITYSENSE
        </span>
        <span
          className="font-mono"
          style={{
            fontSize: 10,
            letterSpacing: '0.15em',
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            opacity: 0.8,
          }}
        >
          MUMBAI ENVIRONMENTAL INTELLIGENCE
        </span>
      </div>

      {/* Centre — Clock */}
      <div
        className="font-mono"
        style={{
          fontSize: 15,
          letterSpacing: '0.18em',
          color: 'var(--text-primary)',
          textShadow: '0 0 6px rgba(0, 212, 255, 0.3)',
          position: 'absolute',
          left: '50%',
          transform: 'translateX(-50%)',
        }}
      >
        {clock}{' '}
        <span
          style={{
            fontSize: 9,
            color: 'var(--text-muted)',
            letterSpacing: '0.1em',
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
          gap: 18,
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
        }}
      >
        {/* Connection */}
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            className={apiConnected ? 'animate-dot-blink' : ''}
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: apiConnected ? '#00ff9f' : '#ff3b5c',
              boxShadow: apiConnected
                ? '0 0 8px rgba(0,255,159,0.6)'
                : '0 0 8px rgba(255,59,92,0.6)',
              display: 'inline-block',
            }}
          />
          <span style={{ color: apiConnected ? 'var(--glow-green)' : 'var(--glow-red)' }}>
            {apiConnected ? 'LIVE' : 'OFFLINE'}
          </span>
        </span>

        {/* Cell count */}
        <span style={{ color: 'var(--text-secondary)' }}>
          <span style={{ color: 'var(--text-bright)', fontWeight: 600 }}>
            {cellCount}
          </span>{' '}
          CELLS
        </span>

        {/* Phase */}
        <span
          style={{
            color: 'var(--glow-cyan)',
            textShadow: '0 0 6px rgba(0, 212, 255, 0.3)',
          }}
        >
          PHASE 3
        </span>
      </div>
    </header>
  )
}
