# City Sense

**An AI-driven geospatial pipeline for assessing and explaining urban environmental risks and sustainability.**

## Problem Statement

Rapid urbanization presents critical challenges, including Urban Heat Islands (UHI), loss of green cover, and increased flood risks. City planners and stakeholders often lack accessible, high-resolution, and explainable insights to make data-driven decisions. **City Sense** bridges this gap by fusing Earth observation data (Sentinel-2, Landsat, SRTM) into a unified, grid-based framework, applying machine learning to score environmental risks, cluster similar urban typologies, and explain the key drivers of those risks using SHAP (SHapley Additive exPlanations).

## Architecture & Pipeline

```mermaid
graph TD
    A[Earth Engine Data] -->|Sentinel, Landsat, DEM| B(Ingestion & Gridding)
    B --> C(Indicator Processing)
    C -->|NDVI, LST, NDBI, DEM| D(PCA Scoring)
    D -->|Risk & Sustainability Scores| E(K-Means Clustering)
    E -->|Urban Typologies| F(XGBoost & SHAP)
    F -->|Explainability| G(Enriched Master Dataset)
    G --> P2(Environmental Intelligence Layer)
    P2 -->|EHI, Status, Comparisons, Summaries| H[Interactive Streamlit Dashboard]
    G --> GEO(Geographic Intelligence Layer)
    GEO -->|Localities, Wards, Landmarks| H
```

## Phase 2: Environmental Intelligence Layer

The Environmental Intelligence Layer converts raw remote sensing indicators
into human-readable narratives and comparative analytics that city planners
can act on directly — without requiring GIS expertise.

### Design Principle

Every indicator answers **"So what?"**

| Before (Phase 1) | After (Phase 2) |
|---|---|
| NDVI = 0.18 | Vegetation cover is 44% below the city average, indicating poor ecological health and limited cooling capacity. |
| LST = 39.4°C | This grid is among the hottest 6% of locations in Mumbai and exhibits a strong Urban Heat Island effect. |
| Risk = 0.82 | Environmental Health: **19 / 100 — Critical**. Primary issue: Urban Heat Island. |

### Environmental Health Index (EHI)

A composite score (0–100, higher = healthier) computed independently of the
PCA Risk Score using a domain-justified weighted formula:

| Indicator | Weight | Rationale |
|---|---|---|
| LST (surface temperature) | 30% | Primary heat stress driver in Mumbai |
| NDVI (vegetation) | 25% | Key ecological cooling mechanism |
| UHI Intensity | 20% | Urban heat island amplification |
| NDBI (built-up density) | 15% | Impervious surface coverage |
| DEM (elevation) | 10% | Flood susceptibility proxy |

**Formula:**
1. MinMax-normalise each indicator to [0, 1] using city-wide min/max.
2. Invert NDVI and DEM so that `1.0 = highest risk` for all indicators.
3. Weighted sum → composite ∈ [0, 1].
4. `EHI = (1 − composite) × 100`, clamped to [0, 100].

**Status labels:** Critical (0–19) · Poor (20–39) · Moderate (40–59) · Good (60–79) · Excellent (80–100)

### Comparative Analytics

For every cell, each indicator is compared against city-wide statistics:
- Absolute deviation from city mean (e.g. `+4.3°C`)
- Percentage deviation (e.g. `12% above city average`)
- Percentile rank (e.g. `93rd percentile — hotter than 93% of all grids`)

### Detected Environmental Conditions

The layer automatically detects six named conditions using percentile-rank
thresholds (no ML model required):

| Condition | Trigger criteria |
|---|---|
| Urban Heat Island | UHI rank ≥ 75th AND LST rank ≥ 70th percentile |
| Low Vegetation | NDVI rank ≤ 25th percentile |
| High Built-up Density | NDBI rank ≥ 75th percentile |
| Flood Susceptibility | DEM rank ≤ 20th percentile |
| Environmental Stress | EHI < 40 |
| Ecological Stability | EHI ≥ 70 AND NDVI rank ≥ 60th percentile |

### Architecture

```mermaid
graph TD
    M[cells_master.geojson] -->|read-only| CA(comparative_analysis.py)
    M -->|read-only| EH(environmental_health.py)
    M -->|read-only| II(indicator_interpreter.py)
    CA --> ES(environmental_summary.py)
    EH --> ES
    II --> ES
    ES -->|templates| ET(environment_templates.py)
    ES --> GEI(generate_environmental_intelligence.py)
    GEI --> OUT[data/environmental_intelligence.json]
    OUT --> DASH[dashboard/app.py]
```

### Module Reference

