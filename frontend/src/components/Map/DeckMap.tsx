// ============================================================
// DeckMap — Full-screen WebGL choropleth + hotspot + cluster labels
// ============================================================

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import DeckGL from '@deck.gl/react'
import type { MapViewState } from '@deck.gl/core'
import { Map as MapLibreMap } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

import { useStore } from '@/store/useStore'
import { useCells } from '@/api/citysense'
import type { TooltipInfo } from '@/types'
import {
  makeChoroplethLayer,
  makeHotspotLayer,
  makeClusterLabelLayer,
} from './layers'

// ----------------------------------------------------------------
// Constants
// ----------------------------------------------------------------

const INITIAL_VIEW: MapViewState = {
  longitude: 72.877,
  latitude: 19.076,
  zoom: 11,
  pitch: 30,
  bearing: -10,
  minZoom: 9,
  maxZoom: 17,
}

const MAP_STYLE =
  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

// ----------------------------------------------------------------
// useAnimationFrame hook — returns a 0–1 value oscillating every N ms
// ----------------------------------------------------------------

function useAnimationFrame(periodMs = 2000) {
  const [time, setTime] = useState(0)
  const frameRef = useRef<number>(0)

  useEffect(() => {
    let start = performance.now()
    const tick = (now: number) => {
      const elapsed = (now - start) % periodMs
      setTime(elapsed / periodMs)
      frameRef.current = requestAnimationFrame(tick)
    }
    frameRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frameRef.current)
  }, [periodMs])

  return time
}

// ----------------------------------------------------------------
// Hotspot extractor — top-10 cells by risk_score
// ----------------------------------------------------------------

function extractHotspots(geojson: GeoJSON.FeatureCollection) {
  const features = [...geojson.features]
    .filter(
      (f) =>
        f.properties &&
        typeof f.properties.risk_score === 'number' &&
        f.geometry.type === 'Polygon',
    )
    .sort(
      (a, b) => (b.properties!.risk_score as number) - (a.properties!.risk_score as number),
    )
    .slice(0, 10)

  return features.map((f) => {
    // Compute centroid of polygon
    const coords = (f.geometry as GeoJSON.Polygon).coordinates[0]
    const n = coords.length
    const lng = coords.reduce((s, c) => s + c[0], 0) / n
    const lat = coords.reduce((s, c) => s + c[1], 0) / n
    return {
      position: [lng, lat] as [number, number],
      radius: 200 + ((f.properties!.risk_score as number) / 100) * 200,
    }
  })
}

// ----------------------------------------------------------------
// Cluster centroid extractor
// ----------------------------------------------------------------

function extractClusterCentroids(geojson: GeoJSON.FeatureCollection) {
  const buckets: Record<string, { lngs: number[]; lats: number[]; label: string }> = {}
  for (const f of geojson.features) {
    const p = f.properties
    if (!p || !p.cluster || f.geometry.type !== 'Polygon') continue
    const key = String(p.cluster_id ?? p.cluster)
    if (!buckets[key]) buckets[key] = { lngs: [], lats: [], label: String(p.cluster) }
    const coords = (f.geometry as GeoJSON.Polygon).coordinates[0]
    const n = coords.length
    buckets[key].lngs.push(coords.reduce((s, c) => s + c[0], 0) / n)
    buckets[key].lats.push(coords.reduce((s, c) => s + c[1], 0) / n)
  }

  return Object.values(buckets).map((b) => ({
    position: [
      b.lngs.reduce((s, v) => s + v, 0) / b.lngs.length,
      b.lats.reduce((s, v) => s + v, 0) / b.lats.length,
    ] as [number, number],
    label: b.label,
  }))
}

// ----------------------------------------------------------------
// Component
// ----------------------------------------------------------------

