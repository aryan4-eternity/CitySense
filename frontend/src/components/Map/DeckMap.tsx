// ============================================================
// DeckMap — Full-screen WebGL choropleth + hotspot + cluster labels
// ============================================================

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import DeckGL from '@deck.gl/react'
import type { MapViewState, Layer } from '@deck.gl/core'
import { Map as MapLibreMap } from 'react-map-gl/maplibre'
import { Box } from 'lucide-react'
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
    let startTimestamp = performance.now()
    const tick = (now: number) => {
      const elapsed = (now - startTimestamp) % periodMs
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
    // Vertex-average centroid: acceptable here because CitySense grid cells are
    // near-square with evenly spaced vertices (5 pts including closing repeat).
    // Do not reuse this helper for irregular or non-convex polygons.
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
    // Vertex-average centroid per cell, then average of cell centroids per cluster.
    // Acceptable because grid cells are near-square — see extractHotspots comment.
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
  const is3D = useStore((s) => s.is3D)
  const setIs3D = useStore((s) => s.setIs3D)
  const animTime = useAnimationFrame(2000)

  const [viewState, setViewState] = useState<MapViewState>(INITIAL_VIEW)

  // Fly to selected cell when selectedCellId changes
  useEffect(() => {
    if (!selectedCellId || !geojson) return
    const feature = geojson.features.find(
      (f) => f.properties && f.properties.cell_id === selectedCellId,
    )
    if (feature && feature.geometry.type === 'Polygon') {
      const coords = feature.geometry.coordinates[0]
      const n = coords.length
      const lng = coords.reduce((s, c) => s + c[0], 0) / n
      const lat = coords.reduce((s, c) => s + c[1], 0) / n
      setViewState((prev) => ({
        ...prev,
        longitude: lng,
        latitude: lat,
        zoom: 13,
        transitionDuration: 1200,
      }))
    }
  }, [selectedCellId, geojson])

  const handleToggle3D = () => {
    const next = !is3D
    setIs3D(next)
    setViewState((prev) => ({
      ...prev,
      pitch: next ? 55 : 20,
      bearing: next ? -15 : 0,
      transitionDuration: 800,
    }))
  }

  // Derived data
  const hotspots = useMemo(
    () => (geojson ? extractHotspots(geojson) : []),
    [geojson],
  )

  const clusterCentroids = useMemo(
    () => (geojson ? extractClusterCentroids(geojson) : []),
    [geojson],
  )

  // Tooltip is local to this component — nothing outside DeckMap reads hover state.
  const [localTooltip, setLocalTooltip] = useState<TooltipInfo | null>(null)

  const onHover = useCallback(
    (info: { object?: GeoJSON.Feature; x: number; y: number }) => {
      if (info.object) {
        const props = info.object.properties as Record<string, unknown>
        setLocalTooltip({
          x: info.x,
          y: info.y,
          cellId: (props.cell_id as string) ?? '',
          ehi: (props.environmental_health as number) ?? null,
          priorityLabel: (props.planning_priority as string) ?? null,
          lst: (props.mean_lst as number) ?? null,
          cluster: (props.cluster as string) ?? null,
        })
      } else {
        setLocalTooltip(null)
      }
    },
    [],
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

  // Build layers — typed as Layer[] to avoid as-any casts
  const layers = useMemo((): Layer[] => {
    if (!geojson) return []
    const result: Layer[] = [
      makeChoroplethLayer(geojson, activeLayer, selectedCellId, is3D, onHover, onClick),
      makeHotspotLayer(hotspots, animTime),
    ]
    if (activeLayer === 'cluster') {
      result.push(makeClusterLabelLayer(clusterCentroids))
    }
    return result
  }, [geojson, activeLayer, selectedCellId, is3D, hotspots, animTime, clusterCentroids, onHover, onClick])

  return (
    <div id="deck-map-container" style={{ position: 'absolute', inset: 0, zIndex: 0 }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState }) => setViewState(viewState as unknown as MapViewState)}
        controller={true}
        layers={layers}
        getCursor={({ isHovering }: { isHovering: boolean }) =>
          isHovering ? 'pointer' : 'grab'
        }
      >
        <MapLibreMap mapStyle={MAP_STYLE} />
      </DeckGL>

      {/* 3D Extrusion Mode Floating Control */}
      <div
        style={{
          position: 'fixed',
          top: 64,
          right: 20,
          zIndex: 105,
          display: 'flex',
          gap: 4,
          padding: '3px 4px',
          borderRadius: 8,
          background: 'rgba(4, 14, 32, 0.88)',
          border: '1px solid rgba(0, 200, 255, 0.25)',
          boxShadow: '0 8px 32px rgba(0, 4, 16, 0.6), 0 0 16px rgba(0, 212, 255, 0.08)',
          backdropFilter: 'blur(16px)',
        }}
      >
        <button
          type="button"
          onClick={handleToggle3D}
          title={is3D ? 'Switch to 2D flat view' : 'Switch to 3D extruded severity columns'}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '5px 11px',
            borderRadius: 6,
            border: is3D ? '1px solid var(--glow-cyan)' : '1px solid transparent',
            background: is3D ? 'rgba(0, 212, 255, 0.18)' : 'transparent',
            color: is3D ? 'var(--glow-cyan)' : 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.08em',
            cursor: 'pointer',
            boxShadow: is3D ? '0 0 12px rgba(0, 212, 255, 0.25)' : 'none',
            transition: 'all 0.2s',
          }}
        >
          <Box size={14} color={is3D ? 'var(--glow-cyan)' : 'var(--text-muted)'} />
          <span>{is3D ? '3D EXTRUDED' : '2D VIEW'}</span>
        </button>
      </div>

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
