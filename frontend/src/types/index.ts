// ============================================================
// CitySense TypeScript Interfaces
// Mirrors the exact shape returned by backend/main.py
// ============================================================

// ------------------------------------------------------------------
// Master cell properties (from cells_master.geojson)
// ------------------------------------------------------------------
export interface CellMaster {
  cell_id: string
  mean_ndvi: number
  mean_lst: number
  mean_ndbi: number
  mean_dem: number
  uhi_intensity: number
  risk_score: number
  sustainability_score: number
  cluster_id: number
  cluster: string
  top_positive_driver: string | null
  top_positive_shap: number
  top_negative_driver: string | null
  top_negative_shap: number
  explanation_text: string
}

// ------------------------------------------------------------------
// Environmental intelligence (from environmental_intelligence.json)
// ------------------------------------------------------------------
export interface EnvIntelligence {
  environmental_health: number
  environmental_status: 'Excellent' | 'Good' | 'Moderate' | 'Poor' | 'Critical'
  city_rank_lst: number
  city_rank_ndvi: number
  city_rank_ndbi: number
  city_rank_uhi: number
  city_rank_dem: number
  city_rank_risk: number
  mean_lst_vs_city_avg: number
  mean_ndvi_vs_city_avg: number
  mean_ndbi_vs_city_avg: number
  uhi_intensity_vs_city_avg: number
  mean_dem_vs_city_avg: number
  mean_lst_pct_diff: number
  mean_ndvi_pct_diff: number
  mean_ndbi_pct_diff: number
  uhi_intensity_pct_diff: number
  mean_dem_pct_diff: number
  detected_conditions: string[]
  primary_issue: string | null
  secondary_issue: string | null
  spatial_context: string
  environmental_summary: string
}

// ------------------------------------------------------------------
// Planning profile (from planning_profiles.json)
// ------------------------------------------------------------------
export interface PlanningProfile {
  planning_priority: 'Critical' | 'High' | 'Medium' | 'Low' | 'Very Low'
  priority_score: number
  primary_objective: string
  recommended_intervention: string
  secondary_interventions: string[]
  expected_benefits: string[]
  implementation_cost: 'Low' | 'Medium' | 'High'
  implementation_timeline: string
  implementation_complexity: 'Easy' | 'Moderate' | 'Complex'
  confidence: number
  evidence: string
  environmental_health: number
  risk_score: number
}

// ------------------------------------------------------------------
// SHAP explanation (from cell_explanations.json)
// ------------------------------------------------------------------
export interface CellExplanation {
  cell_id?: string
  risk_score?: number
  sustainability_score?: number
  top_positive_driver?: string
  top_positive_shap?: number
  top_negative_driver?: string
  top_negative_shap?: number
  explanation_text?: string
}

// ------------------------------------------------------------------
// Geographic Metadata (from geographic_metadata.json)
// ------------------------------------------------------------------
export interface GeographicMetadata {
  grid_id?: string
  primary_locality?: string
  secondary_localities?: string[]
  ward?: string
  zone?: string
  nearest_landmarks?: string[]
  dominant_land_use?: string
  population?: number
  population_density?: number
  grid_area_km2?: number
  perimeter_km?: number
  centroid_lat?: number
  centroid_lon?: number
}

// ------------------------------------------------------------------
// Full bundle returned by /api/cell/:id
// ------------------------------------------------------------------
export interface CellBundle {
  master: CellMaster
  environment: Partial<EnvIntelligence>
  planning: Partial<PlanningProfile>
  explanation: Partial<CellExplanation>
  flood?: {
    flood_susceptibility_score?: number
    flood_category?: string
    elevation_m?: number
    drainage_distance_m?: number
    monsoon_precipitation_mm?: number
  }
  access?: {
    iai_score?: number
    iai_category?: string
    hospital_dist_m?: number
    school_dist_m?: number
    park_dist_m?: number
    transit_dist_m?: number
  }
  burden?: {
    burden_score?: number
    burden_category?: string
    environmental_deficit?: number
    access_deficit?: number
  }
  geographic?: GeographicMetadata
}

