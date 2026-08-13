// ============================================================
// CellMiniMap — Embedded map showing the selected cell boundary
// on real map tiles with a glowing cyan polygon highlight.
// ============================================================

import { useMemo } from 'react'
import DeckGL from '@deck.gl/react'
import type { MapViewState } from '@deck.gl/core'
import { GeoJsonLayer } from '@deck.gl/layers'
import { Map as MapLibreMap } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

const MAP_STYLE =
  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

// ----------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------

/** Compute the centroid of a polygon from its coordinate ring. */
function polygonCentroid(coords: number[][]): [number, number] {
  const n = coords.length
  const lng = coords.reduce((s, c) => s + c[0], 0) / n
  const lat = coords.reduce((s, c) => s + c[1], 0) / n
  return [lng, lat]
}

/** Build a GeoJSON FeatureCollection from a single polygon geometry. */
function toFeatureCollection(
  geometry: GeoJSON.Polygon,
): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: [{ type: 'Feature', properties: {}, geometry }],
  }
}

// ----------------------------------------------------------------
// Props
// ----------------------------------------------------------------

interface CellMiniMapProps {
  geometry: GeoJSON.Polygon
  cellId: string
  /** EHI 0–100 used to tint the fill colour */
  ehi?: number | null
}

// ----------------------------------------------------------------
// Component
// ----------------------------------------------------------------

export function CellMiniMap({ geometry, cellId, ehi }: CellMiniMapProps) {
  const coords = geometry.coordinates[0]
  const [lng, lat] = polygonCentroid(coords)

  const viewState: MapViewState = {
    longitude: lng,
    latitude:  lat,
    zoom:      14,
    pitch:     0,
    bearing:   0,
  }

  // Fill colour: interpolate red→green based on EHI
  const fillColor: [number, number, number, number] = useMemo(() => {
    if (ehi == null) return [0, 212, 255, 40]
    const t = Math.max(0, Math.min(1, ehi / 100))
    const r = Math.round(255 * (1 - t))
    const g = Math.round(255 * t)
    return [r, g, 60, 50]
  }, [ehi])

  const geojson = useMemo(() => toFeatureCollection(geometry), [geometry])

  const layer = new GeoJsonLayer({
    id:       'cell-highlight',
    data:     geojson,
    pickable: false,
    stroked:  true,
    filled:   true,
    getFillColor:        fillColor,
    getLineColor:        [0, 212, 255, 230] as [number, number, number, number],
    lineWidthMinPixels:  3,
    lineWidthMaxPixels:  3,
  })

  // Google Maps link using centroid
  const gmapsUrl = `https://www.google.com/maps/search/?api=1&query=${lat.toFixed(5)},${lng.toFixed(5)}`
  // OpenStreetMap link
  const osmUrl   = `https://www.openstreetmap.org/?mlat=${lat.toFixed(5)}&mlon=${lng.toFixed(5)}#map=16/${lat.toFixed(5)}/${lng.toFixed(5)}`

  return (
    <div style={{ marginTop: 12, marginBottom: 4 }}>
      {/* Map container */}
      <div
        style={{
          position: 'relative',
          height: 180,
          borderRadius: 6,
          overflow: 'hidden',
          border: '1px solid var(--border)',
          boxShadow: '0 0 12px rgba(0,212,255,0.1)',
        }}
      >
        <DeckGL
          initialViewState={viewState}
          controller={true}
          layers={[layer]}
          style={{ position: 'absolute', inset: 0 as unknown as string }}
        >
          <MapLibreMap mapStyle={MAP_STYLE} />
        </DeckGL>

        {/* Cell ID badge overlay */}
        <div
          style={{
            position: 'absolute',
            top: 6,
            left: 8,
            background: 'rgba(5,16,35,0.85)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            padding: '2px 7px',
            fontSize: 10,
            fontFamily: 'var(--font-mono)',
            color: 'var(--glow-cyan)',
            letterSpacing: '0.06em',
            pointerEvents: 'none',
          }}
        >
          {cellId}
        </div>

        {/* Zoom hint */}
        <div
          style={{
            position: 'absolute',
            bottom: 6,
            right: 8,
            fontSize: 9,
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            pointerEvents: 'none',
          }}
        >
          scroll to zoom · drag to pan
        </div>
      </div>

      {/* External links */}
      <div
        style={{
          display: 'flex',
          gap: 8,
          marginTop: 6,
          fontSize: 10,
          fontFamily: 'var(--font-mono)',
        }}
      >
        <a
          href={gmapsUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            color: 'var(--glow-cyan)',
            textDecoration: 'none',
            padding: '3px 8px',
            border: '1px solid var(--border)',
            borderRadius: 4,
            transition: 'border-color 0.2s',
            letterSpacing: '0.05em',
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.borderColor = 'var(--glow-cyan)')
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.borderColor = 'var(--border)')
          }
        >
          🗺️ Google Maps
        </a>
        <a
          href={osmUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            color: 'var(--text-secondary)',
            textDecoration: 'none',
            padding: '3px 8px',
            border: '1px solid var(--border)',
            borderRadius: 4,
            transition: 'border-color 0.2s',
            letterSpacing: '0.05em',
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.borderColor = 'var(--text-secondary)')
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.borderColor = 'var(--border)')
          }
        >
          🌐 OpenStreetMap
        </a>
        <span
          style={{
            marginLeft: 'auto',
            color: 'var(--text-muted)',
            fontSize: 9,
            alignSelf: 'center',
          }}
        >
          {lat.toFixed(4)}°N, {lng.toFixed(4)}°E
        </span>
      </div>
    </div>
  )
}
