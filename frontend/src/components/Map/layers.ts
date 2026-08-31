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
 *  enough that colour differences are still crisp and readable. */
const FILL_ALPHA = 130

// ----------------------------------------------------------------
// Multi-stop piecewise color scales (Scientific GIS standard)
// Ensures moderate zones show up as neutral gold/yellow/lime,
// and ONLY severe/crisis cells turn crimson red.
// ----------------------------------------------------------------

type ColorStop = { t: number; rgb: [number, number, number] }

const SCALES: Record<LayerConfig['colorScale'], ColorStop[]> = {
  // EHI & IAI (Higher is healthier):
  // 0-25: Crimson Red (Critical Deficit) -> 25-45: Vivid Amber (Poor) -> 45-65: Warm Gold (Moderate Baseline) -> 65-80: Fresh Lime (Good) -> 80-100: Lush Emerald (Excellent)
  green_red: [
    { t: 0.00, rgb: [255, 45, 75] },    // 0: Critical deficit (Crimson Red)
    { t: 0.25, rgb: [255, 75, 55] },    // 25: Critical / Poor transition
    { t: 0.40, rgb: [255, 140, 35] },   // 40: Poor (Vivid Amber/Orange)
    { t: 0.50, rgb: [255, 215, 45] },   // 50: Moderate urban baseline (Warm Gold)
    { t: 0.70, rgb: [85, 215, 95] },    // 70: Good (Fresh Lime Green)
    { t: 0.88, rgb: [0, 235, 130] },    // 88: Benchmark-level Green Urban
    { t: 1.00, rgb: [0, 240, 130] },    // 100: Pristine / Forest (Lush Emerald)
  ],

  // Risk, Planning Priority, Flood Susceptibility, Burden (Higher is riskier):
  // 0-30: Lush Emerald (Safe) -> 30-50: Fresh Lime (Low Risk) -> 50-70: Warm Gold (Moderate) -> 70-85: Vivid Orange (Elevated) -> 85-100: Crimson Red (Critical Hotspots)
  red_green: [
    { t: 0.00, rgb: [0, 235, 130] },    // 0: Safe (Lush Emerald)
    { t: 0.28, rgb: [85, 215, 95] },    // 28: Low risk (Fresh Lime)
    { t: 0.50, rgb: [255, 215, 45] },   // 50: Moderate urban baseline (Warm Gold)
    { t: 0.75, rgb: [255, 130, 35] },   // 75: High priority / stress (Vivid Orange)
    { t: 0.88, rgb: [255, 65, 55] },    // 88: Near-crisis boundary
    { t: 1.00, rgb: [255, 45, 75] },    // 100: Critical crisis hotspot (Crimson Red)
  ],

  // LST (Thermal gradient: Blue 28-33°C -> Cyan 33-36°C -> Gold 36-40°C -> Orange 40-43°C -> Red >43°C)
  blue_red: [
    { t: 0.00, rgb: [30, 105, 245] },   // Cool forest/water (<30°C)
    { t: 0.30, rgb: [0, 195, 225] },    // Mild coastal (33-35°C)
    { t: 0.55, rgb: [255, 215, 45] },   // Typical urban (38-40°C)
    { t: 0.80, rgb: [255, 115, 30] },   // Elevated thermal stress (41-43°C)
    { t: 1.00, rgb: [255, 35, 75] },    // Extreme UHI peak hotspot (>44°C)
  ],

  // NDVI (Vegetation gradient: Brown <0.12 -> Olive 0.12-0.22 -> Mint 0.22-0.38 -> Deep Forest >0.45)
  brown_green: [
    { t: 0.00, rgb: [145, 95, 70] },    // Barren / mudflat
    { t: 0.20, rgb: [195, 155, 95] },   // Dense impervious / concrete (<0.18)
    { t: 0.35, rgb: [200, 220, 75] },   // Sparse roadside greenery / grass (~0.25)
    { t: 0.60, rgb: [65, 205, 95] },    // Green-urban benchmark & residential gardens (~0.38)
    { t: 1.00, rgb: [0, 160, 55] },     // Dense national park canopy & mangroves (>0.55)
  ],

  // UHI Intensity (-2°C to +15°C relative to SGNP baseline)
  blue_orange: [
    { t: 0.00, rgb: [25, 85, 230] },    // Cooler than SGNP baseline (<0°C)
    { t: 0.20, rgb: [0, 185, 220] },    // Mild maritime cooling (+1 to +3°C)
    { t: 0.45, rgb: [200, 225, 245] },  // Neutral baseline transition (+5 to +6°C)
    { t: 0.65, rgb: [255, 215, 45] },   // Typical urban UHI (+8 to +10°C, Warm Gold)
    { t: 0.82, rgb: [255, 130, 35] },   // Elevated urban heat anomaly (+11 to +13°C)
    { t: 1.00, rgb: [255, 35, 55] },    // Severe heat island anomaly (+14°C to +15°C)
  ],

  categorical: [
    { t: 0.00, rgb: [100, 160, 220] },
    { t: 1.00, rgb: [100, 160, 220] },
  ],
}

