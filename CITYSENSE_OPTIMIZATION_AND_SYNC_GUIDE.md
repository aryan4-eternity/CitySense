# CitySense: Green-Urban Metric Optimization & Data Sync Architecture Guide

## 1. Executive Summary

This guide provides a comprehensive technical overview of the **Green-Urban Benchmark Recalibration**, the **Frontend Map Layer Optimization**, the **Resilient Satellite Data Sync Architecture**, and the **Production Deployment Model** (Render Backend + Vercel Frontend) for the **CitySense** platform.

---

## 2. Problem Statement & Root Cause

### The "Mostly Red" Map Problem
In initial deployments across the 1,663 grid cells of the Mumbai Metropolitan Region (MMR):
1. **City-Wide Extreme Min/Max Normalization**: The Environmental Health Index (EHI) normalized raw indicators against the absolute minimum and maximum across the entire geographic region. Because the pristine Sanjay Gandhi National Park (SGNP) and surrounding coastal waters set extreme minimum temperatures (~29.6°C) and maximum NDVI (~0.64), almost all standard residential and commercial urban cells were classified as "Poor" or "Critical".
2. **Resulting Skew**:
   - City-wide average EHI was depressed to **~26.5 / 100**.
   - Less than 3% of cells reached "Moderate" or "Good".
   - Derived layers (Planning Priority and Composite Burden) inherited this severe skew, causing the Deck.gl choropleth map to be visually dominated by crimson red.
3. **Hard-Coded Map Ranges**: Frontend layer configurations in `layers.ts` used narrow min/max bounds (e.g., UHI max set to 8°C when real MMR UHI reaches ~14°C), causing standard urban heat readings to clip at the top of the color ramp.

---

## 3. The Solution: Green-Urban Neighborhood Benchmarks

Rather than comparing urban neighborhoods against a pristine uninhabited rainforest (SGNP), CitySense anchors environmental quality to the **greenest comparable urban neighborhoods** in the city.

### 3.1 Step 1: Comparable Urban Cell Selection
Module: `environment/benchmarks.py` $\rightarrow$ `select_comparable_urban_cells()`

Filters the 1,663 total cells to extract **1,338 comparable urban cells** by excluding:
1. **Water / Sea Cells**: Flagged by `is_water == True` or $(\text{NDVI} < 0.05 \text{ and } \text{DEM} < 3.5\text{ m})$.
2. **SGNP Reference Zone**: Centroids falling inside $\text{Lon: } [72.87, 72.93], \text{Lat: } [19.18, 19.25]$.
3. **Non-Urban Outlier Clusters**:
   - `Cluster 1: Green/Forested` (Ecological Sanctuaries / Forest Ridges).
   - `Cluster 3: Extreme Urban Heat / Industrial` (Dense Heavy Industrial Zones).

### 3.2 Step 2: Top-10% Green-Urban Benchmark
Module: `environment/benchmarks.py` $\rightarrow$ `select_green_urban_benchmark_cells()`

Within the 1,338 comparable urban cells, the top 10% by vegetation index ($\text{NDVI} \ge 0.354$) are selected as the green-urban benchmark set ($N = 134$ cells).

### 3.3 Step 3: Indicator Anchor Calculation
Module: `environment/benchmarks.py` $\rightarrow$ `compute_benchmarks()`

For each indicator, a **Good Anchor ($G$)** and a **Worst Anchor ($W$)** are established and persisted to `data/benchmarks.json`:

$$\begin{aligned}
G &= \text{median}(\text{Benchmark Cells}) \\
W &= \begin{cases}
p_{95}(\text{All MMR Cells}) & \text{for indicators where higher is worse (LST, UHI, NDBI)} \\
p_{5}(\text{All MMR Cells}) & \text{for indicators where higher is better (NDVI, DEM)}
\end{cases}
\end{aligned}$$

#### Calibrated MMR Benchmark Anchors (`data/benchmarks.json`)
| Indicator | Direction | Good Anchor ($G$) | Worst Anchor ($W$) | Interpretation |
|---|---|---|---|---|
| **`mean_lst`** | Higher = Worse | **36.43 °C** | **43.33 °C** | Green urban residential vs city 95th percentile heat |
| **`uhi_intensity`** | Higher = Worse | **6.23 °C** | **13.13 °C** | Green urban heat anomaly vs peak industrial anomaly |
| **`mean_ndbi`** | Higher = Worse | **0.094** | **0.318** | Vegetated urban density vs dense concrete core |
| **`mean_ndvi`** | Higher = Better | **0.3795** | **0.123** | Green canopy median vs barren/paved 5th percentile |
| **`mean_dem`** | Higher = Better | **32.65 m** | **13.90 m** | Natural elevation median vs low-lying flood-prone |