| Module | Responsibility |
|---|---|
| `environment_templates.py` | All constants: EHI weights, status thresholds, condition rules, summary templates |
| `comparative_analysis.py` | City-wide statistics; per-cell percentile ranks and deviations |
| `environmental_health.py` | EHI computation (single-cell and vectorised batch); status label |
| `indicator_interpreter.py` | Condition detection; spatial context sentence generation |
| `environmental_summary.py` | Template-based narrative paragraph (no LLM) |
| `generate_environmental_intelligence.py` | Pipeline stage orchestrator; writes JSON output |

### Output Data Model

Each cell in `data/environmental_intelligence.json` contains:

```json
{
  "environmental_health": 71.4,
  "environmental_status": "Moderate",
  "city_rank_lst": 93.0,
  "city_rank_ndvi": 18.0,
  "city_rank_ndbi": 78.0,
  "city_rank_uhi": 88.0,
  "city_rank_dem": 22.0,
  "city_rank_risk": 85.0,
  "mean_lst_vs_city_avg": 4.3,
  "mean_ndvi_vs_city_avg": -0.15,
  "mean_ndvi_pct_diff": -44.0,
  "detected_conditions": ["Urban Heat Island", "Low Vegetation"],
  "primary_issue": "Urban Heat Island",
  "secondary_issue": "Low Vegetation",
  "spatial_context": "This grid is hotter than 93% of all Mumbai grids ...",
  "environmental_summary": "This grid experiences elevated surface temperatures ..."
}
```

### Dashboard Sidebar Layout (Phase 2)

```
📍 Geographic Profile
↓
🌿 Environmental Health   ← EHI score + status badge (NEW)
↓
🔥 Environmental Issues   ← detected conditions (NEW)
↓
📈 Comparative Analysis   ← per-indicator rank + delta vs city avg (NEW)
↓
🧠 Environmental Summary  ← template-based paragraph (NEW)
↓
📊 Spatial Context        ← spatial ranking sentence (NEW)
↓
📋 Raw Indicators         ← collapsed expander (previously top-level)
↓
🧠 AI Explanation         ← SHAP explanation (unchanged)
↓
💡 Recommendation         ← rule-based recommendation (unchanged)
```

## Features & Methodology

- **Data Ingestion & Gridding**: Divides the bounding box (Mumbai) into a high-resolution spatial grid and extracts remote sensing data using Google Earth Engine.
- **Indicators**:
  - **NDVI**: Normalized Difference Vegetation Index (green cover).
  - **LST**: Land Surface Temperature (derived from thermal bands).
  - **NDBI**: Normalized Difference Built-up Index (urban density).
  - **DEM**: Digital Elevation Model (flood risk proxy).
  - **UHI Intensity**: Deviation of a cell's temperature from the mean LST of a reference green area (Sanjay Gandhi National Park / Aarey Colony), following standard urban heat island methodology.
- **PCA Scoring**: Uses Principal Component Analysis to compute a composite Risk Score and a Sustainability Score.
- **Clustering**: K-Means clustering groups cells into distinct urban typologies (e.g., "Dense Urban Heat Core", "Vegetated Suburbs").
- **Explainability (SHAP)**: An XGBoost surrogate model predicts the Risk Score, and SHAP values are extracted to explain the primary positive and negative drivers for *every single grid cell*.
- **Geographic Intelligence Layer (Phase 1)**: Transforms raw grid identifiers into meaningful geographic profiles.
  - Reverse geocoding (OpenStreetMap Nominatim) maps cells to localities (e.g., *Powai*).
  - Spatial joins map grids to administrative wards and zones.
  - Overpass API detects nearby landmarks (hospitals, schools, parks).
  - Land use classification categorizes dominant urban footprints.
  - Ward-level census data estimates cell-level population.
- **Environmental Intelligence Layer (Phase 2)**: Converts raw indicators into city-planner-facing narratives without any new ML models.
  - Environmental Health Index (EHI, 0–100) with five status tiers.
  - Comparative analytics: percentile ranks and deviations vs. city average for every indicator.
  - Automatic detection of six named environmental conditions (Urban Heat Island, Low Vegetation, etc.).
  - Deterministic template-based Environmental Summary paragraphs.
  - Spatial context sentences ("hotter than 93% of Mumbai grids").
- **Interactive Dashboard**: A Streamlit application featuring Folium maps for visualizing layers, clicking on cells for detailed Geographic Profiles, environmental breakdowns, AI explanations, and rule-based recommendations.

## Results & Key Findings