/** Map a 0–1 ratio to an RGBA colour using multi-stop piecewise interpolation. */
function applyScale(ratio: number, scale: LayerConfig['colorScale']): RGBA {
  const stops = SCALES[scale] ?? SCALES.green_red
  const t = Math.max(0, Math.min(1, ratio))

  if (t <= stops[0].t) return [...stops[0].rgb, FILL_ALPHA]
  if (t >= stops[stops.length - 1].t) return [...stops[stops.length - 1].rgb, FILL_ALPHA]

  for (let i = 0; i < stops.length - 1; i++) {
    const s0 = stops[i]
    const s1 = stops[i + 1]
    if (t >= s0.t && t <= s1.t) {
      const localT = (t - s0.t) / (s1.t - s0.t)
      return [
        lerp(s0.rgb[0], s1.rgb[0], localT),
        lerp(s0.rgb[1], s1.rgb[1], localT),
        lerp(s0.rgb[2], s1.rgb[2], localT),
        FILL_ALPHA,
      ]
    }
  }

  return [...stops[0].rgb, FILL_ALPHA]
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
    min: 28, max: 46,
  },
  mean_ndvi: {
    key: 'mean_ndvi',
    label: 'Vegetation Index (NDVI)',
    shortLabel: 'NDVI',
    unit: '',
    colorScale: 'brown_green',
    description: 'Normalised Difference Vegetation Index (–1 to +1)',
    min: 0.05, max: 0.65,
  },
  mean_ndbi: {
    key: 'mean_ndbi',
    label: 'Built-up Density (NDBI)',
    shortLabel: 'NDBI',
    unit: '',
    colorScale: 'red_green',
    description: 'Normalised Difference Built-up Index (higher = denser urban)',
    min: -0.15, max: 0.35,
  },
  uhi_intensity: {
    key: 'uhi_intensity',
    label: 'Urban Heat Island Intensity',
    shortLabel: 'UHI',
    unit: '°C',
    colorScale: 'blue_orange',
    description: 'Temperature deviation from green reference zone (°C)',
    min: -2, max: 15,
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
    colorScale: 'red_green',
    description: 'Flood susceptibility proxy: elevation, monsoon rainfall, drainage proximity, imperviousness (0–100, higher = more susceptible)',
    min: 0, max: 100,
  },
  iai_score: {
    key: 'iai_score',
    label: 'Infrastructure Access Index (IAI)',
    shortLabel: 'Access',
    unit: '/100',
    colorScale: 'green_red',
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
// MMR Regional Boundaries (White Glow Outline on Selection)
// ----------------------------------------------------------------
import type { MMRRegionKey } from '@/types'

export const REGION_BOUNDARIES: Record<Exclude<MMRRegionKey, 'all'>, GeoJSON.Feature> = {
  island_city: {
    type: 'Feature',
    properties: { name: 'Mumbai Island City (South Mumbai)', region: 'island_city' },
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [72.785, 18.940],
        [72.795, 18.885],
        [72.845, 18.885],
        [72.855, 18.940],
        [72.865, 18.975],
        [72.885, 19.035],
        [72.845, 19.035],
        [72.805, 19.015],
        [72.785, 18.970],
        [72.785, 18.940],
      ]],
    },
  },
  suburban: {
    type: 'Feature',
    properties: { name: 'Mumbai Suburban District', region: 'suburban' },
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [72.810, 19.000],
        [72.890, 19.000],
        [72.955, 19.000],
        [72.955, 19.140],
        [72.955, 19.280],
        [72.890, 19.280],
        [72.785, 19.280],
        [72.785, 19.160],
        [72.810, 19.000],
      ]],
    },
  },
  navi_mumbai: {
    type: 'Feature',
    properties: { name: 'Navi Mumbai & Panvel', region: 'navi_mumbai' },
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [72.940, 18.870],
        [73.050, 18.870],
        [73.160, 18.880],
        [73.160, 19.060],
        [73.105, 19.155],
        [72.985, 19.185],
        [72.940, 19.185],
        [72.940, 19.040],
        [72.940, 18.870],
      ]],
    },
  },
  thane: {
    type: 'Feature',
    properties: { name: 'Thane Municipal Corporation', region: 'thane' },
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [72.880, 19.260],
        [72.880, 19.340],
        [73.040, 19.340],
        [73.040, 19.160],
        [72.930, 19.160],
        [72.930, 19.260],
        [72.880, 19.260],
      ]],
    },
  },
  kalyan_dombivli: {
    type: 'Feature',
    properties: { name: 'Kalyan-Dombivli & Extended MMR', region: 'kalyan_dombivli' },
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [73.040, 19.170],
        [73.175, 19.170],
        [73.175, 19.350],
        [73.040, 19.350],
        [73.040, 19.170],
      ]],
    },
  },
}

