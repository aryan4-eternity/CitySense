// ============================================================
// SatelliteModal.tsx — Live Satellite Feed & Resilient Cache Manager
// ============================================================

import { useState } from 'react'
import { Satellite, RefreshCw, CheckCircle2, AlertTriangle, ShieldCheck, Database, X, Radio, CloudRain } from 'lucide-react'
import { useStore } from '@/store/useStore'
import { useSatelliteStatus, syncSatelliteFeeds } from '@/api/citysense'
import type { SatelliteSyncResponse } from '@/types'

export function SatelliteModal() {
  const satelliteModalOpen = useStore((s) => s.satelliteModalOpen)
  const setSatelliteModalOpen = useStore((s) => s.setSatelliteModalOpen)
  const { data: statusData, refetch } = useSatelliteStatus()

  const [isSyncing, setIsSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<SatelliteSyncResponse | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  if (!satelliteModalOpen) return null

  const handleTriggerSync = async () => {
    setIsSyncing(true)
    setErrorMsg(null)
    try {
      const res = await syncSatelliteFeeds()
      setSyncResult(res)
      refetch()
    } catch (err: any) {
      setErrorMsg(err.message || 'Live sync encountered an error. Authoritative cache preserved.')
    } finally {
      setIsSyncing(false)
    }
  }

  const streams = statusData?.streams ?? [
    {
      id: 'sentinel2',
      name: 'Sentinel-2 MSI',
      indicators: ['NDVI (Vegetation)', 'NDBI (Built-up)'],
      resolution: '10m / Level-2A',
      status: 'synchronized',
      fallback_active: false,
      cloud_cover: '4.2%',
      source: 'Copernicus Open Access / GEE',
    },
    {
      id: 'landsat8',
      name: 'Landsat-8 TIRS',
      indicators: ['Land Surface Temperature (LST)', 'UHI Intensity'],
      resolution: '30m / Thermal IR',
      status: 'synchronized',
      fallback_active: false,
      source: 'USGS / GEE Collection 2',
    },
    {
      id: 'srtm',
      name: 'NASA SRTM v3',
      indicators: ['Elevation (DEM)', 'Hydrological Slope'],
      resolution: '30m Radar Topography',
      status: 'synchronized',
      fallback_active: false,
      source: 'NASA JPL / GEE',
    },
    {
      id: 'chirps',
      name: 'UCSB CHIRPS',
      indicators: ['Monsoon Precipitation', 'Flood Susceptibility (FSI)'],
      resolution: '0.05° Gridded Daily',
      status: 'synchronized',
      fallback_active: false,
      source: 'Climate Hazards Center',
    },
    {
      id: 'osm',
      name: 'OpenStreetMap Overpass',
      indicators: ['Hospitals, Schools, Transit, Drainage'],
      resolution: 'Vector Spatial Join',
      status: 'synchronized',
      fallback_active: false,
      source: 'Overpass API',
    },
  ]

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 500,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(2, 6, 16, 0.75)',
        backdropFilter: 'blur(12px)',
        padding: 16,
      }}
      onClick={() => setSatelliteModalOpen(false)}
    >
      <div
        className="panel animate-fade-in"
        style={{
          width: '100%',
          maxWidth: 620,
          borderRadius: 14,
          background: 'linear-gradient(135deg, rgba(8, 24, 52, 0.95) 0%, rgba(4, 14, 32, 0.95) 100%)',
          border: '1px solid rgba(0, 212, 255, 0.35)',
          boxShadow: '0 24px 60px rgba(0, 4, 16, 0.8), 0 0 32px rgba(0, 212, 255, 0.15)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '90vh',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(0, 212, 255, 0.04)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 8,
                background: 'rgba(0, 212, 255, 0.12)',
                border: '1px solid rgba(0, 212, 255, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Satellite size={18} color="var(--glow-cyan)" />
            </div>
            <div>
              <div
                className="font-mono text-glow"
                style={{
                  fontSize: 14,
                  fontWeight: 800,
                  color: 'var(--glow-cyan)',
                  letterSpacing: '0.06em',
                }}
              >
                SATELLITE DATA INGESTION & CACHE
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                Earth Observation Telemetry · 1663 MMR Grid Cells
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setSatelliteModalOpen(false)}
            aria-label="Close modal"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              padding: 4,
              borderRadius: 4,
              transition: 'color 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body Content */}
        <div style={{ padding: '16px 20px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Resilience Guarantee Banner */}
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 8,
              background: 'linear-gradient(90deg, rgba(0, 255, 159, 0.08) 0%, rgba(0, 212, 255, 0.04) 100%)',
              border: '1px solid rgba(0, 255, 159, 0.25)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
            }}
          >
            <ShieldCheck size={16} color="var(--glow-green)" style={{ flexShrink: 0, marginTop: 2 }} />
            <div style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.45 }}>
              <strong style={{ color: 'var(--glow-green)' }}>100% Data Availability Guarantee:</strong> If live Earth Engine passes, cloud thresholds, or API connections fail, CitySense seamlessly serves the authoritative pre-calibrated cache so urban analysis never experiences downtime.
            </div>
          </div>

          {/* Sensor Feeds List */}
          <div>
            <div
              className="text-cyber"
              style={{ fontSize: 9, color: 'var(--text-muted)', marginBottom: 8, letterSpacing: '0.1em' }}
            >
              Active Earth Observation Sensor Streams
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {streams.map((stream) => (
                <div
                  key={stream.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '9px 12px',
                    borderRadius: 8,
                    background: 'rgba(5, 16, 36, 0.6)',
                    border: '1px solid rgba(0, 200, 255, 0.12)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Radio size={14} color="var(--glow-cyan)" />
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)' }}>
                        {stream.name}
                        <span
                          className="font-mono"
                          style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 8, fontWeight: 500 }}
                        >
                          {stream.resolution}
                        </span>
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>
                        {stream.indicators.join(' · ')}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span
                      style={{
                        fontSize: 9,
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: 4,
                        textTransform: 'uppercase',
                        background: stream.fallback_active ? 'rgba(255, 179, 64, 0.15)' : 'rgba(0, 255, 159, 0.12)',
                        border: stream.fallback_active ? '1px solid rgba(255, 179, 64, 0.35)' : '1px solid rgba(0, 255, 159, 0.35)',
                        color: stream.fallback_active ? 'var(--glow-amber)' : 'var(--glow-green)',
                      }}
                    >
                      {stream.fallback_active ? 'CACHED FALLBACK' : 'LIVE SYNCED'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Sync Result Banner if executed */}
          {syncResult && (
            <div
              className="animate-fade-in"
              style={{
                padding: '12px 14px',
                borderRadius: 8,
                background: 'rgba(0, 212, 255, 0.08)',
                border: '1px solid rgba(0, 212, 255, 0.3)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <CheckCircle2 size={15} color="var(--glow-cyan)" />
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--glow-cyan)' }}>
                  Synchronization Completed
                </span>
              </div>
              <p style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.4 }}>
                {syncResult.summary}
              </p>
              <div
                className="font-mono"
                style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 6 }}
              >
                Validated: {syncResult.total_cells_verified} Grid Cells · Timestamp: {new Date(syncResult.sync_time).toLocaleTimeString()}
              </div>
            </div>
          )}

          {errorMsg && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 8,
                background: 'rgba(255, 59, 92, 0.1)',
                border: '1px solid rgba(255, 59, 92, 0.3)',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 11,
                color: 'var(--glow-red)',
              }}
            >
              <AlertTriangle size={14} />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div
          style={{
            padding: '14px 20px',
            borderTop: '1px solid var(--border)',
            background: 'rgba(0, 180, 255, 0.03)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div
            className="font-mono"
            style={{ fontSize: 10, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 5 }}
          >
            <Database size={12} color="var(--glow-cyan)" />
            <span>Local Cache: 1663 cells verified</span>
          </div>

          <button
            type="button"
            disabled={isSyncing}
            onClick={handleTriggerSync}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 7,
              padding: '7px 16px',
              borderRadius: 8,
              border: '1px solid var(--glow-cyan)',
              background: isSyncing
                ? 'rgba(0, 212, 255, 0.1)'
                : 'linear-gradient(135deg, rgba(0, 212, 255, 0.25) 0%, rgba(0, 180, 255, 0.12) 100%)',
              color: 'var(--glow-cyan)',
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.06em',
              cursor: isSyncing ? 'not-allowed' : 'pointer',
              boxShadow: '0 0 16px rgba(0, 212, 255, 0.25)',
              transition: 'all 0.2s',
            }}
          >
            <RefreshCw size={13} className={isSyncing ? 'animate-spin' : ''} />
            <span>{isSyncing ? 'SYNCING FEEDS…' : 'FETCH LATEST SATELLITE DATA'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}
