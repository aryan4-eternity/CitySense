import { GeoJsonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import type { LayerKey } from '@/types'

// ----------------------------------------------------------------
// Colour interpolation helpers
// ----------------------------------------------------------------

function lerp(a: number, b: number, t: number): number {
  return Math.round(a + (b - a) * Math.max(0, Math.min(1, t)))
}

type RGBA = [number, number, number, number]

// ----------------------------------------------------------------
// Water / sea cell detection
// ----------------------------------------------------------------
// Reads the `is_water` boolean injected by the backend at startup.
// The threshold (ndvi < 0.05 AND dem < 3.5) lives in backend/main.py
// as _WATER_NDVI_MAX / _WATER_DEM_MAX — do not duplicate it here.
// Null ndvi/dem cells are treated as missing data, NOT as water;
// they render with the grey missing-data colour in getCellColor.

function isWaterCell(props: Record<string, unknown>): boolean {
  return props['is_water'] === true
}


/** Translucent alpha — low enough to see the basemap through, high
 *  enough that colour differences are still readable. */
const FILL_ALPHA = 120

/** Map a 0–1 ratio to an RGBA colour using the given scale. */
function applyScale(ratio: number, scale: LayerConfig['colorScale']): RGBA {
  const t = Math.max(0, Math.min(1, ratio))
  switch (scale) {
    case 'green_red':   // EHI: green (high) → red (low)
      return [lerp(0, 255, 1 - t), lerp(255, 30, 1 - t), lerp(120, 50, 1 - t), FILL_ALPHA]
    case 'red_green':   // Risk: red (high) → green (low)
      return [lerp(0, 255, t), lerp(255, 30, t), lerp(120, 50, t), FILL_ALPHA]
    case 'blue_red':    // LST: blue (cool) → red (hot)
      return [lerp(30, 255, t), lerp(140, 30, t), lerp(240, 40, t), FILL_ALPHA]
    case 'brown_green': // NDVI: brown (low) → green (high)
      return [lerp(160, 10, t), lerp(80, 220, t), lerp(30, 50, t), FILL_ALPHA]
    case 'blue_orange': // UHI: blue (negative) → orange (positive)
      return [lerp(20, 255, t), lerp(100, 160, t), lerp(240, 20, t), FILL_ALPHA]
    case 'categorical':
      return [100, 160, 220, FILL_ALPHA] // fallback — handled per-feature below
    default:
      return [100, 180, 255, FILL_ALPHA]
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
  flood_susceptibility_score: {
    key: 'flood_susceptibility_score',
    label: 'Flood Susceptibility Index (FSI)',
    shortLabel: 'Flood',
    unit: '/100',
    colorScale: 'blue_red',
    description: 'Flood susceptibility proxy: elevation, monsoon rainfall, drainage proximity, imperviousness (0–100, higher = more susceptible)',
    min: 0, max: 100,
  },
  iai_score: {
    key: 'iai_score',
    label: 'Infrastructure Access Index (IAI)',
    shortLabel: 'Access',
    unit: '/100',
    colorScale: 'red_green',
    description: 'Infrastructure access index: proximity to hospitals, schools, parks, transit (0–100, higher = better access)',
    min: 0, max: 100,
  },
  burden_score: {
    key: 'burden_score',
    label: 'Environmental Burden + Access Gap',
    shortLabel: 'Burden',
    unit: '/100',
    colorScale: 'red_green',
    description: 'Combined environmental health deficit and infrastructure access gap (0–100, higher = greater combined burden)',
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
// Entries 0-3 match the K-Means cluster IDs produced by the current pipeline.
// UNKNOWN_CLUSTER_COLOR is used for any cluster_id not in this map — visually
// distinct from all four named clusters so new IDs don't silently merge with
// cluster 4's amber.
const CLUSTER_COLORS: Record<number, RGBA> = {
  0: [0, 180, 255, FILL_ALPHA],    // Coastal/Lowland — cyan
  1: [0, 220, 120, FILL_ALPHA],    // Green/Forested — green
  2: [255, 80, 60, FILL_ALPHA],    // Dense Urban Heat — red
  3: [180, 100, 255, FILL_ALPHA],  // Green/Forested alt — purple
}
const UNKNOWN_CLUSTER_COLOR: RGBA = [120, 120, 120, FILL_ALPHA] // dim grey

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

  // Water / sea cells → fully transparent (basemap shows through)
  if (isWaterCell(props)) return [0, 0, 0, 0]

  if (layerKey === 'cluster') {
    const clusterId = props['cluster_id'] as number ?? -1
    return CLUSTER_COLORS[clusterId] ?? UNKNOWN_CLUSTER_COLOR
  }

  const config = LAYER_CONFIGS[layerKey]
  const value = getValue(props, layerKey)

  // Missing data → distinct grey (visually different from transparent water)
  if (value === null || isNaN(value as number)) return [40, 60, 90, 80]

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
      if (isWaterCell(props)) return [0, 0, 0, 0]
      if (props['cell_id'] === selectedCellId) return [0, 212, 255, 255]
      return [100, 180, 240, 50]
    },

    getLineWidth: (feature: GeoJSON.Feature) => {
      const props = feature.properties as Record<string, unknown>
      if (isWaterCell(props)) return 0
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
    getSize: 13,
    sizeUnits: 'pixels',
    getColor: [255, 255, 255, 255],
    getTextAnchor: 'middle',
    getAlignmentBaseline: 'center',
    lineHeight: 1.6,
    fontFamily: 'Inter, -apple-system, Segoe UI, system-ui, sans-serif',
    fontWeight: 700,
    background: true,
    getBorderWidth: 1.5,
    getBorderColor: [0, 212, 255, 220],
    backgroundPadding: [14, 8, 14, 8],
    getBackgroundColor: [5, 16, 35, 235],
    billboard: true,
    fontSettings: {
      buffer: 8,
      sdf: false,
    },
  })
}
