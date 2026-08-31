// ============================================================
// Header — Top bar with project title, live clock, status
// ============================================================

import { useEffect, useState } from 'react'
import { Activity, BarChart3, ShieldCheck, Wifi, WifiOff, Satellite } from 'lucide-react'
import { useStore } from '@/store/useStore'
import { checkHealth, useCityStats } from '@/api/citysense'
import { SearchBar } from './SearchBar'
import { RegionSelector } from './RegionSelector'

export function Header() {
  const apiConnected = useStore((s) => s.apiConnected)
  const setApiConnected = useStore((s) => s.setApiConnected)
  const statsPanelOpen = useStore((s) => s.statsPanelOpen)
  const setStatsPanelOpen = useStore((s) => s.setStatsPanelOpen)
  const setSatelliteModalOpen = useStore((s) => s.setSatelliteModalOpen)
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
    const timer = setInterval(update, 1000)
    return () => clearInterval(timer)
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

  const cellCount = stats?.total_cells ?? 1663

  return (
    <header
      id="header-bar"
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
        padding: '0 18px',
        borderBottom: '1px solid var(--border)',
        background: 'rgba(2, 6, 16, 0.88)',
        backdropFilter: 'blur(16px)',
        boxShadow: '0 4px 24px rgba(0, 4, 16, 0.6)',
      }}
    >
      {/* Left — Logo + Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background: 'linear-gradient(135deg, rgba(0, 212, 255, 0.25) 0%, rgba(0, 180, 255, 0.08) 100%)',
              border: '1px solid var(--glow-cyan)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 12px var(--glow-cyan-dim)',
            }}
          >
            <Activity size={16} color="var(--glow-cyan)" />
          </div>
          <span
            className="font-mono text-glow"
            style={{
              fontSize: 16,
              fontWeight: 900,
              letterSpacing: '0.12em',
              color: 'var(--glow-cyan)',
            }}
          >
            CITYSENSE
          </span>
        </div>

        <div className="header-subtitle" style={{ display: 'flex', flexDirection: 'column' }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: '0.04em',
              color: 'var(--text-primary)',
            }}
          >
            MMR Environmental Intelligence
          </span>
          <span
            className="font-mono"
            style={{
              fontSize: 9,
              letterSpacing: '0.06em',
              color: 'var(--text-muted)',
            }}
          >
            {cellCount} MMR Grid Cells • 1 km² Resolution
          </span>
        </div>
      </div>

      {/* Centre — Region Selector, Search & Clock */}
      <div
        style={{
          position: 'absolute',
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <RegionSelector />
        <SearchBar />

        <div
          className="header-clock font-mono"
          style={{
            fontSize: 12,
            letterSpacing: '0.14em',
            color: 'var(--text-primary)',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            borderRadius: 16,
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
              fontSize: 8,
              color: 'var(--text-muted)',
              letterSpacing: '0.12em',
              fontWeight: 500,
            }}
          >
            IST
          </span>
        </div>
      </div>

      {/* Right — Status */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
        }}
      >
        {/* Discreet Satellite Ingestion & Cache Telemetry Button */}
        <button
          type="button"
          onClick={() => setSatelliteModalOpen(true)}
          title="Inspect Live Satellite Streams & Cached Fallback Telemetry"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '3px 10px',
            borderRadius: 16,
            background: 'rgba(0, 212, 255, 0.08)',
            border: '1px solid rgba(0, 212, 255, 0.3)',
            color: 'var(--glow-cyan)',
            cursor: 'pointer',
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: '0.06em',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(0, 212, 255, 0.18)'
            e.currentTarget.style.boxShadow = '0 0 12px rgba(0, 212, 255, 0.3)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(0, 212, 255, 0.08)'
            e.currentTarget.style.boxShadow = 'none'
          }}
        >
          <Satellite size={12} color="var(--glow-cyan)" />
          <span>FEEDS: SYNC</span>
        </button>

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
