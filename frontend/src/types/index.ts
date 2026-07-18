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
// Full bundle returned by /api/cell/:id
// ------------------------------------------------------------------
export interface CellBundle {
  master: CellMaster
  environment: Partial<EnvIntelligence>
  planning: Partial<PlanningProfile>
  explanation: Partial<CellExplanation>
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
  ehi: number | null
  priorityLabel: string | null
  lst: number | null
  cluster: string | null
}
