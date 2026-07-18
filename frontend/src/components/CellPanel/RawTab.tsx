// ============================================================
// RawTab — Raw indicators + SHAP + cluster + Google Maps link
// ============================================================

import type { CellBundle } from '@/types'

const DISPLAY_KEYS: { key: string; label: string; unit: string }[] = [
  { key: 'mean_ndvi', label: 'NDVI', unit: '' },
  { key: 'mean_lst', label: 'Land Surface Temperature', unit: '°C' },
  { key: 'mean_ndbi', label: 'Built-up Density (NDBI)', unit: '' },
  { key: 'mean_dem', label: 'Elevation (DEM)', unit: 'm' },
  { key: 'uhi_intensity', label: 'UHI Intensity', unit: '°C' },
  { key: 'risk_score', label: 'Risk Score', unit: '/100' },
  { key: 'sustainability_score', label: 'Sustainability Score', unit: '/100' },
]

export function RawTab({ bundle }: { bundle: CellBundle }) {
  const master = bundle.master
  const explanation = bundle.explanation

  // Try to derive coordinates from the cell_id or geometry
  // cell_id format is typically "cell_LAT_LNG" or similar
  const cellId = master.cell_id
  const lat = 19.076 // fallback (Mumbai)
  const lng = 72.877

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: '14px 0' }}>
      {/* ── Raw Indicator Table ── */}
      <div>
        <SectionLabel>Raw Indicators</SectionLabel>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            marginTop: 6,
            fontSize: 11,
          }}
        >
          <tbody>
            {DISPLAY_KEYS.map(({ key, label, unit }) => {
              const value = (master as any)[key]
              return (
                <tr key={key}>
                  <td
                    style={{
                      padding: '4px 0',
                      color: 'var(--text-secondary)',
                      borderBottom: '1px solid rgba(0,180,255,0.06)',
                    }}
                  >
                    {label}
                  </td>
                  <td
                    className="font-mono"
                    style={{
                      padding: '4px 0',
                      textAlign: 'right',
                      color: 'var(--text-bright)',
                      fontWeight: 600,
                      borderBottom: '1px solid rgba(0,180,255,0.06)',
                    }}
                  >
                    {value != null ? Number(value).toFixed(3) : '—'}
                    <span
                      style={{
                        fontSize: 9,
                        color: 'var(--text-muted)',
                        marginLeft: 2,
                      }}
                    >
                      {unit}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* ── Cluster Label ── */}
      <div>
        <SectionLabel>Urban Typology</SectionLabel>
        <div
          className="card-glow font-mono"
          style={{
            marginTop: 6,
            padding: '8px 12px',
            fontSize: 12,
            color: 'var(--glow-cyan)',
            textShadow: '0 0 6px var(--glow-cyan-dim)',
          }}
        >
          {master.cluster ?? '—'}
          {master.cluster_id != null && (
            <span
              style={{
                fontSize: 10,
                color: 'var(--text-muted)',
                marginLeft: 8,
              }}
            >
              (ID: {master.cluster_id})
            </span>
          )}
        </div>
      </div>

      {/* ── SHAP Explanation ── */}
      {(master.explanation_text || explanation?.explanation_text) && (
        <div>
          <SectionLabel>SHAP Explanation</SectionLabel>
          <div
            style={{
              fontSize: 11,
              lineHeight: 1.6,
              color: 'var(--text-primary)',
              marginTop: 6,
              padding: '10px 12px',
              borderLeft: '2px solid var(--glow-amber)',
              background: 'rgba(255,179,64,0.04)',
              borderRadius: '0 4px 4px 0',
            }}
          >
            {master.explanation_text || explanation?.explanation_text}
          </div>

          {/* Top drivers */}
          <div
            style={{
              display: 'flex',
              gap: 10,
              marginTop: 8,
              fontSize: 10,
              fontFamily: 'var(--font-mono)',
            }}
          >
            {master.top_positive_driver && (
              <div style={{ flex: 1 }}>
                <span style={{ color: 'var(--glow-red)' }}>▲</span>{' '}
                <span style={{ color: 'var(--text-secondary)' }}>
                  {master.top_positive_driver}
                </span>
                <span
                  style={{
                    color: 'var(--glow-red)',
                    marginLeft: 4,
                    fontWeight: 600,
                  }}
                >
                  +{master.top_positive_shap?.toFixed(3)}
                </span>
              </div>
            )}
            {master.top_negative_driver && (
              <div style={{ flex: 1 }}>
                <span style={{ color: 'var(--glow-green)' }}>▼</span>{' '}
                <span style={{ color: 'var(--text-secondary)' }}>
                  {master.top_negative_driver}
                </span>
                <span
                  style={{
                    color: 'var(--glow-green)',
                    marginLeft: 4,
                    fontWeight: 600,
                  }}
                >
                  {master.top_negative_shap?.toFixed(3)}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Google Maps Link ── */}
      <div>
        <a
          href={`https://www.google.com/maps/@${lat},${lng},15z`}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 11,
            color: 'var(--glow-cyan)',
            textDecoration: 'none',
            fontFamily: 'var(--font-mono)',
            padding: '6px 10px',
            border: '1px solid var(--border)',
            borderRadius: 4,
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.borderColor = 'var(--glow-cyan)')
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.borderColor = 'var(--border)')
          }
        >
          📍 View on Google Maps
        </a>
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