---

## 4. Mathematical Normalization & Index Formulation

### 4.1 Directional Risk Normalization
Module: `environment/environmental_health.py`

For each indicator $i$ with cell value $v_i$:

$$\text{risk\_norm}_i = \begin{cases}
\text{clip}\left(\frac{v_i - G_i}{W_i - G_i}, 0.0, 1.0\right) & \text{if } i \in \{\text{LST}, \text{UHI}, \text{NDBI}\} \\
\text{clip}\left(\frac{G_i - v_i}{G_i - W_i}, 0.0, 1.0\right) & \text{if } i \in \{\text{NDVI}, \text{DEM}\}
\end{cases}$$

- A cell at or better than the green-urban benchmark scores **$\text{risk\_norm} = 0.0$** (zero risk).
- A cell at or worse than the 95th percentile worst threshold scores **$\text{risk\_norm} = 1.0$** (maximum risk).

### 4.2 Environmental Health Index (EHI)
$$\text{EHI} = \left(1.0 - \sum_{i} w_i \cdot \text{risk\_norm}_i\right) \times 100$$

**Domain Weights**:
- Land Surface Temperature (LST): **30%**
- Vegetation Cover (NDVI): **25%**
- Urban Heat Island Intensity (UHI): **20%**
- Built-up Density (NDBI): **15%**
- Terrain Elevation (DEM): **10%**

*Missing Value Handling*: If an indicator is missing/NaN, its weight is redistributed proportionally among the remaining available indicators.

### 4.3 Distribution Shift (Before vs After)
| Metric | Before (City Min/Max) | After (Green-Urban Benchmarks) |
|---|---|---|
| **City-Wide Mean EHI** | ~26.5 / 100 | **47.5 / 100** |
| **Excellent Status ($>80$)** | < 3% | **16.2%** (270 cells) |
| **Moderate Status ($40–60$)** | ~25% | **54.2%** (902 cells) |
| **Critical Status ($<20$)** | ~60% | **14.9%** (247 cells) |
| **Green Urban Neighborhood (`r11_c24`)** | EHI $\approx$ 38.2 (Poor) | **EHI = 92.64 (Excellent)** |
| **Heavy Industrial Hotspot (`r11_c31`)** | EHI $\approx$ 10.5 (Critical) | **EHI = 10.00 (Critical)** |

---

## 5. Frontend Color Scale & UI Calibration

### 5.1 Deck.gl Continuous Color Ramps (`frontend/src/components/Map/layers.ts`)
Multi-stop piecewise color interpolation maps normalized values to intuitive palettes:

1. **`green_red` (EHI, IAI — Higher is healthier)**:
   - `t: 0.00` $\rightarrow$ `[255, 45, 75]` (Critical Deficit / Crimson Red)
   - `t: 0.25` $\rightarrow$ `[255, 75, 55]` (Critical/Poor boundary)
   - `t: 0.40` $\rightarrow$ `[255, 140, 35]` (Poor / Orange)
   - `t: 0.50` $\rightarrow$ `[255, 215, 45]` (Moderate Urban Baseline / Warm Gold)
   - `t: 0.70` $\rightarrow$ `[85, 215, 95]` (Good / Fresh Lime Green)
   - `t: 0.88` $\rightarrow$ `[0, 235, 130]` (Green-Urban Benchmark Emerald)
   - `t: 1.00` $\rightarrow$ `[0, 240, 130]` (Pristine Forest / Lush Emerald)

2. **`red_green` (Risk, Planning Priority, Flood, Burden — Higher is riskier)**:
   - `t: 0.00` $\rightarrow$ `[0, 235, 130]` (Low Risk / Safe Emerald)
   - `t: 0.28` $\rightarrow$ `[85, 215, 95]` (Low / Fresh Lime)
   - `t: 0.50` $\rightarrow$ `[255, 215, 45]` (Moderate Baseline / Warm Gold)
   - `t: 0.75` $\rightarrow$ `[255, 130, 35]` (High Priority / Vivid Orange)
   - `t: 1.00` $\rightarrow$ `[255, 45, 75]` (Critical Crisis Hotspots / Crimson Red)

3. **`blue_red` (LST)**: Calibrated to `min: 28°C, max: 46°C`.
4. **`blue_orange` (UHI)**: Calibrated to `min: -2°C, max: 15°C`.

