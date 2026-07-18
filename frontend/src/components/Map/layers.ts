import { GeoJsonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import type { LayerKey } from '@/types'

// ----------------------------------------------------------------
// Colour interpolation helpers
// ----------------------------------------------------------------

function lerp(a: number, b: number, t: number): number {
  return Math.round(a + (b - a) * Math.max(0, Math.min(1, t)))
}

type RGBA = [number, number, number, number]

/** Map a 0–1 ratio to an RGBA colour using the given scale. */
function applyScale(ratio: number, scale: LayerConfig['colorScale']): RGBA {
  const t = Math.max(0, Math.min(1, ratio))
  switch (scale) {
    case 'green_red':   // EHI: green (high) → red (low)  — note: high EHI = healthier
      return [lerp(0, 255, 1 - t), lerp(255, 40, 1 - t), lerp(159, 60, 1 - t), 210]
    case 'red_green':   // Risk: red (high) → green (low)
      return [lerp(0, 255, t), lerp(255, 40, t), lerp(159, 60, t), 210]
    case 'blue_red':    // LST: blue (cool) → red (hot)
      return [lerp(30, 255, t), lerp(120, 30, t), lerp(220, 50, t), 210]
    case 'brown_green': // NDVI: brown (low) → green (high)
      return [lerp(139, 20, t), lerp(90, 200, t), lerp(43, 60, t), 210]
    case 'blue_orange': // UHI: blue (negative) → orange (positive)
      return [lerp(20, 255, t), lerp(100, 150, t), lerp(220, 20, t), 210]
    case 'categorical':
      return [100, 160, 220, 180] // fallback — handled per-feature below
    default:
      return [100, 180, 255, 180]
  }
}

// ----------------------------------------------------------------
// Layer configuration registry
// ----------------------------------------------------------------

export interface LayerConfig {
  key: LayerKey
  label: string
  shortLabel: string
  unit: string
  colorScale: 'green_red' | 'red_green' | 'blue_red' | 'brown_green' | 'categorical' | 'blue_orange'
  description: string
  // For continuous scales: city-wide min/max for normalisation
  min?: number
  max?: number
}

export const LAYER_CONFIGS: Record<LayerKey, LayerConfig> = {
  environmental_health: {
    key: 'environmental_health',
    label: 'Environmental Health (EHI)',
    shortLabel: 'EHI',
    unit: '/100',
    colorScale: 'green_red',
    description: 'Composite environmental health index (0–100, higher = healthier)',
    min: 0, max: 100,
  },
  risk_score: {
    key: 'risk_score',
    label: 'Risk Score',
    shortLabel: 'Risk',
    unit: '/100',
    colorScale: 'red_green',
    description: 'PCA-derived environmental risk score (0–100, higher = more risk)',
    min: 0, max: 100,
  },
  mean_lst: {
    key: 'mean_lst',
    label: 'Land Surface Temperature',
    shortLabel: 'LST',
    unit: '°C',
    colorScale: 'blue_red',
    description: 'Mean land surface temperature derived from Landsat thermal band',
    min: 28, max: 50,
  },
  mean_ndvi: {
    key: 'mean_ndvi',
    label: 'Vegetation Index (NDVI)',
    shortLabel: 'NDVI',
    unit: '',
    colorScale: 'brown_green',
    description: 'Normalised Difference Vegetation Index (–1 to +1)',
    min: -0.2, max: 0.7,
  },
  mean_ndbi: {
    key: 'mean_ndbi',
    label: 'Built-up Density (NDBI)',
    shortLabel: 'NDBI',
    unit: '',
    colorScale: 'red_green',
    description: 'Normalised Difference Built-up Index (higher = denser urban)',
    min: -0.25, max: 0.35,
  },
  uhi_intensity: {
    key: 'uhi_intensity',
    label: 'Urban Heat Island Intensity',
    shortLabel: 'UHI',
    unit: '°C',
    colorScale: 'blue_orange',
    description: 'Temperature deviation from green reference zone (°C)',
    min: -10, max: 10,
  },
  planning_priority_score: {
    key: 'planning_priority_score',
    label: 'Planning Priority Score',
    shortLabel: 'Priority',
    unit: '/100',
    colorScale: 'red_green',
    description: 'Intervention urgency score combining EHI, risk, population, and land use',
    min: 0, max: 100,
  },
  cluster: {
    key: 'cluster',
    label: 'Urban Typology Clusters',
    shortLabel: 'Clusters',
    unit: '',
    colorScale: 'categorical',
    description: 'K-Means urban typology classification',
  },
}

// Cluster colour palette (Tab10-inspired, high contrast on dark background)
const CLUSTER_COLORS: Record<number, RGBA> = {
  0: [0, 180, 255, 200],    // Coastal/Lowland — cyan
  1: [0, 220, 120, 200],    // Green/Forested — green
  2: [255, 80, 60, 200],    // Dense Urban Heat — red
  3: [180, 100, 255, 200],  // Green/Forested alt — purple
  4: [255, 180, 40, 200],   // fallback — amber
}

// ----------------------------------------------------------------
// Property value getter — resolves env_intel fields joined onto GeoJSON
// ----------------------------------------------------------------

function getValue(
  props: Record<string, unknown>,
  layerKey: LayerKey,
): number | null {
  // planning_priority_score is in planning_profiles, joined as property
  if (layerKey === 'planning_priority_score') {
    return (props['planning_priority_score'] as number) ?? null
  }
  const v = props[layerKey]
  if (v === null || v === undefined) return null
  return Number(v)
}

// ----------------------------------------------------------------
// Fill colour function — used by GeoJsonLayer getFillColor
// ----------------------------------------------------------------

export function getCellColor(
  props: Record<string, unknown>,
  layerKey: LayerKey,
  isSelected: boolean,
): RGBA {
  if (isSelected) return [0, 212, 255, 240]   // bright cyan for selected

  if (layerKey === 'cluster') {
    const clusterId = props['cluster_id'] as number ?? 0
    return CLUSTER_COLORS[clusterId] ?? CLUSTER_COLORS[4]
  }

  const config = LAYER_CONFIGS[layerKey]
  const value = getValue(props, layerKey)

  if (value === null || isNaN(value)) return [40, 60, 90, 120]  // grey for missing

  const vmin = config.min ?? 0
  const vmax = config.max ?? 100
  const ratio = (value - vmin) / (vmax - vmin)

  return applyScale(ratio, config.colorScale)
}

// ----------------------------------------------------------------
// GeoJsonLayer — choropleth grid
// ----------------------------------------------------------------

export function makeChoroplethLayer(
  geojson: GeoJSON.FeatureCollection,
  activeLayer: LayerKey,
  selectedCellId: string | null,
  onHover: (info: { object?: GeoJSON.Feature; x: number; y: number }) => void,
  onClick: (info: { object?: GeoJSON.Feature }) => void,
) {
  return new GeoJsonLayer({
    id: `choropleth-${activeLayer}`,
    data: geojson,
    pickable: true,
    stroked: true,
    filled: true,
    extruded: false,
    lineWidthMinPixels: 0,
    lineWidthMaxPixels: 1,

    getFillColor: (feature: GeoJSON.Feature) => {
      const props = feature.properties as Record<string, unknown>
      const isSelected = props['cell_id'] === selectedCellId
      return getCellColor(props, activeLayer, isSelected)
    },

    getLineColor: (feature: GeoJSON.Feature) => {
      const props = feature.properties as Record<string, unknown>
      if (props['cell_id'] === selectedCellId) return [0, 212, 255, 255]
      return [0, 80, 140, 60]
    },

    getLineWidth: (feature: GeoJSON.Feature) => {
      const props = feature.properties as Record<string, unknown>
      return props['cell_id'] === selectedCellId ? 2 : 0.5
    },

    updateTriggers: {
      getFillColor:  [activeLayer, selectedCellId],
      getLineColor:  [selectedCellId],
      getLineWidth:  [selectedCellId],
    },

    onHover,
    onClick,

    transitions: {
      getFillColor: { duration: 400, easing: (t: number) => t },
    },
  })
}

// ----------------------------------------------------------------
// ScatterplotLayer — pulsing hotspot rings on top-N risk cells
// ----------------------------------------------------------------

export function makeHotspotLayer(
  hotspots: Array<{ position: [number, number]; radius: number }>,
  animTime: number,  // 0–1, driven by useAnimationFrame
) {
  // Animate radius oscillation using animTime
  return new ScatterplotLayer({
    id: 'hotspots',
    data: hotspots,
    pickable: false,
    opacity: 0.6,
    stroked: true,
    filled: false,
    radiusUnits: 'meters',
    getPosition: (d) => d.position,
    getRadius: (d) => d.radius * (1 + 0.35 * Math.sin(animTime * Math.PI * 2)),
    getLineColor: [255, 59, 92, 180],
    getLineWidth: 2,
    lineWidthUnits: 'pixels',
  })
}

// ----------------------------------------------------------------
// TextLayer — cluster centroid labels
// ----------------------------------------------------------------

export function makeClusterLabelLayer(
  centroids: Array<{ position: [number, number]; label: string }>,
) {
  return new TextLayer({
    id: 'cluster-labels',
    data: centroids,
    pickable: false,
    getPosition: (d) => d.position,
    getText: (d) => d.label,
    getSize: 11,
    getColor: [200, 230, 255, 180],
    getTextAnchor: 'middle',
    getAlignmentBaseline: 'center',
    fontFamily: 'Inter, system-ui, sans-serif',
    fontWeight: 600,
    background: true,
    getBorderWidth: 0,
    backgroundPadding: [4, 2],
    getBackgroundColor: [5, 16, 35, 180],
  })
}
