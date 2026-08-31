# Optimize Metric Scoring: Green-Urban Benchmarks to Fix "Mostly Red" Map

## Objective
Recalibrate the continuous layer scores (EHI, Priority, Burden — and align Risk/LST/NDVI/NDBI/UHI color mapping) so the map is not dominated by red. Anchor the "good" end of every continuous metric to **greenest comparable urban neighborhoods** (top-10% NDVI urban cells), then re-run the pipeline to regenerate data and re-tune the frontend color scales.

## Root Cause
- EHI is MinMax-normalized against **city-wide min/max** (`environment/environmental_health.py`), with heat-heavy weights (LST 30% + UHI 20% = 50%).
- With the wider MMR feature range, most cells land in the Poor/Critical band → **avg EHI ≈ 26.5** → mostly red.
- Priority and Burden are derived from EHI, so they inherit the skew.
- Risk is already percentile-ranked (uniform), but its color stops still highlight too many cells as red/orange.
- Frontend color scales + per-layer `min/max` in `frontend/src/components/Map/layers.ts` are hard-coded and no longer match the real distribution.

## Approach

### 1. Benchmark definition (new module `environment/benchmarks.py`)
- Select "comparable urban cells":
  - exclude water cells (`is_water`)
  - exclude non-urban clusters (Ecological Sanctuary / Forest Ridge, Dense Industrial / High Thermal Risk) and the SGNP bbox
  - from the remaining cells, take the **top-10% by NDVI** = "greenest comparable urban neighborhoods"
- Compute per-indicator anchor set for these cells: median + p95 (for LST/UHI/NDBI) and p5 + median (for NDVI/DEM), persisted to `data/benchmarks.json`.

### 2. Benchmark-anchored normalization (modify `environment/environmental_health.py`)
Replace city-wide min/max with benchmark anchors `G` (good) and `W` (worst):
- LST / UHI / NDBI (higher = worse): `risk_norm = clip((value - G) / (W - G), 0, 1)`
- NDVI / DEM (higher = better): `risk_norm = clip((G - value) / (G - W), 0, 1)`
- Keep the existing weights (LST 30%, NDVI 25%, UHI 20%, NDBI 15%, DEM 10%) and missing-value weight redistribution.
- Keep `compute_ehi` / `compute_ehi_batch` signatures; add an optional `anchors` param so behavior is explicit and testable. EHI = `(1 - weighted_composite) * 100`.

Expected outcome: green-urban benchmark cells score EHI ≈ 80–100, a typical urban cell ≈ 50–70, and only the worst ~10–15% fall below 30.

### 3. Align derived scores
- `planning/generate_planning_profiles.py` — reuses regenerated EHI/risk (verify it reads from regenerated `environmental_intelligence.json`).
- `environment/composite_burden.py` — no formula change; re-run so burden follows the new EHI.
- `processing/pca_scoring.py` — keep percentile-ranked risk (already uniform); do not change formula.

### 4. Regenerate data (data-side fix)
Run only the recompute stages (no GEE/OSM refetch):
```bash
python -m environment.generate_environmental_intelligence
python -m planning.generate_planning_profiles
python -m environment.composite_burden
```
Backend (`backend/main.py`) merges `environmental_health`, `planning_priority_score`, FSI, IAI, burden onto the GeoJSON from these JSON files at request time, so no master-GeoJSON rewrite is strictly required — but run `_sync_master.py` (existing helper) to confirm `cells_master.geojson` embedded fields match the regenerated JSONs.

### 5. Frontend color re-tune (`frontend/src/components/Map/layers.ts`)
- Update `LAYER_CONFIGS` per-layer `min`/`max` to the regenerated (benchmark-anchored) observed ranges.
- Re-tune `SCALES` stops so only the worst ~10–15% render crimson; typical urban cells render gold/lime; benchmark cells render emerald.
- Update `getCellColor` normalization to use the new `min/max` (no hard-coded assumptions).

### 6. Tests & docs
- Update `tests/test_environmental_intelligence.py` EHI expectations to the new benchmark-anchored values (add a test: a top-10% NDVI urban cell must score EHI ≥ 70).
- Update `README.md` indices table + key-findings numbers (avg EHI, priority distribution).

## Files to change
| File | Change |
|---|---|
| `environment/benchmarks.py` (new) | Benchmark selection + anchor computation |
| `environment/environmental_health.py` | Anchor-based normalization |
| `environment/generate_environmental_intelligence.py` | Compute + persist benchmarks, pass anchors |
| `frontend/src/components/Map/layers.ts` | New min/max + re-tuned color stops |
| `tests/test_environmental_intelligence.py` | New expectations |
| `README.md` | Updated numbers/methodology |
| `data/benchmarks.json` (new output) | Anchor values |

## Verification / DoD
1. `pytest tests/ -v` passes with updated expectations (88 tests).
2. Recompute stages log a balanced distribution (e.g. Excellent/Good > 40%, Critical < 15%).
3. `/api/stats` shows a higher avg EHI (≈50+) and a reasonable priority distribution.
4. `tsc -b && npm run build` passes; frontend shows EHI/Priority/Burden with green-urban cells green, most urban cells gold, only worst cells red.
5. Sanity-check a known green urban cell (top-10% NDVI) vs a known industrial cell in the regenerated JSON.

## Traceability
| Step | Targets | Verification |
|---|---|---|
| Benchmark module | `environment/benchmarks.py` | Unit test: anchors within expected ranges |
| Anchor-based EHI | `environmental_health.py` | EHI tests updated + pass |
| Regenerate JSONs | env_intel, planning, burden | `/api/stats` avg EHI ≥ ~50 |
| Color re-tune | `layers.ts` | Build passes; visual check |
| Docs/tests | README, tests | pytest + build green |