export function makeRegionBoundaryLayer(selectedRegion: MMRRegionKey, is3D: boolean): GeoJsonLayer | null {
  if (!selectedRegion) return null

  // When "All MMR" is selected → render ALL 5 region boundaries with subtle white delineation
  // When a specific region is selected → render only that region with a bright thick outline
  const isOverview = selectedRegion === 'all'

  const features = isOverview
    ? Object.values(REGION_BOUNDARIES)
    : [REGION_BOUNDARIES[selectedRegion as keyof typeof REGION_BOUNDARIES]].filter(Boolean)

  if (features.length === 0) return null

  const boundaryGeoJson: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: features as GeoJSON.Feature[],
  }

  return new GeoJsonLayer({
    id: `region-boundary-${selectedRegion}-${is3D ? '3d' : '2d'}`,
    data: boundaryGeoJson,
    pickable: false,
    stroked: true,
    filled: isOverview ? false : true,        // No fill tint in overview mode
    extruded: false,
    lineWidthMinPixels: isOverview ? 1.5 : 3.5,
    lineWidthMaxPixels: isOverview ? 4 : 8,
    getLineColor: isOverview
      ? [255, 255, 255, 90]                   // Subtle white delineation in overview
      : [255, 255, 255, 255],                 // Bright crisp white for focused region
    getFillColor: isOverview
      ? [0, 0, 0, 0]                          // Fully transparent in overview
      : [255, 255, 255, 14],                  // Subtle glow in focused mode
    getLineWidth: isOverview ? 2 : 4,
    lineJointRounded: true,
    lineCapRounded: true,
    updateTriggers: {
      getLineColor: [selectedRegion],
      getLineWidth: [selectedRegion],
      getFillColor: [selectedRegion],
    },
  })
}

// ----------------------------------------------------------------
// Fill colour function — used by GeoJsonLayer getFillColor
// ----------------------------------------------------------------

export function getCellColor(
  props: Record<string, unknown>,
  layerKey: LayerKey,
  isSelected: boolean,
  selectedRegion: MMRRegionKey = 'all',
): RGBA {
  if (isSelected) return [0, 212, 255, 65]   // translucent cyan highlight

  // Water / sea cells → fully transparent (basemap shows through)
  if (isWaterCell(props)) return [0, 0, 0, 0]

  const cellRegion = (props['region_key'] as string) || ''
  const isDimmed = selectedRegion !== 'all' && cellRegion && cellRegion !== selectedRegion

  if (layerKey === 'cluster') {
    const clusterId = props['cluster_id'] as number ?? -1
    const baseColor = CLUSTER_COLORS[clusterId] ?? UNKNOWN_CLUSTER_COLOR
    return isDimmed ? [baseColor[0], baseColor[1], baseColor[2], 30] : baseColor
  }

  const config = LAYER_CONFIGS[layerKey]
  const value = getValue(props, layerKey)

  // Missing data → distinct grey
  if (value === null || isNaN(value as number)) {
    return isDimmed ? [40, 60, 90, 25] : [40, 60, 90, 80]
  }

  const vmin = config.min ?? 0
  const vmax = config.max ?? 100
  const ratio = (value - vmin) / (vmax - vmin)

  const color = applyScale(ratio, config.colorScale)
  if (isDimmed) {
    return [color[0], color[1], color[2], 32] // dimmed outside active selected region
  }
  return color
}