// ------------------------------------------------------------------
// /api/stats response
// ------------------------------------------------------------------
export interface CityStats {
  total_cells: number
  avg_ehi: number
  min_ehi: number
  max_ehi: number
  avg_risk: number
  priority_counts: Record<string, number>
  status_counts: Record<string, number>
  top_issues: Array<{ issue: string; count: number }>
  top_interventions: Array<{ intervention: string; count: number }>
}

// ------------------------------------------------------------------
// /api/rankings row
// ------------------------------------------------------------------
export interface RankingRow {
  cell_id: string
  planning_priority: string
  priority_score: number
  recommended_intervention: string
  environmental_health: number
  risk_score: number
  mean_lst: number
  mean_ndvi: number
  cluster: string
  primary_issue: string | null
}

// ------------------------------------------------------------------
// Map layer configuration
// ------------------------------------------------------------------
export type LayerKey =
  | 'environmental_health'
  | 'risk_score'
  | 'mean_lst'
  | 'mean_ndvi'
  | 'mean_ndbi'
  | 'uhi_intensity'
  | 'planning_priority_score'
  | 'flood_susceptibility_score'
  | 'iai_score'
  | 'burden_score'
  | 'cluster'

export interface LayerConfig {
  key: LayerKey
  label: string
  shortLabel: string
  unit: string
  colorScale: 'green_red' | 'red_green' | 'blue_red' | 'brown_green' | 'categorical' | 'blue_orange'
  description: string
}

// ------------------------------------------------------------------
// Tooltip state (shown on cell hover over map)
// ------------------------------------------------------------------
export interface TooltipInfo {
  x: number
  y: number
  cellId: string
  activeMetric: string
  activeValue: number | string | null
  activeUnit: string
  ehi: number | null
  risk: number | null
  ndvi: number | null
  ndbi: number | null
  priorityLabel: string | null
  lst: number | null
  cluster: string | null
}

// ------------------------------------------------------------------
// Basemap configuration
// ------------------------------------------------------------------
export type BasemapKey = 'satellite' | 'dark' | 'streets' | 'light'

export interface BasemapOption {
  key: BasemapKey
  label: string
  shortLabel: string
  description: string
  style: string | Record<string, unknown>
}

// ------------------------------------------------------------------
// Satellite Feed & Ingestion types
// ------------------------------------------------------------------
export interface SatelliteStreamInfo {
  id: string
  name: string
  indicators: string[]
  resolution: string
  status: 'synchronized' | 'cached_fallback' | 'offline'
  fallback_active: boolean
  cloud_cover?: string
  emissivity_corrected?: boolean
  source: string
}

export interface SatelliteStatusResponse {
  status: string
  last_sync: string
  cached_cells: number
  streams: SatelliteStreamInfo[]
}

export interface SatelliteFeedResult {
  id: string
  name: string
  status: 'synced' | 'cached_fallback' | 'failed'
  mode: string
  message: string
  records: number
}

export interface SatelliteSyncResponse {
  status: 'success' | 'partial_fallback'
  sync_time: string
  total_cells_verified: number
  fallback_engaged: boolean
  summary: string
  feeds: SatelliteFeedResult[]
}

// ------------------------------------------------------------------
// MMR Regional Division types
// ------------------------------------------------------------------
export type MMRRegionKey =
  | 'all'
  | 'island_city'
  | 'suburban'
  | 'navi_mumbai'
  | 'thane'
  | 'kalyan_dombivli'

export interface MMRRegionOption {
  key: MMRRegionKey
  label: string
  shortLabel: string
  icon: string
  corporation: string
  description: string
  center: [number, number] // [lng, lat]
  zoom: number
  pitch?: number
  bearing?: number
}

// ------------------------------------------------------------------
// Chat types
// ------------------------------------------------------------------
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  cell_id?: string | null  // if set, the map should highlight this cell
}

export interface ChatRequest {
  messages: Array<{ role: string; content: string }>
}

export interface ChatResponse {
  reply: string
  cell_id: string | null
}