export function DeckMap() {
  const { data: geojson, isLoading } = useCells()
  const activeLayer = useStore((s) => s.activeLayer)
  const selectedCellId = useStore((s) => s.selectedCellId)
  const setSelectedCellId = useStore((s) => s.setSelectedCellId)
  const setTooltip = useStore((s) => s.setTooltip)
  const animTime = useAnimationFrame(2000)

  // Derived data
  const hotspots = useMemo(
    () => (geojson ? extractHotspots(geojson) : []),
    [geojson],
  )

  const clusterCentroids = useMemo(
    () => (geojson ? extractClusterCentroids(geojson) : []),
    [geojson],
  )

  // Tooltip state (local — only coordinates, not global store)
  const [localTooltip, setLocalTooltip] = useState<TooltipInfo | null>(null)

  const onHover = useCallback(
    (info: { object?: GeoJSON.Feature; x: number; y: number }) => {
      if (info.object) {
        const props = info.object.properties as Record<string, unknown>
        const tip: TooltipInfo = {
          x: info.x,
          y: info.y,
          cellId: (props.cell_id as string) ?? '',
          ehi: (props.environmental_health as number) ?? null,
          priorityLabel: (props.planning_priority as string) ?? null,
          lst: (props.mean_lst as number) ?? null,
          cluster: (props.cluster as string) ?? null,
        }
        setLocalTooltip(tip)
        setTooltip(tip)
      } else {
        setLocalTooltip(null)
        setTooltip(null)
      }
    },
    [setTooltip],
  )

  const onClick = useCallback(
    (info: { object?: GeoJSON.Feature }) => {
      if (info.object) {
        const cellId = (info.object.properties as Record<string, unknown>)
          .cell_id as string
        setSelectedCellId(cellId ?? null)
      }
    },
    [setSelectedCellId],
  )

  // Build layers
  const layers = useMemo(() => {
    if (!geojson) return []
    const result = [
      makeChoroplethLayer(geojson, activeLayer, selectedCellId, onHover, onClick),
      makeHotspotLayer(hotspots, animTime),
    ]
    if (activeLayer === 'cluster') {
      result.push(makeClusterLabelLayer(clusterCentroids) as any)
    }
    return result
  }, [geojson, activeLayer, selectedCellId, hotspots, animTime, clusterCentroids, onHover, onClick])

  return (
    <div id="deck-map-container" style={{ position: 'absolute', inset: 0, zIndex: 0 }}>
      <DeckGL
        initialViewState={INITIAL_VIEW}
        controller={true}
        layers={layers}
        getCursor={({ isHovering }: { isHovering: boolean }) =>
          isHovering ? 'pointer' : 'grab'
        }
      >
        <MapLibreMap mapStyle={MAP_STYLE} />
      </DeckGL>

      {/* Loading overlay */}
      {isLoading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(5,13,26,0.85)',
            zIndex: 50,
          }}
        >
          <div
            className="font-mono text-glow"
            style={{
              fontSize: 14,
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              color: 'var(--glow-cyan)',
            }}
          >
            Loading cell grid…
          </div>
        </div>
      )}

      {/* Tooltip */}
      {localTooltip && (
        <div
          className="deck-tooltip animate-fade-in"
          style={{
            position: 'absolute',
            left: localTooltip.x + 12,
            top: localTooltip.y - 8,
            zIndex: 60,
            maxWidth: 220,
          }}
        >
          <div
            style={{
              fontSize: 11,
              color: 'var(--glow-cyan)',
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.08em',
              marginBottom: 4,
            }}
          >
            {localTooltip.cellId}
          </div>
          {localTooltip.ehi !== null && (
            <div style={{ fontSize: 12, marginBottom: 2 }}>
              EHI:{' '}
              <span style={{ color: 'var(--text-bright)', fontWeight: 600 }}>
                {localTooltip.ehi.toFixed(1)}
              </span>
            </div>
          )}
          {localTooltip.priorityLabel && (
            <div style={{ fontSize: 12, marginBottom: 2 }}>
              Priority:{' '}
              <span style={{ fontWeight: 600 }}>{localTooltip.priorityLabel}</span>
            </div>
          )}
          {localTooltip.lst !== null && (
            <div style={{ fontSize: 12 }}>
              LST:{' '}
              <span style={{ fontWeight: 600 }}>{localTooltip.lst.toFixed(1)}°C</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