// ----------------------------------------------------------------
// GeoJsonLayer — choropleth grid
// ----------------------------------------------------------------

export function makeChoroplethLayer(
  geojson: GeoJSON.FeatureCollection,
  activeLayer: LayerKey,
  selectedCellId: string | null,
  selectedRegion: MMRRegionKey,
  is3D: boolean,
  onHover: (info: { object?: GeoJSON.Feature; x: number; y: number }) => void,
  onClick: (info: { object?: GeoJSON.Feature }) => void,
) {
  return new GeoJsonLayer({
    id: `choropleth-${activeLayer}-${is3D ? '3d' : '2d'}`,
    data: geojson,
    pickable: true,
    stroked: true,
    filled: true,
    extruded: is3D,
    wireframe: is3D,
    lineWidthMinPixels: 0,
    lineWidthMaxPixels: 3,

    getFillColor: (feature: GeoJSON.Feature) => {
      const props = feature.properties as Record<string, unknown>
      const isSelected = props['cell_id'] === selectedCellId
      return getCellColor(props, activeLayer, isSelected, selectedRegion)
    },

    getLineColor: (feature: GeoJSON.Feature) => {
      const props = feature.properties as Record<string, unknown>
      if (isWaterCell(props)) return [0, 0, 0, 0]
      if (props['cell_id'] === selectedCellId) return [0, 230, 255, 255]
      const cellRegion = (props['region_key'] as string) || ''
      if (selectedRegion !== 'all' && cellRegion === selectedRegion) {
        return [255, 255, 255, 120] // crisp white cell borders inside selected region
      }
      return [100, 180, 240, 50]
    },

    getLineWidth: (feature: GeoJSON.Feature) => {
      const props = feature.properties as Record<string, unknown>
      if (isWaterCell(props)) return 0
      if (props['cell_id'] === selectedCellId) return 2.5
      const cellRegion = (props['region_key'] as string) || ''
      if (selectedRegion !== 'all' && cellRegion === selectedRegion) return 1.0
      return 0.5
    },

    getElevation: (feature: GeoJSON.Feature) => {
      if (!is3D) return 0
      const props = feature.properties as Record<string, unknown>
      if (isWaterCell(props)) return 0
      const val = getValue(props, activeLayer)
      if (val === null || isNaN(val as number)) return 80

      const config = LAYER_CONFIGS[activeLayer]
      const vmin = config.min ?? 0
      const vmax = config.max ?? 100
      const ratio = Math.max(0, Math.min(1, ((val as number) - vmin) / (vmax - vmin)))
      return ratio * 3200 + 100
    },

    onHover,
    onClick,

    updateTriggers: {
      getFillColor:  [activeLayer, selectedCellId, selectedRegion],
      getLineColor:  [selectedCellId, selectedRegion],
      getLineWidth:  [selectedCellId, selectedRegion],
      getElevation:  [activeLayer, is3D],
    },

    transitions: {
      getFillColor: { duration: 400, easing: (t: number) => t },
      getElevation: { duration: 600, easing: (t: number) => t },
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
    getPosition: (d) => [d.position[0], d.position[1], 100],
    getText: (d) => d.label,
    getSize: 12,
    sizeUnits: 'pixels',
    getColor: [255, 255, 255, 255],
    getTextAnchor: 'middle',
    getAlignmentBaseline: 'center',
    getPixelOffset: [0, -8],
    fontFamily: 'Inter, -apple-system, Segoe UI, system-ui, sans-serif',
    fontWeight: 700,
    background: true,
    getBorderWidth: 1.5,
    getBorderColor: [0, 212, 255, 220],
    backgroundPadding: [12, 6, 12, 6],
    getBackgroundColor: [5, 16, 35, 235],
    billboard: true,
    parameters: {
      depthTest: false,
    },
    fontSettings: {
      buffer: 8,
      sdf: false,
    },
  })
}