- **LST-NDVI Correlation**: As expected, a strong negative correlation is observed between vegetation density and land surface temperature, validating the UHI effect.
- **Feature Importance**: NDBI (built-up area) and LST are the strongest drivers of high Risk Scores, while NDVI heavily drives Sustainability Scores.
- **Clustering Map**: Distinct patterns emerge across the city, highlighting the dense urban core versus the greener outskirts and coastal boundaries.

## Project Structure

```text
CitySense/city_sense/
├── README.md
├── LICENSE
├── requirements.txt
├── config/
│   ├── config.yaml              # All runtime configuration
│   └── geographic_config.yaml   # Geographic intelligence settings
├── config_loader.py             # Shared YAML configuration loader
├── main.py                      # Single pipeline entry point
├── utils.py                     # Configuration validation & structured logging
├── geo_utils.py                 # Shared geographic utilities
├── ingestion/                   # Scripts to fetch and grid GEE data
├── processing/                  # Scripts to calculate indicators
├── modeling/                    # Scoring, clustering, and SHAP explanations
├── metadata/                    # Phase 1: Geographic Intelligence Layer
├── environment/                 # Phase 2: Environmental Intelligence Layer
│   ├── environment_templates.py     # Constants, thresholds, and templates
│   ├── comparative_analysis.py      # City-wide stats and percentile rankings
│   ├── environmental_health.py      # EHI computation and status labels
│   ├── indicator_interpreter.py     # Condition detection and spatial context
│   ├── environmental_summary.py     # Template-based narrative paragraphs
│   └── generate_environmental_intelligence.py  # Pipeline stage + JSON output
├── dashboard/                   # Streamlit application (app.py)
├── data/                        # Processed GeoJSON, JSON, and imagery
│   ├── geo/                     # Cached geographic metadata and ward boundaries
│   ├── overlays/                # Optional static satellite imagery overlays
│   └── environmental_intelligence.json  # Phase 2 enrichment output
└── tests/                       # Unit tests for all modules
```

## Setup & Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/aryan4-eternity/CitySense
   cd city_sense
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Earth Engine Authentication:**
   You must have a Google Earth Engine account. Authenticate your environment:
   ```bash
   earthengine authenticate
   ```

5. **Configuration:**
   Update `config/config.yaml` with your preferred city, bounding box, grid
   resolution, date range, model settings, dashboard defaults, and output paths.

## How to Run the Pipeline

The entire pipeline is orchestrated by `main.py`. It validates
`config/config.yaml`, sets up structured logging, and calls the real ingestion
and processing stages in dependency order. Individual stages remain runnable
as Python modules for focused development.

```bash
python main.py
```
Logs will be output to the console and saved to `citysense.log`.

## How to Run the Dashboard

To view the interactive Streamlit dashboard locally:

```bash
python -m streamlit run dashboard/app.py
```
Then navigate to `http://localhost:8501` in your web browser. 

*Optional: Place exported `mumbai_rgb.tif` and `mumbai_thermal.tif` in `data/overlays/` to enable satellite basemap toggles.*

## Validation & Testing

The project includes unit tests to ensure data integrity and model sanity.
To run the tests:

```bash
pytest tests/
```
**Validation Summary:**
- **Silhouette Score:** Evaluates the quality of K-Means clustering.
- **LST Bounds:** Unit tests ensure surface temperatures fall within a plausible range (10°C - 60°C).
- **SHAP Consistency:** Verifies that features like LST positively contribute to Risk, while NDVI negatively contributes.
- **EHI Bounds:** Unit tests verify EHI is always in [0, 100] and that high-stress cells score lower than low-stress cells.
- **Condition Detection:** Deterministic unit tests verify each of the six environmental conditions fires correctly on synthetic data.
- **Summary Templates:** Tests assert that generated summaries never contain unfilled `{placeholder}` tokens across all condition/status combinations.

## Future Work

- **Phase 3 — Planning Recommendation Engine:** Will consume `primary_issue`, `environmental_health`, `environmental_status`, and `environmental_summary` from `environmental_intelligence.json` to generate ward-level intervention recommendations without recomputation.
- **Temporal Analysis:** Expanding the pipeline to process multiple time windows and assess seasonal changes. The `environment/` modules are designed for future extensibility to time-series inputs.
- **Higher Resolution:** Utilizing commercial satellite data for sub-10m resolution.
- **Policy Simulator:** Adding a feature to the dashboard allowing users to "simulate" adding green roofs to a cell and observing the predicted risk reduction.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- Google Earth Engine for data access.
- The open-source geospatial Python community (GeoPandas, Folium).
- The creators of SHAP for model explainability.