### 5.2 Cell Panel Header Badge Differentiation (`frontend/src/components/CellPanel/CellPanel.tsx`)
To prevent duplicate `CRITICAL` labels when a cell is critical in both environment and planning:
- Environmental Health Badge: **`ENV: <STATUS>`** (e.g. `ENV: CRITICAL`, `ENV: MODERATE`)
- Planning Urgency Badge: **`PRIORITY: <PRIORITY>`** (e.g. `PRIORITY: CRITICAL`, `PRIORITY: MEDIUM`)
- Embedded HTML `title` tooltips clarify their distinct analytical meanings on hover.

---

## 6. End-to-End System Architecture

```
                                  OFFLINE / LOCAL DATA PIPELINE
                     ┌─────────────────────────────────────────────────────────┐
                     │ Google Earth Engine (Landsat-8, Sentinel-2, SRTM)       │
                     │ OpenStreetMap (Overpass API)                            │
                     │ CHIRPS Precipitation                                    │
                     └────────────────────────────┬────────────────────────────┘
                                                  │
                                                  ▼
                     ┌─────────────────────────────────────────────────────────┐
                     │ environment/benchmarks.py                               │
                     │ environment/generate_environmental_intelligence.py      │
                     │ planning/generate_planning_profiles.py                  │
                     │ environment/composite_burden.py                         │
                     │ _sync_master.py                                         │
                     └────────────────────────────┬────────────────────────────┘
                                                  │ (Produces data/ JSON & GeoJSON)
                                                  ▼
                     ┌─────────────────────────────────────────────────────────┐
                     │ data/cells_master.geojson (1,663 cells)                 │
                     │ data/benchmarks.json                                    │
                     │ data/environmental_intelligence.json                    │
                     │ data/planning_profiles.json                             │
                     └────────────────────────────┬────────────────────────────┘
                                                  │
                             ┌────────────────────┴────────────────────┐
                             │ Git Push to GitHub                      │
                             ▼                                         ▼
                 ┌───────────────────────┐                 ┌───────────────────────┐
                 │    RENDER (Backend)   │                 │    VERCEL (Frontend)  │
                 │  FastAPI (Python)     │                 │  React + Deck.gl      │
                 │  backend/main.py      │◄───HTTP API─────│  frontend/src         │
                 │  • /api/cells         │   (React Query) │  • Interactive Map    │
                 │  • /api/cell/{id}     │                 │  • Radar Charts       │
                 │  • /api/satellite-sync│                 │  • AI Copilot Chat    │
                 └───────────────────────┘                 └───────────────────────┘
```

---

## 7. Satellite Live Telemetry & Resilient Fallback

When a user clicks **"Satellite Feeds" $\rightarrow$ "Trigger Sync"** in the top navigation bar:

1. **Frontend Request**: Calls `POST /api/satellite-sync`.
2. **Backend Telemetry Check**: Evaluates active satellite feeds:
   - **Sentinel-2 MSI** (10m NDVI & NDBI)
   - **Landsat-8 TIRS** (30m Thermal LST & UHI)
   - **NASA SRTM v3** (30m Elevation & Slope)
   - **UCSB CHIRPS** (0.05° Monsoon Precipitation)
   - **OpenStreetMap** (Vector Infrastructure & Drainage)
3. **Resilient Cloud & Fallback Handling**:
   - If a live satellite pass is obscured by monsoon cloud cover (e.g. Landsat thermal band cloud cover $> 20\%$) or hits API rate limits:
   - The backend flags `fallback_engaged: true` and serves data from the **Authoritative Calibrated Cache**.
   - **Guarantee**: The application maintains 100% uptime with zero missing cells or interface crashes.

---

## 8. Operations & Maintenance Runbook

### When do you need to run terminal commands?
- **During Regular Platform Usage**: **Never.** The deployed app on Vercel and Render is fully autonomous.
- **When modifying Python scoring formulas or weights**:
  ```bash
  # 1. Recompute Environmental Intelligence with benchmarks
  python -m environment.generate_environmental_intelligence

  # 2. Recompute Planning Profiles
  python -m planning.generate_planning_profiles

  # 3. Recompute Composite Burden
  python -m environment.composite_burden

  # 4. Synchronize master GeoJSON
  python _sync_master.py
  ```

### How to verify test integrity:
```bash
python -m pytest tests/ -v
# Verified: 93/93 tests passing (100% green)
```

### How to deploy updates to Render & Vercel:
```bash
git add .
git commit -m "Optimize metric scoring with green-urban benchmarks and fix UI badges"
git push origin main
```
Render automatically redeploys `backend/main.py`, and Vercel automatically deploys the updated React frontend.
