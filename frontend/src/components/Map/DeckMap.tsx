// ============================================================
// DeckMap — Full-screen WebGL choropleth + hotspot + cluster labels
// Supports Basemap Switcher (Satellite, Dark, Streets, Light)
// ============================================================

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import DeckGL from '@deck.gl/react'
import type { MapViewState, Layer } from '@deck.gl/core'
import { Map as MapLibreMap } from 'react-map-gl/maplibre'
import { Box } from 'lucide-react'
import 'maplibre-gl/dist/maplibre-gl.css'

import { useStore } from '@/store/useStore'
import { useCells } from '@/api/citysense'
import type { TooltipInfo, BasemapKey } from '@/types'
import { MMR_REGIONS } from '@/components/Header/RegionSelector'
import {
  makeChoroplethLayer,
  makeHotspotLayer,
  makeClusterLabelLayer,
  makeRegionBoundaryLayer,
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

// ----------------------------------------------------------------
// Basemap Configurations
// ----------------------------------------------------------------

export const BASEMAP_CONFIGS: Record<
  BasemapKey,
  {
    name: string
    shortLabel: string
    icon: string
    description: string
    style: any
  }
> = {
  satellite: {
    name: 'Satellite Hybrid',
    shortLabel: 'Satellite',
    icon: '🛰️',
    description: 'High-resolution photographic aerial imagery with road & boundary labels',
    style: {
      version: 8,
      sources: {
        'esri-imagery': {
          type: 'raster',
          tiles: [
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          ],
          tileSize: 256,
          attribution: 'Esri, Maxar, Earthstar Geographics',
          maxzoom: 19,
        },
        'esri-boundaries': {
          type: 'raster',
          tiles: [
            'https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
          ],
          tileSize: 256,
          maxzoom: 19,
        },
      },
      layers: [
        {
          id: 'esri-imagery-layer',
          type: 'raster',
          source: 'esri-imagery',
          minzoom: 0,
          maxzoom: 20,
        },
        {
          id: 'esri-boundaries-layer',
          type: 'raster',
          source: 'esri-boundaries',
          minzoom: 0,
          maxzoom: 20,
        },
      ],
    },
  },
  dark: {
    name: 'Cyber Dark',
    shortLabel: 'Dark',
    icon: '🌑',
    description: 'High-contrast minimalist dark vector map',
    style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  },
  streets: {
    name: 'Urban Streets',
    shortLabel: 'Streets',
    icon: '🗺️',
    description: 'Detailed street network, transport lines, and landmark typography',
    style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
  },
  light: {
    name: 'Clean Light',
    shortLabel: 'Light',
    icon: '⚪',
    description: 'Minimalist paper-white light cartography',
    style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  },
}

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
  const selectedRegion = useStore((s) => s.selectedRegion)
  const is3D = useStore((s) => s.is3D)
  const setIs3D = useStore((s) => s.setIs3D)
  const basemapStyle = useStore((s) => s.basemapStyle)
  const setBasemapStyle = useStore((s) => s.setBasemapStyle)
  const animTime = useAnimationFrame(2000)

  const [viewState, setViewState] = useState<MapViewState>(INITIAL_VIEW)

  // Fly to active MMR Region when selectedRegion changes
  useEffect(() => {
    if (!selectedRegion) return
    const regionConfig = MMR_REGIONS.find((r) => r.key === selectedRegion)
    if (regionConfig) {
      setViewState((prev) => ({
        ...prev,
        longitude: regionConfig.center[0],
        latitude: regionConfig.center[1],
        zoom: regionConfig.zoom,
        pitch: is3D ? 55 : (regionConfig.pitch ?? 0),
        bearing: is3D ? -15 : (regionConfig.bearing ?? 0),
        transitionDuration: 1300,
      }))
    }
  }, [selectedRegion, is3D])

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

  const handleResetView = () => {
    setSelectedCellId(null)
    setViewState((prev) => ({
      ...prev,
      longitude: INITIAL_VIEW.longitude,
      latitude: INITIAL_VIEW.latitude,
      zoom: INITIAL_VIEW.zoom,
      pitch: is3D ? 55 : INITIAL_VIEW.pitch,
      bearing: is3D ? -15 : INITIAL_VIEW.bearing,
      transitionDuration: 1000,
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
      makeChoroplethLayer(geojson, activeLayer, selectedCellId, selectedRegion, is3D, onHover, onClick),
      makeHotspotLayer(hotspots, animTime),
    ]

    // Render illuminated pure white boundary around the active selected region
    const boundaryLayer = makeRegionBoundaryLayer(selectedRegion, is3D)
    if (boundaryLayer) {
      result.push(boundaryLayer)
    }

    if (activeLayer === 'cluster') {
      result.push(makeClusterLabelLayer(clusterCentroids))
    }
    return result
  }, [geojson, activeLayer, selectedCellId, selectedRegion, is3D, hotspots, animTime, clusterCentroids, onHover, onClick])

  const activeBasemapConfig = BASEMAP_CONFIGS[basemapStyle] ?? BASEMAP_CONFIGS.satellite

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
        <MapLibreMap key={basemapStyle} mapStyle={activeBasemapConfig.style} />
      </DeckGL>

      {/* Map Floating Control Toolbar (Top Right) */}
      <div
        id="map-controls-toolbar"
        style={{
          position: 'fixed',
          top: 64,
          right: selectedCellId ? 382 : 20,
          zIndex: 105,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '4px 6px',
          borderRadius: 10,
          background: 'rgba(4, 14, 32, 0.88)',
          border: '1px solid rgba(0, 200, 255, 0.25)',
          boxShadow: '0 8px 32px rgba(0, 4, 16, 0.6), 0 0 16px rgba(0, 212, 255, 0.08)',
          backdropFilter: 'blur(16px)',
          transition: 'right 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Basemap Switcher Options */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
          {(['satellite', 'dark', 'streets', 'light'] as BasemapKey[]).map((key) => {
            const config = BASEMAP_CONFIGS[key]
            const isCurrent = basemapStyle === key
            return (
              <button
                key={key}
                type="button"
                onClick={() => setBasemapStyle(key)}
                title={config.description}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '4px 8px',
                  borderRadius: 6,
                  border: isCurrent
                    ? '1px solid var(--glow-cyan)'
                    : '1px solid transparent',
                  background: isCurrent
                    ? 'rgba(0, 212, 255, 0.18)'
                    : 'transparent',
                  color: isCurrent ? 'var(--glow-cyan)' : 'var(--text-secondary)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  fontWeight: isCurrent ? 700 : 500,
                  letterSpacing: '0.04em',
                  cursor: 'pointer',
                  boxShadow: isCurrent ? '0 0 10px rgba(0, 212, 255, 0.2)' : 'none',
                  transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                }}
                onMouseEnter={(e) => {
                  if (!isCurrent) {
                    e.currentTarget.style.background = 'rgba(0, 212, 255, 0.08)'
                    e.currentTarget.style.color = 'var(--text-primary)'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isCurrent) {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = 'var(--text-secondary)'
                  }
                }}
              >
                <span style={{ fontSize: 11 }}>{config.icon}</span>
                <span>{config.shortLabel}</span>
              </button>
            )
          })}
        </div>

        <div
          style={{
            width: 1,
            height: 18,
            background: 'rgba(0, 200, 255, 0.2)',
            margin: '0 2px',
          }}
        />

        {/* 3D Extrusion Toggle */}
        <button
          type="button"
          onClick={handleToggle3D}
          title={is3D ? 'Switch to 2D flat view' : 'Switch to 3D extruded severity columns'}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '4px 8px',
            borderRadius: 6,
            border: is3D ? '1px solid var(--glow-cyan)' : '1px solid transparent',
            background: is3D ? 'rgba(0, 212, 255, 0.18)' : 'transparent',
            color: is3D ? 'var(--glow-cyan)' : 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: '0.06em',
            cursor: 'pointer',
            boxShadow: is3D ? '0 0 10px rgba(0, 212, 255, 0.25)' : 'none',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            if (!is3D) {
              e.currentTarget.style.background = 'rgba(0, 212, 255, 0.08)'
              e.currentTarget.style.color = 'var(--text-primary)'
            }
          }}
          onMouseLeave={(e) => {
            if (!is3D) {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = 'var(--text-secondary)'
            }
          }}
        >
          <Box size={13} color={is3D ? 'var(--glow-cyan)' : 'var(--text-muted)'} />
          <span>{is3D ? '3D' : '2D'}</span>
        </button>

        {/* Reset View Button */}
        <button
          type="button"
          onClick={handleResetView}
          title="Reset map view to Mumbai overview"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '4px 7px',
            borderRadius: 6,
            border: '1px solid transparent',
            background: 'transparent',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(0, 212, 255, 0.08)'
            e.currentTarget.style.color = 'var(--glow-cyan)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent'
            e.currentTarget.style.color = 'var(--text-secondary)'
          }}
        >
          <span style={{ fontSize: 11 }}>🧭</span>
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
