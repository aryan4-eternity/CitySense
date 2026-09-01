# CitySense — Complete Technical Documentation & Architecture Reference

*Comprehensive system reference covering internal mechanics, exact mathematical formulas, data schemas, module breakdown, API contracts, benchmark calibration, frontend architecture, and validation methodology.*

---

## Table of Contents
1. [System Overview & Operating Principles](#1-system-overview--operating-principles)
2. [End-to-End Data Pipeline Flow](#2-end-to-end-data-pipeline-flow)
3. [Ingestion Layer (`ingestion/`)](#3-ingestion-layer-ingestion)
4. [Processing & Machine Learning Layer (`processing/`)](#4-processing--machine-learning-layer-processing)
5. [Environmental Intelligence & Green-Urban Benchmarking (`environment/`)](#5-environmental-intelligence--green-urban-benchmarking-environment)
6. [Geographic Metadata & Enrichment (`metadata/`)](#6-geographic-metadata--enrichment-metadata)
7. [Planning Decision Engine (`planning/`)](#7-planning-decision-engine-planning)
8. [MMR Grid Expansion & Maintenance Scripts (`scripts/`)](#8-mmr-grid-expansion--maintenance-scripts-scripts)
9. [Core Utilities & Shared Helpers](#9-core-utilities--shared-helpers)
10. [Backend API Architecture (`backend/`)](#10-backend-api-architecture-backend)
11. [AI Copilot & Tool Calling (`backend/chat.py`)](#11-ai-copilot--tool-calling-backendchatpy)
12. [Frontend Architecture & Visualization (`frontend/`)](#12-frontend-architecture--visualization-frontend)
13. [Validation Methodology & Ground Truth (`validation/`)](#13-validation-methodology--ground-truth-validation)
14. [Configuration Reference](#14-configuration-reference)
15. [Deployment & Runbook](#15-deployment--runbook)
16. [Known Limitations & Epistemic Boundaries](#16-known-limitations--epistemic-boundaries)

---

## 1. System Overview & Operating Principles

CitySense converts raw Earth-observation and OpenStreetMap data into actionable urban planning intelligence for the **Mumbai Metropolitan Region (MMR)** — **1,663 cells** of approximately 1 km² each (0.01° grid), encompassing:
- Mumbai Island City (BMC South)
- Mumbai Suburban District (BMC West & East)
- Navi Mumbai & Panvel (NMMC / CIDCO / PMC)
- Thane Municipal Corporation (TMC)
- Kalyan-Dombivli & Extended MMR (KDMC / MBMC / VVMC)

### Core Operating Tenets
1. **Deterministic Analytics**: Every score is a transparent, reproducible formula over satellite indicators and geospatial network proximity. 
2. **Interpretability over Black-Box ML**: Machine learning is strictly constrained to dimensionality reduction (PCA for composite risk), urban typology clustering (K-Means), and post-hoc attribution (surrogate Random Forest with TreeSHAP). ML is **never** used for predictive forecasting.
3. **Green-Urban Neighborhood Benchmarking**: Urban cells are benchmarked against top-performing green urban neighborhoods rather than uninhabited rainforests (e.g., Sanjay Gandhi National Park) to prevent artificial score depression.
4. **Static Runtime Serving**: No live database or expensive re-computation occurs on user requests. Process outputs are saved as static GeoJSON/JSON and loaded into memory on backend startup.

---

## 2. End-to-End Data Pipeline Flow

```
[ Google Earth Engine (S2, L8/9, SRTM) ] ──┐
[ CHIRPS Precipitation (0.05°)          ] ──┼─► ingestion/* ─► data/grid.geojson + 5 raw indicator grids
[ OSM Overpass API (Water, Amenities)  ] ──┘

                      │
                      ▼
        processing/merge_indicators.py ────────► data/cells_master.geojson (Base Grid)
                      │
        ┌─────────────┼────────────────────────┬────────────────────────┐
        ▼             ▼                        ▼                        ▼
processing/    processing/              processing/              processing/
compute_uhi.py pca_scoring.py           kmeans_clustering.py     train_explainability.py
(UHI anomaly)  (risk_score, sustain)    (k=4 typologies)         (SHAP drivers, explanations)
        │             │                        │                        │
        └─────────────┴────────────────────────┼────────────────────────┘
                                               │
                                               ▼
                              metadata/geo_enrichment.py
                 (Locality, Ward, Zone, Landmarks, Land Use, Population)
                                               │
               ┌───────────────────────────────┼───────────────────────────────┐
               ▼                               ▼                               ▼
environment/benchmarks.py           metadata/drainage_proxy.py      metadata/infrastructure_access.py
(Compute G & W Anchors)                        │                               │
               │                               ▼                               ▼
environment/generate_environmental_   environment/generate_flood_     environment/generate_infrastructure_
intelligence.py (EHI Index)           susceptibility.py (FSI)         access.py (IAI)
               │                               │                               │
               └───────────────────────┬───────┴───────────────────────────────┘
                                       │
                                       ▼
                       environment/composite_burden.py
                       (Double-disadvantage Burden Index)
                                       │
                                       ▼
                     planning/generate_planning_profiles.py
                     (Priority Scoring + YAML Intervention Rules)
                                       │
                                       ▼
                     metadata/ward_aggregation.py
                     (24 Administrative Ward Aggregation)
                                       │
                                       ▼
                  [ backend/main.py: In-Memory Startup Load ]
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
           REST API Endpoints                     AI Chat Endpoint (/api/chat)
        (/api/cells, /api/cell/{id})            (Gemini 2.5 via OpenRouter Tools)
                    │                                     │
                    └──────────────────┬──────────────────┘
                                       │
                                       ▼
               [ frontend/: React 19 + Deck.gl Choropleth Map ]
```

The top-level orchestrator `main.py` executes stages in dependency order, automatically skipping completed stages if the declared output artifact already exists.

---

## 3. Ingestion Layer (`ingestion/`)

| Module | Source / Sensor | Reduction Scale | Target Output | Description |
|---|---|---|---|---|
| `generate_grid.py` | Bounding Box `[72.76, 18.82, 73.16, 19.36]` | 0.01° (~1 km²) | `data/grid.geojson` | Generates uniform fishnet polygon grid across the MMR. |
| `fetch_ndvi.py` | Sentinel-2 (`COPERNICUS/S2_HARMONIZED`) | 10 m | `data/ndvi_grid.geojson` | Computes mean NDVI for cloud-filtered (≤20%) pre-monsoon scenes. |
| `fetch_lst.py` | Landsat 8/9 Collection 2 Tier 1 L2 | 100 m | `data/lst_grid.geojson` | Converts Band 10 Thermal IR to Land Surface Temp in °C via split-window calibration. |
| `fetch_ndbi.py` | Sentinel-2 (SWIR & NIR bands) | 10 m | `data/ndbi_grid.geojson` | Normalized Difference Built-up Index (Impervious concrete proxy). |
| `fetch_dem.py` | NASA SRTM v3 (`USGS/SRTMGL1_003`) | 30 m | `data/dem_grid.geojson` | Mean digital elevation above sea level in meters. |
| `fetch_precipitation.py` | UCSB CHIRPS (0.05° gridded) | 5,000 m | `data/precipitation_grid.geojson` | Cumulative monsoon rainfall (June–September) in mm. |
| `validate_grid.py` | File check | N/A | `data/grid_validation.png` | Verifies fishnet geometry integrity and bounding coordinate closure. |
| `validate_ndvi.py` | Value range check | N/A | `data/ndvi_validation.png` | Asserts NDVI bounds [-1, 1] and checks distribution across vegetation zones. |
| `validate_lst.py` | Thermal check | N/A | `data/lst_validation.png` | Asserts physical temperature validity (20°C–55°C range for Mumbai pre-monsoon). |

---

## 4. Processing & Machine Learning Layer (`processing/`)

### 4.1 Merge & UHI Extraction
- **`merge_indicators.py`**: Spatial joins all indicator grids onto the base fishnet, generating `cells_master.geojson`.
- **`compute_uhi.py`**: Measures Urban Heat Island (UHI) intensity against the forested Sanjay Gandhi National Park baseline:
  $$\text{UHI\_Intensity}_i = \text{LST}_i - \overline{\text{LST}}_{\text{SGNP}}$$
  where $\overline{\text{LST}}_{\text{SGNP}}$ is the mean temperature of the reference box `[72.87, 19.18, 72.93, 19.25]`.

### 4.2 Composite PCA Risk Score (`pca_scoring.py`)
1. Missing values are median-imputed across the 4 core dimensions: LST, NDVI, NDBI, and DEM.
2. `MinMaxScaler` scales all features to $[0, 1]$.
3. Polarity inversion: Features are inverted so higher values always correspond to higher risk:
   - $\text{NDVI}_{\text{risk}} = 1.0 - \text{norm}(\text{NDVI})$
   - $\text{DEM}_{\text{risk}} = 1.0 - \text{norm}(\text{DEM})$
   - $\text{LST}_{\text{risk}} = \text{norm}(\text{LST})$
   - $\text{NDBI}_{\text{risk}} = \text{norm}(\text{NDBI})$
4. First Principal Component ($PC_1$) is extracted using `scikit-learn` PCA.
5. $PC_1$ is scaled to $[0, 100]$:
   $$\text{risk\_score} = \text{MinMax}(PC_1) \times 100$$
   $$\text{sustainability\_score} = 100.0 - \text{risk\_score}$$
6. Pickled models are persisted to `models/scaler.pkl` and `models/pca_risk.pkl`.

### 4.3 K-Means Typology Clustering (`kmeans_clustering.py`)
Applies K-Means ($k=4$) on normalized `[LST, NDVI, NDBI, DEM]`. Centroid inspection yields intuitive labels:
- **Cluster 0**: *Dense Hot Built-up* (High NDBI, High LST, Low NDVI)
- **Cluster 1**: *Cool Green Park / Forest* (High NDVI, Low LST, High DEM)
- **Cluster 2**: *Coastal Residential / Lowland* (Moderate NDVI, Low Elevation)
- **Cluster 3**: *Extreme Urban Heat / Industrial* (Peak LST, High NDBI, Low Vegetation)

### 4.4 Explainability via Surrogate Random Forest & SHAP (`train_explainability.py`)
- Fits a Random Forest surrogate regressor ($n=200, \text{max\_depth}=5$) to reconstruct the composite `risk_score` from raw inputs.
- TreeSHAP computes additive feature attributions for every cell:
  $$\text{risk\_score}_i = \phi_0 + \phi_{\text{LST}, i} + \phi_{\text{NDVI}, i} + \phi_{\text{NDBI}, i} + \phi_{\text{DEM}, i}$$
- Serializes top positive (risk-amplifying) and top negative (risk-mitigating) drivers to `data/cell_explanations.json`.

---

## 5. Environmental Intelligence & Green-Urban Benchmarking (`environment/`)

### 5.1 The Green-Urban Benchmark Recalibration (`benchmarks.py`)
To prevent the "Mostly Red Map" problem caused by benchmarking urban neighborhoods against a rainforest, CitySense computes Good ($G$) and Worst ($W$) anchor points:

1. Filter the 1,663 grid cells to **1,338 comparable urban cells** (excluding open water, SGNP core, and industrial/forest outlier clusters).
2. Select the top 10% highest-vegetation urban cells ($\text{NDVI} \ge 0.354, N=134$) as the Green-Urban Benchmark set.
3. Compute Good Anchor $G = \text{median}(\text{Benchmark Cells})$ and Worst Anchor $W = p_{95}(\text{All Cells})$ or $p_{5}(\text{All Cells})$.

#### Calibrated Benchmark Values (`data/benchmarks.json`)
| Indicator | Direction | Good Anchor ($G$) | Worst Anchor ($W$) | Description |
|---|---|---|---|---|
| `mean_lst` | Higher = Worse | **36.43 °C** | **43.33 °C** | Green urban residential vs 95th percentile heat |
| `uhi_intensity` | Higher = Worse | **6.23 °C** | **13.13 °C** | Green urban anomaly vs industrial peak |
| `mean_ndbi` | Higher = Worse | **0.094** | **0.318** | Vegetated urban density vs concrete core |
| `mean_ndvi` | Higher = Better | **0.3795** | **0.123** | Green canopy median vs paved 5th percentile |
| `mean_dem` | Higher = Better | **32.65 m** | **13.90 m** | Natural elevation median vs low-lying baseline |

### 5.2 Environmental Health Index (EHI) Formulation (`environmental_health.py`)
Normalized risk for indicator $i$ with value $v_i$:
$$\text{risk\_norm}_i = \begin{cases}
\text{clip}\left(\frac{v_i - G_i}{W_i - G_i}, 0, 1\right) & \text{if higher is worse (LST, UHI, NDBI)} \\
\text{clip}\left(\frac{G_i - v_i}{G_i - W_i}, 0, 1\right) & \text{if higher is better (NDVI, DEM)}
\end{cases}$$

Weighted composite index:
$$\text{EHI} = \left(1.0 - \frac{\sum w_i \cdot \text{risk\_norm}_i}{\sum w_i}\right) \times 100$$

**Weights**: LST (30%), NDVI (25%), UHI (20%), NDBI (15%), DEM (10%).

Status classification:
- **Excellent**: EHI $\ge 80$
- **Good**: $60 \le \text{EHI} < 80$
- **Moderate**: $40 \le \text{EHI} < 60$
- **Poor**: $20 \le \text{EHI} < 40$
- **Critical**: $\text{EHI} < 20$

### 5.3 Flood Susceptibility Index (FSI) (`flood_susceptibility.py`)
Provisional domain-weighted flood vulnerability model (out-of-sample evaluated):
$$\text{FSI} = 0.30 \cdot (1 - \text{norm}(\text{DEM})) + 0.30 \cdot \text{norm}(\text{Precip}) + 0.25 \cdot (1 - \text{norm}(\text{DrainDist})) + 0.15 \cdot \text{norm}(\text{NDBI})$$
Result is scaled to $[0, 100]$.

### 5.4 Infrastructure Access Index (IAI) (`infrastructure_access_index.py`)
Evaluates straight-line proximity to essential civic infrastructure:
$$\text{IAI} = 0.25 \cdot \text{Hosp}_{\text{acc}} + 0.20 \cdot \text{School}_{\text{acc}} + 0.20 \cdot \text{Park}_{\text{acc}} + 0.20 \cdot \text{Transit}_{\text{acc}} + 0.15 \cdot \text{InvCrowd}$$
Where distance scores are inverted ($\text{closer} = \text{higher access}$).

### 5.5 Composite Burden Score (`composite_burden.py`)
Identifies areas suffering double disadvantage:
$$\text{Burden} = 0.50 \cdot (100 - \text{EHI}) + 0.50 \cdot (100 - \text{IAI})$$

### 5.6 Supporting Submodules
- **`comparative_analysis.py`**: Computes city-wide percentiles, standard deviations, and relative rankings.
- **`indicator_interpreter.py`**: Evaluates condition rules (`Urban Heat Island`, `Low Vegetation`, `High Built-up Density`, `Flood Susceptibility`) and generates spatial context text.
- **`environmental_summary.py`**: Deterministic template builder that synthesizes human-readable cell summaries.
- **`environment_templates.py`**: Central repository for weighting constants, thresholds, and template strings.

---

## 6. Geographic Metadata & Enrichment (`metadata/`)

- **`locality_detector.py`**: Reverse geocodes coordinates to Mumbai locality names.
- **`ward_detector.py`**: Spatial point-in-polygon join assigning municipal wards (e.g., A Ward, K/West) and administrative zones.
- **`landmark_detector.py`**: Queries Overpass API for up to 5 landmarks within 1.5 km.
- **`land_use_classifier.py`**: Categorizes cells into `Dense Urban`, `Residential Vegetated`, `Industrial/Commercial`, or `Open/Parkland` based on NDBI/NDVI rules.
- **`population_estimator.py`**: Apportions ward-level 2024 population estimates down to individual 1 km² grid cells.
- **`drainage_proxy.py`**: Computes distance to nearest mapped drain/stream and drain feature count within 1.5 km.
- **`infrastructure_access.py`**: Measures nearest Euclidean distances to hospitals, schools, parks, and transit hubs.
- **`ward_aggregation.py`**: Aggregates cell metrics up to Mumbai's **24 municipal administrative wards**.

---

## 7. Planning Decision Engine (`planning/`)

### 7.1 Priority Score Formulation (`priority_engine.py`)
$$\text{Priority} = 0.35 \cdot (100 - \text{EHI}) + 0.30 \cdot \text{Risk} + 0.20 \cdot \left(\frac{\text{Pop}}{\text{Pop}_{\max}} \times 100\right) + 0.15 \cdot \text{StrategicWeight}$$

### 7.2 Intervention Catalog & Engine (`intervention_engine.py`)
Driven declaratively via `planning/intervention_catalog.yaml`. Interventions match on detected environmental conditions:
- `Urban Heat Island` $\rightarrow$ Urban Tree Canopy Expansion, Cool Roof Programs
- `Flood Susceptibility` $\rightarrow$ Permeable Pavements, Bioswale & Stormwater Retention
- `Low Vegetation + High Built-up` $\rightarrow$ Pocket Parks, Vertical Green Walls
- `Multi-condition overrides` trigger targeted composite strategies (e.g., Integrated Sponge City Retrofit).

### 7.3 Confidence Score Formulation
$$\text{Confidence} = 0.50 \cdot \min\left(\frac{|\phi_{\text{top}}|}{\phi_{\max}}, 1.0\right) + 0.35 \cdot \left(\frac{N_{\text{indicators}}}{5}\right) + 0.15 \cdot \min(N_{\text{cond}} \cdot 0.05, 0.15)$$

---

## 8. MMR Grid Expansion & Maintenance Scripts (`scripts/`)

| Script | Status | Purpose |
|---|---|---|
| `scripts/expand_mmr_grid.py` | **Active / Authoritative** | Extends base Mumbai grid to full 1,663 MMR cells spanning South Mumbai, Suburbs, Navi Mumbai, Thane, and KDMC. Preserves existing trained indicators and assigns locality metadata and regional attributes. |
| `scripts/generate_full_mmr_dataset.py` | **Deprecated / Reference** | Synthesizes an entire test MMR dataset from scratch. Retained for offline simulation reference. |
| `_sync_master.py` | **Utility** | Synchronizes derived index scores from JSON files back into `data/cells_master.geojson` feature properties. |
| `_review_check.py` | **Sanity check** | Verifies range validity and missing value counts across all output JSON tables. |

---

## 9. Core Utilities & Shared Helpers

- **`config_loader.py`**: Centralized loader providing safe, fresh dictionary mappings of `config/config.yaml` and resolving `project_path()`.
- **`utils.py`**: Configures multi-handler structured logging (`logs/pipeline.log` + stdout) and validates bounding box and date ranges.
- **`geo_utils.py`**: Provides `haversine_distance()`, WGS84 math, and Overpass API query execution with an automatic rate-limiting **circuit breaker** (skips queries after 5 consecutive failures).

---

## 10. Backend API Architecture (`backend/`)

FastAPI application loaded statically into memory at startup. CORS is enabled globally.

| Route | Method | Description |
|---|---|---|
| `/health` | GET | Uptime health check returning total loaded cell count (`{"status": "ok", "cells": 1663}`). |
| `/api/cells` | GET | Returns land-only GeoJSON FeatureCollection with all 11 choropleth layers merged. |
| `/api/cell/{cell_id}` | GET | Returns complete cell bundle (`master`, `environment`, `planning`, `explanation`, `flood`, `access`, `burden`, `geographic`). |
| `/api/rankings` | GET | Returns list of all cells sorted by planning priority score descending. |
| `/api/stats` | GET | City-wide aggregations: average EHI, risk distribution, top issues, and top interventions. |
| `/api/wards` | GET | Aggregated profiles for all 24 administrative wards. |
| `/api/wards/{ward_name}`| GET | Specific ward profile by name (e.g., `/api/wards/K-West`). |
| `/api/satellite-status` | GET | Metadata for Sentinel-2, Landsat-8, SRTM, CHIRPS, and OSM data feeds. |
| `/api/satellite-sync` | POST | UI simulation endpoint returning status of data feeds and fallback cache engagement. |
| `/api/chat` | POST | Natural language AI copilot powered by OpenRouter function calling. |

---

## 11. AI Copilot & Tool Calling (`backend/chat.py`)

Interprets natural language queries using OpenRouter (default: `google/gemini-2.5-flash`).

### Available Functions
1. `get_city_stats`: Returns city-wide averages and distributions.
2. `get_cell_details(cell_id)`: Fetches full diagnostic profile for a specific cell.
3. `get_top_cells(limit, priority_level)`: Returns highest-priority cells needing intervention.
4. `get_ward_summary(ward_name)`: Returns aggregated statistics for an administrative ward.
5. `find_cell_by_coordinates(lat, lon)`: Maps latitude/longitude to enclosing grid cell.
6. `search_cells_by_condition(condition, locality)`: Finds cells matching specific environmental stress.
7. `search_cells_by_location(query)`: Locates cells within a named neighborhood (e.g., "Bandra", "Thane").

### Spatial URL Parsing
`extract_coords_from_text()` parses coordinate patterns and Google Maps URLs:
- `@19.0760,72.8777,15z`
- `?q=19.0760,72.8777`
- `maps.google.com/?ll=19.0760,72.8777`

---

## 12. Frontend Architecture & Visualization (`frontend/`)

React 19 + TypeScript + Vite + Tailwind CSS.
- **State Management**: Zustand (`store/useStore.ts`) for UI controls; TanStack Query (`api/citysense.ts`) with `staleTime: Infinity` for API data.
- **Rendering Engine**: Deck.gl `GeoJsonLayer` with WebGL-accelerated 3D extrusion capabilities.

### 12.1 The 11 Choropleth Map Layers
| Layer Key | Display Label | Palette | Value Range | Description |
|---|---|---|---|---|
| `environmental_health` | **EHI** | Red $\rightarrow$ Green | 0 – 100 | Composite Environmental Health Index |
| `risk_score` | **Risk** | Green $\rightarrow$ Red | 0 – 100 | PCA Environmental Risk Score |
| `mean_lst` | **LST** | Blue $\rightarrow$ Red | 28°C – 46°C | Land Surface Temperature |
| `mean_ndvi` | **NDVI** | Brown $\rightarrow$ Green | -0.1 – 0.7 | Vegetation Canopy Index |
| `mean_ndbi` | **NDBI** | Green $\rightarrow$ Purple | -0.3 – 0.5 | Built-up Impervious Surface Index |
| `uhi_intensity` | **UHI** | Blue $\rightarrow$ Orange | -2°C – 15°C | Thermal anomaly above forest baseline |
| `cluster` | **Clusters** | Categorical (5 col) | 0 – 3 | Urban Typology Clusters |
| `planning_priority_score`| **Priority** | Green $\rightarrow$ Red | 0 – 100 | Action Prioritization Urgency |
| `flood_susceptibility_score`| **Flood** | Blue $\rightarrow$ Red | 0 – 100 | Flood Vulnerability Index |
| `iai_score` | **Access** | Red $\rightarrow$ Green | 0 – 100 | Civic Infrastructure Proximity Index |
| `burden_score` | **Burden** | Green $\rightarrow$ Red | 0 – 100 | Double Disadvantage Burden Index |

---

## 13. Validation Methodology & Ground Truth (`validation/`)

1. **Flood Ground Truth Check (`ground_truth_check.py`)**: Evaluates 37 chronic waterlogging locations from BMC flood logs and news archives (2019–2025). Validates that flood points correlate with low elevation and high FSI.
2. **Public Health Ground Truth Check (`health_ground_truth_check.py`)**: Compares ward-level dengue/malaria case records against CitySense environmental risk metrics.
3. **Statistical Validation (`statistical_validation.py`)**: Computes AUC-ROC and Average Precision across indices to confirm that FSI outperforms raw DEM alone in predicting flood spots.

---

## 14. Configuration Reference

- **`config/config.yaml`**: Coordinates bounding box, reduction scales, cloud filtering thresholds, PCA/K-Means hyperparameters, and output file paths.
- **`config/geographic_config.yaml`**: Administrative ward boundary definitions, 2024 population estimates, and land-use classification thresholds.
- **`backend/.env`**: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `google/gemini-2.5-flash`), and `PORT`.

---

## 15. Deployment & Runbook

### Deployed Production Setup
- **Backend**: Render Web Service (`render.yaml`), running `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- **Frontend**: Vercel (`vercel.json`), static Vite build rewriting `/api/*` and `/health` requests to the Render instance.

### Pipeline Re-computation Runbook
To recompute the pipeline after changing formulas:
```bash
# 1. Recalibrate benchmarks and EHI
python -m environment.generate_environmental_intelligence

# 2. Recompute planning profiles
python -m planning.generate_planning_profiles

# 3. Recompute composite burden
python -m environment.composite_burden

# 4. Sync master GeoJSON
python _sync_master.py

# 5. Run test suite (93 unit tests)
pytest tests/ -v
```

---

## 16. Known Limitations & Epistemic Boundaries

1. **Single Pre-Monsoon Snapshot**: Satellite data represents March–May 2023. Seasonal variation across post-monsoon or winter periods is not captured.
2. **No Hydrological Routing**: FSI is a domain-weighted geospatial screening index, not a hydrodynamic flood simulation. It does not model pipe diameter, tidal backwater, or soil percolation.
3. **Proximity vs Accessibility**: Infrastructure access uses Euclidean distance rather than road-network walking time or public transit schedules.
4. **OSM Completeness Variations**: OpenStreetMap drainage and amenity coverage varies between central Mumbai and peri-urban extended MMR.
5. **PCA Sensitivity Decomposition**: Random Forest SHAP values quantify the PCA index construction; they are not an independent causal model of external physical events.
