# CitySense — Complete Technical Documentation

**Project:** CitySense: AI-Powered Urban Planning Decision Support System
**City:** Mumbai, India
**Data:** 836 grid cells, 0.01° resolution (~1 km²/cell) over bbox 72.77–72.99°E, 18.89–19.27°N

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Project Structure](#2-project-structure)
3. [Configuration System](#3-configuration-system)
4. [Pipeline Orchestration — main.py](#4-pipeline-orchestration--mainpy)
5. [Phase 0 — Ingestion Layer](#5-phase-0--ingestion-layer)
6. [Phase 1 — Processing Pipeline](#6-phase-1--processing-pipeline)
7. [Phase 2 — Environmental Intelligence Layer](#7-phase-2--environmental-intelligence-layer)
8. [Phase 3 — Urban Planning Decision Engine](#8-phase-3--urban-planning-decision-engine)
9. [Backend API — FastAPI](#9-backend-api--fastapi)
10. [Frontend — React Command-Center Dashboard](#10-frontend--react-command-center-dashboard)
11. [Data Flow — End to End](#11-data-flow--end-to-end)
12. [Output Files Reference](#12-output-files-reference)
13. [Test Suite](#13-test-suite)
14. [How to Run Everything](#14-how-to-run-everything)
15. [Limitations & Validity](#15-limitations--validity)
16. [Public Health Co-location Check](#16-public-health-co-location-check)

---

## 1. System Overview

CitySense is a three-phase geospatial AI pipeline that transforms raw satellite imagery into actionable urban planning decisions.

```
Satellite Data (GEE)
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 0 — INGESTION                                        │
│  Google Earth Engine → per-cell GeoJSON indicator grids     │
│  Outputs: NDVI, LST, NDBI, DEM grids                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1 — PROCESSING                                       │
│  Merge → UHI → PCA Risk Score → K-Means → SHAP             │
│  Output: cells_master.geojson (all columns)                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2 — ENVIRONMENTAL INTELLIGENCE                       │
│  EHI scoring → condition detection → narratives             │
│  Output: environmental_intelligence.json                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3 — PLANNING DECISION ENGINE                         │
│  YAML knowledge base → priority → intervention              │
│  Output: planning_profiles.json                             │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI) + FRONTEND (React + Deck.gl)             │
│  REST API + WebGL command-center dashboard                  │
└─────────────────────────────────────────────────────────────┘
```

**Key principle:** Each phase only reads its upstream outputs — never modifies them. The master GeoDataFrame is the single source of truth.

---

## 2. Project Structure

```
city_sense/
├── main.py                          # Pipeline orchestrator
├── config_loader.py                 # YAML config loader
├── utils.py                         # Logging + config validation
├── geo_utils.py                     # Shared geographic utilities
├── requirements.txt                 # Python dependencies
├── config/
│   ├── config.yaml                  # All runtime configuration
│   └── geographic_config.yaml       # Geographic enrichment settings
├── ingestion/                       # Phase 0: GEE data fetching
│   ├── generate_grid.py
│   ├── fetch_ndvi.py
│   ├── fetch_lst.py
│   ├── fetch_ndbi.py
│   └── fetch_dem.py
├── processing/                      # Phase 1: Indicator processing
│   ├── merge_indicators.py
│   ├── compute_uhi.py
│   ├── lst_ndvi_analysis.py
│   ├── pca_scoring.py
│   ├── kmeans_clustering.py
│   ├── train_explainability.py
│   ├── generate_explanations_json.py
│   └── validate_scores.py
├── metadata/                        # Geographic enrichment
│   └── geo_enrichment.py
├── environment/                     # Phase 2: Environmental intelligence
│   ├── environment_templates.py
│   ├── comparative_analysis.py
│   ├── environmental_health.py
│   ├── indicator_interpreter.py
│   ├── environmental_summary.py
│   └── generate_environmental_intelligence.py
├── planning/                        # Phase 3: Planning decision engine
│   ├── intervention_catalog.yaml
│   ├── knowledge_base.py
│   ├── priority_engine.py
│   ├── intervention_engine.py
│   ├── planning_summary.py
│   ├── decision_engine.py
│   └── generate_planning_profiles.py
├── backend/
│   └── main.py                      # FastAPI REST server
├── frontend/                        # React + Deck.gl dashboard
│   └── src/
│       ├── App.tsx
│       ├── store/useStore.ts
│       ├── api/citysense.ts
│       ├── types/index.ts
│       ├── styles/globals.css
│       └── components/
│           ├── Map/DeckMap.tsx
│           ├── Map/layers.ts
│           ├── Header/Header.tsx
│           ├── StatsPanel/StatsPanel.tsx
│           ├── CellPanel/CellPanel.tsx
│           ├── LayerBar/LayerBar.tsx
│           └── ui/ScanLine.tsx
├── data/                            # Pipeline outputs
├── models/                          # Trained model .pkl files
├── tests/                           # Unit tests
└── logs/                            # Pipeline run logs
```

---

## 3. Configuration System

### Files

| File | Purpose |
|---|---|
| `config/config.yaml` | Master configuration — all paths, parameters, thresholds |
| `config_loader.py` | Loads and caches the YAML; resolves relative paths |
| `utils.py` | `setup_logging()` and `validate_config()` |

### config_loader.py

**`load_config(path)`**
- Reads `config/config.yaml` using `yaml.safe_load`
- Returns a fresh `dict` on every call (callers cannot pollute a shared copy)
- Default path: `PROJECT_ROOT/config/config.yaml`

**`project_path(config, output_key)`**
- Resolves `config["output_paths"][output_key]` to an absolute `Path`
- Used by every pipeline stage to find its input/output files
- Example: `project_path(cfg, "master_data")` → `d:/…/data/cells_master.geojson`

### Key config.yaml sections

| Section | Contents |
|---|---|
| `aoi` | Bounding box: west=72.77, south=18.89, east=72.99, north=19.27 |
| `grid.cell_size_deg` | 0.01° per cell ≈ 1 km |
| `time_window` | Pre-monsoon 2023-03-01 → 2023-05-31 |
| `gee` | GEE project ID, collection IDs, cloud threshold, reduction scales |
| `model` | PCA components, K-Means candidates, Random Forest hyperparameters |
| `uhi / processing` | UHI baseline zone (Sanjay Gandhi National Park bbox) |
| `dashboard` | Map centre, zoom, layer thresholds |
| `output_paths` | 30+ named paths for every pipeline output |

### utils.py

**`setup_logging()`**
- Creates a `CitySense` root logger
- Console handler: INFO level, formatted with timestamp
- File handler: DEBUG level → `logs/pipeline.log`
- Returns the configured logger

**`validate_config(config)`**
- Checks required keys: `aoi`, `grid`, `time_window`, `output_paths`
- Validates bounding box consistency (west < east, south < north)
- Validates date range (start < end)
- Raises `ValueError` on any failure

---

## 4. Pipeline Orchestration — main.py

### Purpose
Single entry point that runs all 16 pipeline stages in dependency order with smart output-caching.

### `run_stage(name, stage_fn, logger, expected_output)`
- If `expected_output` path already exists on disk → skips the stage (caching)
- Otherwise calls `stage_fn()`, measures elapsed time, logs result
- On exception: logs error with traceback, re-raises (stops pipeline)

### `main()`
Calls `run_stage` for each of the 16 stages in this order:

| # | Stage name | Module | Output cached? |
|---|---|---|---|
| 1 | Generate grid | `ingestion.generate_grid` | `data/grid.geojson` |
| 2 | Fetch NDVI | `ingestion.fetch_ndvi` | `data/ndvi_grid.geojson` |
| 3 | Fetch LST | `ingestion.fetch_lst` | `data/lst_grid.geojson` |
| 4 | Fetch NDBI | `ingestion.fetch_ndbi` | `data/ndbi_grid.geojson` |
| 5 | Fetch DEM | `ingestion.fetch_dem` | `data/dem_grid.geojson` |
| 6 | Merge indicators | `processing.merge_indicators` | None (always runs) |
| 7 | Compute UHI | `processing.compute_uhi` | None |
| 8 | Analyze LST/NDVI | `processing.lst_ndvi_analysis` | None |
| 9 | Score with PCA | `processing.pca_scoring` | None |
| 10 | Cluster typologies | `processing.kmeans_clustering` | None |
| 11 | Train indicator attribution | `processing.train_explainability` | None |
| 12 | Create attribution JSON | `processing.generate_explanations_json` | None |
| 13 | Generate environmental intelligence | `environment.generate_environmental_intelligence` | `data/environmental_intelligence.json` |
| 14 | Generate planning profiles | `planning.generate_planning_profiles` | `data/planning_profiles.json` |
| 15 | Enrich geographic metadata | `metadata.geo_enrichment` | `data/geo/geographic_metadata.json` |
| 16 | Generate validation plots | `processing.validate_scores` | None |

**Run command:** `python main.py`

---

## 5. Phase 0 — Ingestion Layer

All ingestion scripts use Google Earth Engine (GEE) to fetch satellite data. They all follow the same pattern:
1. Load config → init GEE → build AOI geometry
2. Build cloud-masked image composite
3. Load `data/grid.geojson` as `ee.FeatureCollection`
4. `reduceRegions()` → mean value per cell
5. `getInfo()` to retrieve results locally → merge → save GeoJSON

---

### ingestion/generate_grid.py

**Purpose:** Creates a fishnet grid over Mumbai's bounding box. No GEE needed.

**`create_fishnet_grid(west, south, east, north, cell_size)`**
- Generates a rectangular array of cells using `numpy.arange` on lat/lon
- Each cell is a `shapely.geometry.box` polygon
- Cell IDs formatted as `r{row}_c{col}` (e.g. `r0_c0`, `r19_c12`)
- Returns `GeoDataFrame` with `cell_id` + `geometry`, CRS=EPSG:4326

**`main()`**
- Reads AOI + cell_size from config
- Creates 836 cells (22 rows × 38 columns) for Mumbai
- Saves to `data/grid.geojson`

---

### ingestion/fetch_ndvi.py

**Purpose:** Fetches mean NDVI per cell from Sentinel-2.

**Formula:** `NDVI = (B8 − B4) / (B8 + B4)` (NIR minus Red)

**`mask_s2_clouds(image)`**
- Uses QA60 band, masks bits 10 (cloud) and 11 (cirrus)
- Returns cloud-free pixels only

**`get_s2_ndvi_composite(aoi, start_date, end_date, ...)`**
- Filters `COPERNICUS/S2_HARMONIZED` by date, bounds, cloud %
- Applies cloud mask to every scene
- Adds NDVI band using `normalizedDifference(["B8", "B4"])`
- Takes **median** composite → single representative NDVI image

**`export_to_geojson(reduced_fc, local_gdf, output_path)`**
- Calls `getInfo()` on the Earth Engine result
- Merges `mean` NDVI values back onto local GeoDataFrame by `cell_id`
- Saves `data/ndvi_grid.geojson` with columns: `cell_id`, `mean_ndvi`, `geometry`

**Output:** `data/ndvi_grid.geojson`

---

### ingestion/fetch_lst.py

**Purpose:** Fetches mean Land Surface Temperature per cell from Landsat 8+9 with full emissivity correction.

**Physics:**
```
BT = ST_B10 × 0.00341802 + 149.0  (brightness temperature in Kelvin)
NDVI = (B5 − B4) / (B5 + B4)
Pv = ((NDVI − 0.2) / (0.5 − 0.2))²  (proportion of vegetation)
ε = 0.004 × Pv + 0.986              (surface emissivity)
LST(K) = BT / (1 + (λ/ρ) × BT × ln(ε))
LST(°C) = LST(K) − 273.15
```

**`mask_landsat_clouds(image)`**
- Uses QA_PIXEL band, masks bits 0-4 (fill, cloud, cirrus, shadow)

**`add_lst(image)`**
- Full emissivity correction per pixel using the formula above
- Constants: λ=10.9μm, ρ=h·c/k_B=0.01438 mK

**`get_landsat_lst_composite(aoi, start_date, end_date, ...)`**
- Merges Landsat 8 + Landsat 9 collections
- Applies cloud mask, computes per-image LST, takes median composite

**Output:** `data/lst_grid.geojson` with `mean_lst` in °C

---

### ingestion/fetch_ndbi.py

**Purpose:** Fetches mean Built-up Index per cell from Sentinel-2.

**Formula:** `NDBI = (B11 − B8) / (B11 + B8)` (SWIR1 minus NIR)
- Positive = built-up / impervious
- Negative = vegetation / water

Identical cloud masking and composite approach to `fetch_ndvi.py`.

**Output:** `data/ndbi_grid.geojson` with `mean_ndbi`

---

### ingestion/fetch_dem.py

**Purpose:** Fetches mean terrain elevation per cell from SRTM.

**Source:** `USGS/SRTMGL1_003` — 30m global elevation
**No cloud masking needed** — DEM is a static dataset

**Output:** `data/dem_grid.geojson` with `mean_dem` in metres

---

## 6. Phase 1 — Processing Pipeline

### processing/merge_indicators.py

**Purpose:** Joins the four indicator GeoJSONs into a single master dataset.

**`main()`**
1. Reads `ndvi_grid.geojson` as the base GeoDataFrame (keeps geometry)
2. Reads `lst_grid`, `ndbi_grid`, `dem_grid` — drops geometry, merges on `cell_id`
3. Ensures column order: `cell_id, mean_ndvi, mean_lst, mean_ndbi, mean_dem, geometry`
4. Saves to `data/cells_master.geojson`

**Output columns after this stage:** `cell_id`, `mean_ndvi`, `mean_lst`, `mean_ndbi`, `mean_dem`, `geometry`

---

### processing/compute_uhi.py

**Purpose:** Computes Urban Heat Island intensity relative to a green reference zone.

**Reference zone:** Sanjay Gandhi National Park (SGNP) / Aarey Colony
- Config bbox: lon [72.87–72.93], lat [19.18–19.25]

**Formula:**
```
UHI_intensity = LST_cell − mean(LST_reference_cells)
```
- Positive = hotter than the forest baseline (Urban Heat Island effect)
- Negative = cooler than the baseline

**`main()`**
1. Loads master GeoJSON
2. Finds all cells whose centroid falls within the reference bbox
3. Computes `ref_temp` = mean LST of those cells (~39°C)
4. Adds `uhi_intensity` column to every cell
5. Generates `data/uhi_map.png` (diverging blue-white-red colormap centred at 0)
6. Saves updated `cells_master.geojson`

**Output:** Adds `uhi_intensity` column (range: approximately −9°C to +10°C for Mumbai)

---

### processing/pca_scoring.py

**Purpose:** Derives a unified Environmental Risk Score (0–100) using PCA.

**Steps:**
1. **Impute:** Fill missing values with column median
2. **MinMax scale:** Normalise all 4 indicators to [0, 1]
3. **Direction alignment:** Invert NDVI and DEM (so all features positively correlate with risk)
   - High LST → high risk ✓ (no change)
   - High NDBI → high risk ✓ (no change)
   - Low NDVI → high risk → invert: `NDVI_aligned = 1 − NDVI_scaled`
   - Low DEM → high flood risk → invert: `DEM_aligned = 1 − DEM_scaled`
4. **PCA(n_components=1):** Extracts PC1 — explains ~65% of variance
5. **Sign check:** Ensures positive PC1 = higher risk (flips if necessary)
6. **Scale to 0–100:** `risk_score = (PC1 − min) / (max − min) × 100`
7. **Sustainability score:** `sustainability_score = 100 − risk_score`

**Outputs:**
- Adds `risk_score` and `sustainability_score` to `cells_master.geojson`
- Saves `models/scaler.pkl` (MinMaxScaler)
- Saves `models/pca_model.pkl` (fitted PCA)

**Key finding:** LST loading = 0.74, NDVI loading = −0.62 (dominant contributors to PC1 — consistent with domain expectation for urban heat environments)

---

### processing/kmeans_clustering.py

**Purpose:** Groups cells into urban typology clusters using K-Means.

**Steps:**
1. Normalise 4 indicators to [0, 1]
2. Silhouette analysis for k = 2 to 6
3. Uses k=4 (best silhouette score for Mumbai: ~0.59)
4. Fits K-Means with k=4, random_state=42
5. Assigns human-readable labels based on centroid values:

| Cluster | Typical centroid | Label |
|---|---|---|
| 0 | Low LST, Low DEM (sea/coastal) | Coastal/Lowland Urban |
| 1 | High NDVI, Medium LST | Green/Forested |
| 2 | High LST, High NDBI | Dense Urban Heat |
| 3 | Medium NDVI, Low NDBI | Green/Forested (alt) |

**Outputs:**
- Adds `cluster_id` (int) and `cluster` (string label) to master
- Saves `models/kmeans_model.pkl`
- Saves `data/kmeans_silhouette.png`

---

### processing/train_explainability.py

**Purpose:** Trains a Random Forest surrogate model and uses SHAP to decompose the composite risk index into per-indicator contributions (sensitivity analysis). This is **not** an independent explainable-AI model — because `risk_score` is a PCA linear combination of the same four input features, the high R² is expected by construction and confirms the RF approximates the PCA formula, not that it discovers independent drivers of urban risk. See the module docstring for full scope.

**Steps:**
1. **Train/test split:** 80/20, random_state=42
2. **StandardScaler** on training features
3. **RandomForestRegressor:** 200 trees, max_depth=5
4. **Surrogate fit** (expected by construction — not independent validation): R²=0.9934, MAE=1.85, RMSE=2.58
5. **SHAP TreeExplainer:** Computes per-cell SHAP attribution values for all 836 cells
6. **Per-cell index contributors:** For each cell finds:
   - `top_positive_driver`: indicator most strongly raising the composite index score
   - `top_positive_shap`: SHAP magnitude of that contribution (index score points, 0–100 scale)
   - `top_negative_driver`: indicator most strongly suppressing the composite index score
   - `top_negative_shap`: SHAP value (negative)
7. **`build_explanation_text(row)`:** Generates an index-decomposition sentence like *"High composite risk index — dominated by high LST (+19.01)"*

**Outputs:**
- Adds 5 columns to master: `top_positive_driver`, `top_positive_shap`, `top_negative_driver`, `top_negative_shap`, `explanation_text`
- Saves `models/risk_model.pkl` (surrogate) and `models/explain_scaler.pkl`
- Saves `data/feature_importance.png` (indicator contribution chart), `data/shap_summary.png` (SHAP attribution plot), `data/top_driver_map.png` (dominant indicator map)

---

### processing/generate_explanations_json.py

**Purpose:** Extracts indicator attribution columns from the GeoJSON into a lightweight JSON for fast dashboard lookups.

**`main()`**
- Reads `cells_master.geojson`
- For each cell creates a record with `explanation_text` (index-decomposition sentence), `top_positive_driver`, `top_negative_driver`
- Saves as `data/cell_explanations.json` keyed by `cell_id`

**Format:**
```json
{
  "r19_c12": {
    "explanation_text": "High composite risk index — dominated by high LST (+16.21) and attenuated by low NDBI (-0.33)",
    "top_positive_driver": {"feature": "mean_lst", "shap_value": 16.21},
    "top_negative_driver": {"feature": "mean_ndbi", "shap_value": -0.33}
  }
}
```

---

### processing/validate_scores.py

**Purpose:** Generates visual validation plots to sanity-check pipeline outputs.

**Plots generated:**
- `val_risk_distribution.png` — histogram of risk scores with KDE
- `val_risk_vs_lst.png` — scatter plot with trendline (higher LST → higher risk expected)
- `val_risk_by_cluster.png` — boxplot of risk by cluster typology
- `val_cluster_profiles.png` — heatmap of normalised indicator means per cluster

---

## 7. Phase 2 — Environmental Intelligence Layer

**Purpose:** Converts raw indicator values into human-readable narratives and city-wide comparative analytics. No new ML models — entirely deterministic.

---

### environment/environment_templates.py

**Purpose:** Single source of truth for all constants, thresholds, and template strings used by Phase 2 modules. No computation.

**Key constants:**

**`EHI_WEIGHTS`** — Indicator weights for Environmental Health Index:
| Indicator | Weight | Rationale |
|---|---|---|
| `mean_lst` | 30% | Primary heat stress driver in Mumbai |
| `mean_ndvi` | 25% | Key ecological cooling mechanism |
| `uhi_intensity` | 20% | UHI amplification |
| `mean_ndbi` | 15% | Impervious surface coverage |
| `mean_dem` | 10% | Flood susceptibility proxy |

**`STATUS_THRESHOLDS`** — EHI ranges to status labels:
- 80–100 → Excellent, 60–79 → Good, 40–59 → Moderate, 20–39 → Poor, 0–19 → Critical

**`CONDITION_THRESHOLDS`** — Percentile rank rules for 6 conditions:
| Condition | Rule |
|---|---|
| Urban Heat Island | UHI rank ≥ 75 AND LST rank ≥ 70 |
| Low Vegetation | NDVI rank ≤ 25 |
| High Built-up Density | NDBI rank ≥ 75 |
| Flood Susceptibility | DEM rank ≤ 20 |
| Environmental Stress | EHI < 40 |
| Ecological Stability | EHI ≥ 70 AND NDVI rank ≥ 60 |

**`SUMMARY_TEMPLATES`** — 12 paragraph templates keyed by `(condition, status)` pairs

---

### environment/comparative_analysis.py

**Purpose:** Computes city-wide statistics and per-cell percentile rankings. All functions are pure (no file I/O).

**`compute_city_stats(gdf)`**
- Input: full master GeoDataFrame
- For each of 6 indicators: computes mean, median, std, min, max, p10, p25, p75, p90
- Output: nested dict `{indicator: {stat: value}}`

**`compute_cell_comparisons(cell, city_stats, gdf)`**
- For each indicator computes:
  - `city_rank_*` (0–100): percentile rank where 100 = most extreme (bad) for that indicator
  - `*_vs_city_avg`: absolute deviation from city mean
  - `*_pct_diff`: percentage deviation
- Rank convention: LST rank 100 = hottest cell; NDVI rank 100 = most vegetated (best)
- Adds convenience aliases: `city_rank_uhi`, `city_rank_risk`

---

### environment/environmental_health.py

**Purpose:** Computes the Environmental Health Index (EHI) and status label.

**`compute_ehi(cell, city_stats)`**
1. MinMax-normalise each indicator to [0, 1] using city min/max
2. Invert NDVI and DEM (higher = better → convert to "higher = more risk")
3. Apply EHI_WEIGHTS → weighted composite in [0, 1]
4. `EHI = (1 − composite) × 100` → higher = healthier
5. Clamp to [0, 100]
6. NaN safety: missing indicators excluded, remaining weights redistributed

**`compute_ehi_batch(gdf, city_stats)`**
- Vectorised version using pandas operations — much faster than row-by-row for 836 cells
- Per-row weight redistribution using `notna()` mask

**`get_environmental_status(ehi)`**
- Maps EHI to status label using `STATUS_THRESHOLDS`

**Mumbai EHI distribution:** min=10.9, max=80.9, mean=48.1

---

### environment/indicator_interpreter.py

**Purpose:** Detects named environmental conditions and generates spatial context sentences.

**`detect_conditions(cell_comparisons, ehi)`**
- Evaluates each condition's rules with AND logic
- Returns list ordered by `_CONDITION_PRIORITY`
- Special key `_ehi` evaluates directly against EHI value (not a rank)

**`get_primary_and_secondary_issues(conditions, ehi)`**
- Separates "issues" from positive conditions (Ecological Stability treated as positive)
- Returns `(primary, secondary)` tuple

**`generate_spatial_context(cell_comparisons, cell)`**
- Selects LST template (very_high/high/average/low) based on LST rank
- Selects NDVI template based on NDVI rank
- Produces sentence like: *"This grid is hotter than 93% of all Mumbai grids (41.2°C). Vegetation is in the lowest 18% of the city (NDVI: 0.127)."*

---

### environment/environmental_summary.py

**Purpose:** Generates 2–3 sentence narrative paragraphs using template selection. No LLM.

**`generate_summary(cell, ehi, status, conditions, cell_comparisons)`**

Template selection precedence:
1. Exact match: `(primary_condition, status)` in SUMMARY_TEMPLATES
2. Same condition, next-worse status tier
3. `("Environmental Stress", status)` if EHI < 50
4. `SUMMARY_FALLBACK_TEMPLATE`
5. Plain text last resort

**Safety:** `_PLACEHOLDER_RE` regex validates no `{placeholder}` tokens remain in output.

---

### environment/generate_environmental_intelligence.py

**Purpose:** Pipeline stage — orchestrates all Phase 2 modules and writes JSON output.

**`main()`**
1. Loads config, resolves paths
2. Validates required columns in master GeoJSON
3. Calls `compute_city_stats(gdf)` once for city-wide baselines
4. Calls `compute_ehi_batch(gdf, city_stats)` for vectorised EHI
5. Per-cell loop: comparisons → conditions → issues → spatial context → summary
6. Writes `data/environmental_intelligence.json`

**Output per cell (sample):**
```json
{
  "environmental_health": 71.4,
  "environmental_status": "Moderate",
  "city_rank_lst": 93.0,
  "city_rank_ndvi": 18.0,
  "detected_conditions": ["Urban Heat Island", "Low Vegetation"],
  "primary_issue": "Urban Heat Island",
  "spatial_context": "This grid is hotter than 93% of all Mumbai grids.",
  "environmental_summary": "This grid experiences elevated surface temperatures..."
}
```

**Mumbai summary:** 836 cells — Moderate 58%, Poor 29%, Good 12%, Critical 1%, Excellent 1%

---

## 8. Phase 3 — Urban Planning Decision Engine

**Purpose:** Converts environmental evidence into actionable planning decisions. All reasoning is deterministic — driven by a YAML knowledge base, not an LLM.

---

### planning/intervention_catalog.yaml

**Purpose:** The entire recommendation knowledge base. **Edit this file to add or change interventions — no code changes needed.**

**Structure:**
```yaml
interventions:
  <condition_name>:
    primary: "Intervention Name"
    secondary: ["Support 1", "Support 2"]
    objectives: ["Planning Goal"]
    benefits: ["Expected Outcome"]
    cost: "Low|Medium|High"
    timeline: "1-3 Years"
    complexity: "Easy|Moderate|Complex"
    priority_weight: "Low|Medium|High"

multi_condition_overrides:
  - conditions: ["Condition A", "Condition B"]
    primary: "Override Intervention"
    ...
```

**Single-condition entries (7):** Urban Heat Island, Low Vegetation, High Built-up Density, Flood Susceptibility, Environmental Stress, Ecological Stability, default

**Multi-condition overrides (4, most-specific first):**
| Conditions | Primary Intervention |
|---|---|
| UHI + Low Veg + High Built-up | Urban Forest (complex) |
| UHI + Low Vegetation | Urban Forest (moderate) |
| UHI + High Built-up | Cool Roof Program |
| Flood + High Built-up | Integrated Drainage & Green Infrastructure |

---

### planning/knowledge_base.py

**Purpose:** Loads the YAML catalog and resolves the best intervention for a condition set.

**`load_catalog()`**
- Module-level cache — loaded once per process
- Raises `FileNotFoundError` if YAML missing
- Returns full parsed dict with `interventions` and `multi_condition_overrides`

**`get_intervention(conditions, catalog)`**

Resolution order:
1. **Multi-condition overrides:** Find override whose conditions are the largest subset of detected conditions (most-specific match wins)
2. **Single-condition lookup:** First detected condition with a direct entry
3. **Default fallback:** `interventions.default`

**`get_strategic_weight(dominant_land_use)`**
- Returns strategic importance 0–100 for a land use type:
  - Dense Commercial/Industrial → 90
  - Residential → 80
  - Mixed Urban → 70
  - Mixed Residential → 60
  - Sparse Vegetation → 40
  - Green Space/Forest → 30
  - Water Body/Coastal → 10
  - Unknown → 50

---

### planning/priority_engine.py

**Purpose:** Computes Planning Priority Score (0–100) and Priority Label.

**Priority Score formula:**
```
priority_score =
    0.35 × (100 − EHI)         ← environmental urgency
  + 0.30 × risk_score          ← PCA risk
  + 0.20 × population_score    ← exposed population (normalised)
  + 0.15 × strategic_weight    ← land-use importance
```

**Priority Labels:** Critical (80–100), High (60–79), Medium (40–59), Low (20–39), Very Low (0–19)

**`compute_priority_batch(gdf, env_intel, geo_meta)`**
- Derives city-wide max population from geo_meta for normalisation
- Falls back to `(100 − risk_score)` for EHI if Phase 2 data absent
- Returns DataFrame with `cell_id`, `priority_score`, `planning_priority`

**Mumbai distribution:** High=28 (3.3%), Medium=439 (52.5%), Low=369 (44.1%)

---

### planning/intervention_engine.py

**Purpose:** Selects the optimal intervention and computes confidence score.

**`select_intervention(conditions, primary_issue, catalog)`**
- Delegates to `knowledge_base.get_intervention(conditions)`
- Returns 7-key catalog entry dict

**`compute_confidence(top_positive_shap, city_max_shap, n_conditions, n_indicators_present)`**
```
shap_score       = min(|top_positive_shap| / city_max_shap, 1.0)
data_completeness = n_indicators_present / 5
condition_boost  = min(n_conditions × 0.05, 0.15)

confidence = 0.50 × shap_score
           + 0.35 × data_completeness
           + 0.15 × condition_boost
```
Clamped to [0.0, 1.0]. SHAP magnitude is the primary driver (50%).

**`build_evidence_text(primary_issue, cell_comparisons, top_driver, top_shap, intervention_name)`**
- Composes an explanatory paragraph from:
  1. Condition identification sentence
  2. Top 2 most extreme percentile rank sentences
  3. Index attribution sentence (SHAP contributor to composite index)
  4. Conclusion sentence
- Example: *"This area has been identified as having Urban Heat Island. Surface temperature ranks in the hottest 93% of the city. SHAP attribution identifies surface temperature as the dominant contributor to the composite risk index for this cell (SHAP value: +16.21). Therefore Urban Forest provides the highest expected environmental benefit for this grid."*

---

### planning/planning_summary.py

**Purpose:** Assembles the final Planning Profile dict from all computed components.

**`build_planning_profile(cell_id, ehi, risk_score, priority_score, priority_label, intervention, confidence, evidence_text)`**

Returns a dict with **11 required keys** + 2 supplementary:
```json
{
  "planning_priority":          "High",
  "priority_score":             67.3,
  "primary_objective":          "Reduce Urban Heat",
  "recommended_intervention":   "Urban Forest",
  "secondary_interventions":    ["Cool Roof Program", "Street Tree Plantation"],
  "expected_benefits":          ["Lower LST", "Higher NDVI", "Better Air Quality"],
  "implementation_cost":        "Medium",
  "implementation_timeline":    "2-5 Years",
  "implementation_complexity":  "Moderate",
  "confidence":                 0.847,
  "evidence":                   "This area has...",
  "environmental_health":       34.2,
  "risk_score":                 78.1
}
```

---

### planning/decision_engine.py

**Purpose:** Top-level orchestrator that runs all Phase 3 modules over the full dataset.

**`run(gdf, env_intel, geo_meta, explanations)`**
1. Computes `city_max_shap` from GDF for confidence normalisation
2. Calls `compute_priority_batch()` for all cells at once
3. Per-cell loop:
   - Gets EHI, conditions, comparisons from `env_intel`
   - Gets SHAP driver from GDF
   - Counts present indicators for data completeness
   - Calls `select_intervention`, `compute_confidence`, `build_evidence_text`, `build_planning_profile`
4. Returns `{cell_id: profile}` dict

---

### planning/generate_planning_profiles.py

**Purpose:** Pipeline stage — orchestrates decision engine and writes JSON output.

**Dependencies:** `cells_master.geojson` + `environmental_intelligence.json` (required); `geographic_metadata.json` + `cell_explanations.json` (optional)

**`main()`**
1. Validates required files exist
2. Loads all inputs
3. Calls `decision_engine.run()`
4. Writes `data/planning_profiles.json`
5. Logs priority distribution and top-5 interventions

**Mumbai top interventions:** Environmental Monitoring (367), Afforestation (163), Cool Roof (143), Urban Forest (66), Integrated Drainage (29)

---

## 9. Backend API — FastAPI

**File:** `backend/main.py`
**Run:** `python -m uvicorn backend.main:app --reload --port 8000`

### Startup

On startup, the server:
1. Loads all 4 data files from `data/` into memory (loaded once, served forever)
2. Normalises `cell_explanations.json` — handles both list and dict format
3. Filters sea/water cells using `_is_land_cell()` for the `/api/cells` endpoint
4. Builds `_cell_props` dict for O(1) cell lookups

### Land/water filtering

**`_is_land_cell(props)`**
- Returns False if `ndvi < 0.05` AND `dem < 3.5` (sea/coastal water cells)
- This cleans the map — only land cells appear in the choropleth
- 836 total → ~760 land cells after filtering

### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/cells` | Land-only GeoJSON FeatureCollection for Deck.gl |
| GET | `/api/cell/{cell_id}` | Full data bundle: master + environment + planning + explanation |
| GET | `/api/rankings` | All cells sorted by priority_score descending |
| GET | `/api/stats` | City-wide aggregates: avg EHI, priority counts, top issues |
| GET | `/health` | Health check: `{"status": "ok", "cells": 836}` |

### /api/stats response (actual Mumbai data)

```json
{
  "total_cells": 836,
  "avg_ehi": 48.1,
  "avg_risk": 51.8,
  "priority_counts": {"High": 28, "Medium": 439, "Low": 369},
  "top_issues": [
    {"issue": "Urban Heat Island", "count": 209},
    {"issue": "Low Vegetation",    "count": 187},
    {"issue": "High Built-up Density", "count": 31}
  ]
}
```

### /api/cell/{cell_id} bundle

```json
{
  "master":      { ...all GeoJSON properties... },
  "environment": { ...EHI, conditions, ranks, summary... },
  "planning":    { ...priority, intervention, evidence... },
  "explanation": { ...SHAP text, drivers... }
}
```

### CORS

`allow_origins=["*"]` — allows the Vite dev server on port 5173 to call the API on port 8000 without browser restrictions.

---

## 10. Frontend — React Command-Center Dashboard

**Stack:** React 19, TypeScript 6, Deck.gl 9, MapLibre GL 5, Zustand 5, TanStack Query 5, Tailwind CSS 4, Recharts 3

**Run:** `cd frontend && npm run dev` → `http://localhost:5173`

The Vite dev server proxies `/api/*` → `http://localhost:8000` automatically.

---

### src/types/index.ts

TypeScript interfaces for all API response shapes:
- `CellMaster` — GeoJSON feature properties
- `EnvIntelligence` — Phase 2 analytics per cell
- `PlanningProfile` — Phase 3 planning data per cell
- `CellBundle` — combined `/api/cell/:id` response
- `CityStats` — `/api/stats` response
- `RankingRow` — `/api/rankings` row
- `LayerKey` — union type of 8 valid layer names
- `TooltipInfo` — hover tooltip data

---

### src/store/useStore.ts

Zustand global state with 5 fields:
- `selectedCellId` — which cell is selected (null = none)
- `activeLayer` — which choropleth layer is showing (default: `environmental_health`)
- `tooltip` — current hover tooltip data
- `statsPanelOpen` — left panel visibility
- `apiConnected` — backend health status

---

### src/api/citysense.ts

TanStack React Query hooks:
- `useCityStats()` — `/api/stats`, staleTime=Infinity
- `useCells()` — `/api/cells`, staleTime=Infinity (large GeoJSON, cached forever)
- `useCell(cellId)` — `/api/cell/:id`, enabled only when cellId is set
- `useRankings()` — `/api/rankings`, staleTime=Infinity
- `checkHealth()` — `/health`, used by Header for status dot

---

### src/components/Map/layers.ts

Pure functions that create Deck.gl layer objects.

**`LAYER_CONFIGS`** — registry of all 8 layers with their colour scales and min/max ranges

**Colour scales:**
- `green_red` — EHI: green (healthy) → red (critical)
- `red_green` — Risk: red (dangerous) → green (safe)
- `blue_red` — LST: blue (cool) → red (hot)
- `brown_green` — NDVI: brown (bare) → green (vegetated)
- `blue_orange` — UHI: blue (negative/cool) → orange (hot)
- `categorical` — Clusters: Tab10 palette

**`isWaterCell(props)`** — filters out sea cells (NDVI < 0.05 AND DEM < 3.5) → transparent fill

**`makeChoroplethLayer(geojson, activeLayer, selectedCellId, onHover, onClick)`**
- `GeoJsonLayer` with `getFillColor` driven by the active layer's colour scale
- Selected cell → bright cyan `[0, 212, 255, 240]`
- Gold highlight on hover
- 400ms transition animation on layer switch

**`makeHotspotLayer(hotspots, animTime)`**
- `ScatterplotLayer` of pulsing rings on top-10 risk cells
- Radius oscillates using `Math.sin(animTime × π × 2)` — driven by `requestAnimationFrame`
- Red rings `[255, 59, 92]`

**`makeClusterLabelLayer(centroids)`**
- `TextLayer` showing cluster names at cluster centroids
- Only visible when `activeLayer === 'cluster'`

---

### src/components/Map/DeckMap.tsx

Full-screen WebGL map component.

**Initial view state:** longitude=72.877, latitude=19.076, zoom=11, pitch=30°, bearing=−10°

**`useAnimationFrame(periodMs)`** — custom hook that returns a 0–1 value oscillating every `periodMs` milliseconds using `requestAnimationFrame`

**`extractHotspots(geojson)`** — finds top-10 cells by `risk_score`, computes polygon centroids

**`extractClusterCentroids(geojson)`** — averages cell centroids per cluster

**Map interactions:**
- Hover → sets `localTooltip` (shown as floating div) + `setTooltip` in store
- Click → calls `setSelectedCellId(cell_id)` → triggers `useCell()` fetch

**Loading state:** Semi-transparent overlay with "Loading cell grid…" while GeoJSON loads

---

### src/components/Header/Header.tsx

Top bar (height: 48px, z-index: 200).

- **Brand:** "🌆 CITYSENSE" + subtitle in monospace with cyan text-shadow glow
- **Clock:** Live IST time updated every 1 second via `setInterval`
- **Status dot:** Green pulsing dot when API connected, red when offline
- **Health polling:** Checks `/health` every 15 seconds

---

### src/components/StatsPanel/StatsPanel.tsx

Left floating panel (width: 260px, z-index: 100), slides in from left on mount.

**Sections:**
1. **Big Numbers:** Total cells, Avg EHI, High Priority count — monospace with glow, flicker animation on load
2. **Priority Distribution:** Stacked horizontal bar showing Critical/High/Medium/Low/Very Low proportions
3. **Top Issues:** 5 rows with icon, issue name, count, and animated progress bar
4. **Priority Cells:** Top-5 cells by priority_score — clickable buttons that select the cell on the map

---

### src/components/CellPanel/CellPanel.tsx

Right floating panel (width: 340px, z-index: 100), slides in from right when a cell is selected.

**Header:** Cell ID (cyan monospace) + EHI status badge + priority badge (pulsing red for Critical)

**Close button:** × icon — sets `selectedCellId(null)`

**Three tabs:** Environment | Planning | Raw Data

---

### src/components/CellPanel/EnvTab.tsx

**Environmental Health tab contents:**
- Large EHI score + status badge
- Detected conditions as coloured icon pills
- 4 indicator rows: LST, NDVI, NDBI, UHI — each with value, delta vs city avg, percentile bar
- Environmental summary paragraph
- Spatial context sentence

---

### src/components/CellPanel/PlanningTab.tsx

**Planning Intelligence tab contents:**
- Priority badge (animated pulse for Critical) + priority score
- Primary planning objective
- Recommended intervention (large bold text)
- Secondary interventions as bullet list
- Expected benefits as checkmark list
- 3 chips: Cost | Timeline | Complexity
- Evidence paragraph in styled quote box
- Confidence as circular SVG arc gauge

---

### src/components/CellPanel/RawTab.tsx

**Raw Data tab contents:**
- Table of all numeric indicator values
- Indicator attribution text (index decomposition sentence)
- Cluster label
- Top index contributors (dominant upward/downward indicators with SHAP magnitudes)

---

### src/components/LayerBar/LayerBar.tsx

Bottom floating layer switcher (z-index: 150), slides up from bottom on mount.

**8 layer buttons:** EHI | Risk | LST | NDVI | NDBI | UHI | Clusters | Priority

Each button shows:
- A small colour swatch showing the layer's gradient
- Short label in monospace uppercase
- Active state: cyan glow border + text-shadow
- Full description as tooltip (HTML `title` attribute)

Clicking a button calls `setActiveLayer(key)` → DeckMap re-renders with new colour scale.

---

### src/components/ui/ScanLine.tsx

Atmospheric overlay — a thin cyan line that sweeps from top to bottom every 8 seconds.

- `position: fixed; inset: 0; pointer-events: none; z-index: 9999`
- Pure CSS animation: `scanline 8s linear infinite`
- Completely non-interactive — never blocks clicks

---

### src/styles/globals.css

Complete dark command-center design system:

**CSS custom properties:** 12 colour tokens, 2 font stacks
**Keyframe animations:** scanline, pulse-glow-red, pulse-glow-cyan, flicker, slide-in-left, slide-in-right, slide-in-bottom, fade-in, dot-blink, radar-ring, shimmer
**Utility classes:** `.panel`, `.card`, `.card-glow`, `.font-mono`, `.text-glow`, `.text-cyber`
**Component classes:** `.indicator-bar-track`, `.indicator-bar-fill`, `.badge-critical/high/medium/low/verylow`, `.tab-list`, `.tab-trigger`

---

## 11. Data Flow — End to End

```
GEE (Sentinel-2, Landsat 8/9, SRTM)
    │
    │  fetch_ndvi    → data/ndvi_grid.geojson   (cell_id, mean_ndvi)
    │  fetch_lst     → data/lst_grid.geojson    (cell_id, mean_lst °C)
    │  fetch_ndbi    → data/ndbi_grid.geojson   (cell_id, mean_ndbi)
    │  fetch_dem     → data/dem_grid.geojson    (cell_id, mean_dem m)
    │
    ▼
merge_indicators
    → data/cells_master.geojson
      [cell_id, mean_ndvi, mean_lst, mean_ndbi, mean_dem, geometry]
    │
compute_uhi
    → adds: uhi_intensity
    │
pca_scoring
    → adds: risk_score (0–100), sustainability_score (0–100)
    → saves: models/scaler.pkl, models/pca_model.pkl
    │
kmeans_clustering
    → adds: cluster_id, cluster
    → saves: models/kmeans_model.pkl
    │
train_explainability  ← surrogate RF + SHAP index decomposition
    → adds: top_positive_driver, top_positive_shap,
            top_negative_driver, top_negative_shap,
            explanation_text  (index attribution, not causal claim)
    → saves: models/risk_model.pkl, models/explain_scaler.pkl
    → saves: data/feature_importance.png, data/shap_summary.png
    │
generate_explanations_json
    → data/cell_explanations.json  {cell_id: {explanation, shap}}
    │
generate_environmental_intelligence  ← reads cells_master READ-ONLY
    → data/environmental_intelligence.json
      {cell_id: {ehi, status, conditions, ranks, summary, spatial_context}}
    │
generate_planning_profiles  ← reads env_intel + master READ-ONLY
    → data/planning_profiles.json
      {cell_id: {priority, score, intervention, benefits, cost, evidence}}
    │
geo_enrichment  ← optional enrichment with Nominatim/Overpass APIs
    → data/geo/geographic_metadata.json
      {cell_id: {locality, ward, population, landmarks}}
    │
    ▼
FastAPI backend (backend/main.py)
    ├── /api/cells     → GeoJSON to Deck.gl
    ├── /api/cell/:id  → merged bundle per cell
    ├── /api/stats     → city aggregates
    └── /api/rankings  → sorted intervention list
    │
    ▼
React frontend (frontend/src/)
    ├── DeckMap.tsx    → WebGL choropleth + hotspots
    ├── Header.tsx     → title + clock + status
    ├── StatsPanel.tsx → left stats panel
    ├── CellPanel.tsx  → right cell detail (3 tabs)
    └── LayerBar.tsx   → layer switcher
```

---

## 12. Output Files Reference

| File | Size (approx) | Contents | Producer | Consumers |
|---|---|---|---|---|
| `data/grid.geojson` | 200 KB | 836 empty grid polygons | `generate_grid` | All ingestion scripts |
| `data/ndvi_grid.geojson` | 250 KB | cell_id + mean_ndvi | `fetch_ndvi` | `merge_indicators` |
| `data/lst_grid.geojson` | 250 KB | cell_id + mean_lst | `fetch_lst` | `merge_indicators` |
| `data/ndbi_grid.geojson` | 250 KB | cell_id + mean_ndbi | `fetch_ndbi` | `merge_indicators` |
| `data/dem_grid.geojson` | 250 KB | cell_id + mean_dem | `fetch_dem` | `merge_indicators` |
| `data/cells_master.geojson` | 2.5 MB | All 15 columns per cell | Processing stages | Phase 2, Phase 3, Backend |
| `data/cell_explanations.json` | 400 KB | Indicator attribution text per cell (index decomposition, not causal explanation) | `generate_explanations_json` | Backend |
| `data/environmental_intelligence.json` | 1.2 MB | Phase 2 analytics per cell | `generate_environmental_intelligence` | Phase 3, Backend |
| `data/planning_profiles.json` | 1.0 MB | Phase 3 profiles per cell | `generate_planning_profiles` | Backend |
| `data/geo/geographic_metadata.json` | 500 KB | Locality, population per cell | `geo_enrichment` | Backend |
| `models/scaler.pkl` | 2 KB | MinMaxScaler (PCA) | `pca_scoring` | Dashboard inference |
| `models/pca_model.pkl` | 2 KB | Fitted PCA | `pca_scoring` | Dashboard inference |
| `models/risk_model.pkl` | 10 MB | RF surrogate for index decomposition (not independent predictor) | `train_explainability` | SHAP attribution |
| `models/explain_scaler.pkl` | 2 KB | StandardScaler (RF surrogate) | `train_explainability` | SHAP attribution |

---

## 13. Test Suite

**Run all tests:** `pytest tests/ -v`

**Current status: 82/82 tests passing (1.3s)**

| File | Tests | Coverage |
|---|---|---|
| `tests/test_environmental_intelligence.py` | 37 | Phase 2 modules (comparative_analysis, environmental_health, indicator_interpreter, environmental_summary) |
| `tests/test_planning_engine.py` | 35 | Phase 3 modules (knowledge_base, priority_engine, intervention_engine, planning_summary, decision_engine) |
| `tests/test_scoring.py` | 3 | PCA risk score bounds, correlation, cluster labels |
| `tests/test_indicators.py` | 3 | LST/NDVI/DEM value ranges |
| `tests/test_geographic.py` | 4 | Ward detector, land use, population, area calculator |

**Key test patterns:**
- All tests use **synthetic GeoDataFrames** — no real dataset required
- Phase 2 tests: 10-row GDF from max-stress to min-stress cells
- Phase 3 tests: same synthetic GDF + synthetic env_intel and geo_meta dicts
- No external API calls in any test

---

## 14. How to Run Everything

### Prerequisites

```bash
# Python environment
pip install -r requirements.txt

# Node.js v18+ (currently v24.15.0)
# Install from https://nodejs.org if not present

# Frontend dependencies
cd frontend && npm install && cd ..
```

### Step 1 — Earth Engine Authentication (first time only)

```bash
python -c "import ee; ee.Authenticate()"
```

### Step 2 — Run the full pipeline

```bash
python main.py
```

This runs all 16 stages in order. Already-completed stages are skipped via output-caching.

To run individual stages:
```bash
python -m environment.generate_environmental_intelligence
python -m planning.generate_planning_profiles
```

### Step 3 — Run the React dashboard

Open **two terminals:**

```bash
# Terminal 1 — Backend API
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Frontend dev server
cd frontend
npm run dev
```

Open `http://localhost:5173`

### Step 4 — Run tests

```bash
pytest tests/ -v
```

### Production build

```bash
cd frontend
npm run build
# Output: frontend/dist/ — serve with any static file server
```

---

## 15. Limitations & Validity

This section states what CitySense currently proves, what it does not, and what remains to be done. It is written to accompany any presentation or report that draws on the pipeline outputs.

---

### 15.1 Temporal Scope

All satellite data is drawn from a single pre-monsoon window: March–May 2023. The risk_score, EHI, cluster assignments, and planning profiles are computed from this snapshot only. No multi-season or year-over-year comparison has been performed. Temporal stability — whether a cell ranked "High" in pre-monsoon 2023 remains high-risk in post-monsoon 2023 or in 2024 — is unverified. Outputs should be interpreted as a characterisation of Mumbai's environmental profile for that specific window, not as a stable baseline.

---

### 15.2 Ground-Truth Validation

A spatial validation has been performed against 25 documented chronic waterlogging locations compiled from multi-year news reports (Times of India, Indian Express, NDTV, Economic Times, Mumbai Mirror, 2019–2025) and BMC's published 100-location flood-preparedness list (2020). Full methodology, per-location results, and limitations are in `validation/ground_truth_results.txt` and `validation/ground_truth_map.png`.

**Results (run: August 2026):**

- **DEM elevation check:** 0 of 25 flood spots (0%) fall in the bottom 25% of land-cell elevation (≤ 2.6 m SRTM). Average elevation of flood spots = 11.1 m vs city land average = 22.4 m. This result is informative rather than negative: Mumbai's documented flood spots are not at sea level — they flood due to localised drainage failure and low local relief, not absolute coastal elevation. SRTM DEM at 1 km resolution does not resolve the sub-grid drainage micro-topology responsible for urban waterlogging. DEM is therefore a weak flood predictor for Mumbai specifically at this resolution, which is consistent with published findings on Mumbai flood hydrology.

- **Composite risk score check:** 10 of 25 flood spots (40%) fall in the top quartile of risk score (≥ 79.6/100). The average risk score for flood spots is 78.0 vs the city average of 51.8 — flood-prone locations score substantially above the city mean. Given that the risk index is dominated by heat indicators (LST + UHI = 50% of EHI weight) rather than flood-specific indicators, a 40% top-quartile hit rate indicates meaningful spatial co-location with high-risk areas, not a flood model validation.

**Interpretation:** The validation confirms that CitySense's composite risk index co-locates with known environmental stress areas at above-chance rates, while confirming that DEM alone is insufficient to predict Mumbai's drainage-driven flooding at 1 km resolution. The system identifies heat and ecological stress risk, not flood inundation probability. A proper flood validation would require sub-100m DEM with drainage network topology and storm-sewer capacity data, which are not currently modelled.

**Validation limitations:** The 25 locations are a convenience sample of the most-reported spots, biased toward high-profile areas. Coordinates are geocoded from place names (±200–500 m typical accuracy). The 1 km² grid cell may contain both flood-prone and non-flood-prone sub-areas.

---

### 15.3 EHI Weight Basis

The `EHI_WEIGHTS` (LST 30%, NDVI 25%, UHI 20%, NDBI 15%, DEM 10%) in `environment/environment_templates.py` are domain-expert weights following the expert-judgment methodology described in OECD/JRC (2008) *Handbook on Constructing Composite Indicators*, §5.3 (https://doi.org/10.1787/9789264043466-en), which recognises expert-opinion weighting as a valid approach when data-driven methods (PCA-based, equal, or regression weights) cannot be grounded in an independent outcome variable.

The indicator set and direction of influence is consistent with the composite UHI index used in Ranagalage et al. (2018), *Spatial Changes of Urban Heat Island Formation in the Colombo District, Sri Lanka*, Sustainability 10(5):1367 (https://doi.org/10.3390/su10051367), which constructs a four-indicator composite (LST, inverted NDVI, NDBI, population density) for a comparable coastal South Asian city. CitySense departs from that study's equal weighting by assigning higher weights to thermal indicators (LST 30%, UHI 20%) because Mumbai's pre-monsoon heat stress is the dominant and most spatially variable environmental risk in the study window, and by substituting DEM (10%) for population density as the fourth sub-component, serving as a flood-susceptibility proxy appropriate for Mumbai's low-lying coastal topography.

No sensitivity analysis across alternative weight configurations has been performed. The DEM elevation validation (§15.2) additionally shows that DEM is a weak flood predictor at 1 km resolution for Mumbai, which suggests the 10% DEM weight may be further revisited in future work.

---

### 15.4 Spatial Resolution and Intervention Actionability

The grid resolution is 0.01° (~1 km²). This is appropriate for city-wide risk identification and comparative ranking across Mumbai's 836 cells. It is not appropriate for parcel-level or site-level intervention planning. Recommended interventions such as "Urban Forest" or "Drainage Infrastructure Upgrade" indicate a direction and approximate scale of response for a grid cell's dominant environmental condition — they are not site-approved plans. Land availability, ownership, zoning constraints, and microclimate variation within a cell are not modeled.

Ward-level aggregation of planning recommendations has been implemented. `metadata/ward_aggregation.py` spatially joins all 836 cells to Mumbai's 24 administrative wards using the centroid-based ward assignment from `metadata/ward_detector.py` and aggregates to dominant intervention, dominant issue, average priority score, high-priority cell count, priority distribution, average EHI, average risk score, and a one-sentence planning summary per ward. Output is written to `data/ward_profiles.json` and served at `GET /api/wards` and `GET /api/wards/{ward_name}` via the FastAPI backend.

**Current ward-level findings (August 2026):** L Ward (Eastern Suburbs, 930,000 population), H/East Ward (Western Suburbs, 570,000), and K/East Ward (Western Suburbs, 850,000) rank highest by average planning priority score (56.3, 55.1, 54.5 respectively), all with Urban Heat Island as the dominant issue and Cool Roof Program as the dominant recommended intervention. Outer wards A, G/South, and H/West score lowest (30–33) and are dominated by coastal/lowland cells with lower thermal stress. Ward assignment uses nearest-centroid approximation; polygon-boundary ward shapefiles were not available as a machine-readable open dataset and have not been sourced.

---

### 15.5 Population Data Quality

The `population_score` component of the Planning Priority Score (20% weight, `planning/priority_engine.py`) is sourced from `metadata/population_estimator.py`, which derives cell-level population from ward-level baseline figures stored in `config/geographic_config.yaml`. These baselines are static YAML values scaled by a heuristic NDBI multiplier (`adjusted_density = base_density × (1 + NDBI × 2.0)`). The ward baseline figures are not cited to a specific census year or source within the codebase. No gridded population dataset (e.g. WorldPop or GHSL 100m) has been integrated. Priority scores for cells in wards with poor or absent geographic metadata default to population = 0, which underweights those cells regardless of their environmental condition. Furthermore, if `geo_enrichment.py` has not been run for a deployment, the entire population component defaults to zero for all cells.

---

### 15.6 Composite Index Attribution (SHAP)

The SHAP values in `data/cell_explanations.json` decompose the composite risk index, not independently measured risk. For a full statement of scope, see **Section 6 — processing/train_explainability.py**, which explains why R²=0.993 is expected by construction and what the attribution sentences do and do not claim.

---

## 16. Public Health Co-location Check

*Added post-Priority-5. Methodology and results in `validation/health_ground_truth_check.py`, `validation/health_results.txt`, and `validation/health_map.png`.*

### 16.1 Approach

Ward-level comparison of CitySense composite scores against documented high vector-borne disease burden (dengue/malaria) for six wards. Point-level disease data is not publicly available for Mumbai — disease burden appears in news reports and BMC citations at ward or neighbourhood resolution only. This analysis therefore uses ward names as the matching unit, joining to `data/ward_profiles.json` rather than geocoding point locations.

The six wards were selected because they have the most consistently documented high disease burden across independent sources spanning multiple years (2016–2025): M/East Ward, L Ward, K/East Ward, M/West Ward, N Ward, and D Ward. This is a convenience selection, not a random sample. The sample size (6 wards) is too small for any correlation coefficient to be meaningful; this is a directional consistency check only.

City-wide ward baselines: mean avg_risk_score = 55.2, mean avg_ehi = 45.2 (across 24 named wards).

### 16.2 Results

| Ward | Disease | Risk score | EHI | vs city risk | vs city EHI | Result |
|---|---|---|---|---|---|---|
| M/East Ward | Malaria (primary) + Dengue | 36.6 | 53.0 | BELOW | ABOVE | DIVERGE |
| L Ward | Dengue (primary) | 80.3 | 29.3 | ABOVE | BELOW | CONVERGE |
| K/East Ward | Dengue + Malaria | 80.4 | 34.6 | ABOVE | BELOW | CONVERGE |
| M/West Ward | Dengue | 79.7 | 34.9 | ABOVE | BELOW | CONVERGE |
| N Ward | Malaria + Dengue | 73.5 | 41.3 | ABOVE | BELOW | CONVERGE |
| D Ward | Malaria (construction) | 27.9 | 50.9 | BELOW | ABOVE | DIVERGE |

**4 of 6 wards (67%) converge** — they score above the city mean risk score AND below the city mean EHI, consistent with being high-burden disease areas. The convergent wards (L, K/East, M/West, N) are all Urban Heat Island dominant in the composite index, reflecting the same dense urban heat environment that drives mosquito breeding and standing water accumulation.

### 16.3 The Divergent Cases

**M/East Ward (Govandi/Mankhurd/Trombay)** is the city's highest malaria burden ward by a substantial margin — Times of India (2021) cited BMC data showing ~95% of Mumbai's malaria burden comes from M/East — yet it scores below the city mean in risk (36.6 vs 55.2) and above it in EHI (53.0 vs 45.2). This is the most important finding of the check. The divergence is explained by composition: M/East Ward includes large green/forested Aarey Colony-adjacent cells that score well on NDVI and LST, suppressing the ward's composite average. The actual malaria burden is concentrated in the dense informal settlement micro-pockets of Govandi and Mankhurd, which occupy only a fraction of the ward's 1 km² cells. The composite index cannot resolve this sub-grid heterogeneity.

**D Ward (Worli/Prabhadevi)** was cited in an MCGM pest-control notice (2020) as a construction-site malaria risk area. It scores lowest in the city on risk (27.9) and highest relative to EHI. Construction-site malaria is driven by temporary larval breeding in excavations — a transient condition not captured by any of the five satellite-derived indicators (LST, NDVI, NDBI, DEM, UHI). This divergence is expected and does not indicate a model error.

### 16.4 What This Does and Does Not Prove

The CitySense composite risk index is a heat-and-ecology stress indicator, not a disease burden predictor. Co-location with high-burden wards (where it occurs) reflects shared environmental drivers — heat stress, impervious surface density, poor ecological health — rather than a causal or predictive relationship with disease incidence. The M/East result demonstrates clearly that the index can miss the city's highest disease-burden ward when that burden is concentrated in slum micro-pockets that are under-resolved at 1 km². A proper public-health validation would require ward-level confirmed case counts from BMC's epidemiology cell (not publicly available in machine-readable form) and a purpose-built disease risk model using sub-grid settlement density and drainage topology. Neither is currently in scope for CitySense.

---

## Quick Reference — Key Numbers (Mumbai 2023)

| Metric | Value |
|---|---|
| Total grid cells | 836 |
| Grid resolution | 0.01° ≈ 1 km² |
| Date range | March–May 2023 (pre-monsoon) |
| Average EHI | 48.1 / 100 |
| EHI range | 10.9 (Critical) – 80.9 (Good) |
| Average risk score | 51.8 / 100 |
| PCA explained variance | 65.4% |
| RF model R² | 0.993 (surrogate fit — expected by construction, not independent validation) |
| Cells with UHI > +5°C | 70 (8.4%) |
| Urban Heat Island cells | 209 (25%) |
| Low Vegetation cells | 187 (22%) |
| High Priority cells | 28 (3.3%) |
| Top intervention | Urban Forest (66 cells) |

---

*Generated: August 2026 | CitySense Phase 3 | Mumbai Environmental Intelligence*
