"""
generate_flood_susceptibility.py
=================================
Pipeline stage: computes FSI for all 836 cells and writes
data/flood_susceptibility.json.

Inputs (all read-only):
    data/cells_master.geojson          — mean_dem, mean_ndbi
    data/drainage_proxy.json           — drain_distance_km per cell
    data/precipitation_grid.geojson    — cumul_precip per cell
                                         (optional — FSI degrades gracefully
                                          if precipitation data is absent)

Output:
    data/flood_susceptibility.json     — FSI per cell

Usage:
    python -m environment.generate_flood_susceptibility
    python environment/generate_flood_susceptibility.py
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from pathlib import Path
import sys

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import geopandas as gpd

from config_loader import load_config, project_path
from environment.flood_susceptibility import (
    compute_fsi_city_stats,
    compute_fsi_batch,
    get_fsi_status,
    generate_fsi_narrative,
)

logger = logging.getLogger("CitySense.environment.generate_flood_susceptibility")


def _load_json(path: Path, label: str) -> dict:
    if not path.exists():
        logger.warning("%s not found at '%s' — proceeding without it.", label, path)
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_precip_geojson(path: Path) -> dict[str, dict]:
    """Load precipitation GeoJSON and convert to {cell_id: {cumul_precip, mean_precip}}."""
    if not path.exists():
        return {}
    gdf = gpd.read_file(str(path))
    result: dict[str, dict] = {}
    for _, row in gdf.iterrows():
        cell_id = row.get("cell_id")
        if cell_id:
            result[cell_id] = {
                "cumul_precip": row.get("cumul_precip"),
                "mean_precip":  row.get("mean_precip"),
            }
    return result


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("=== CitySense — Generate Flood Susceptibility Index ===")
    t_start = time.time()

    cfg = load_config()

    master_path = project_path(cfg, "master_data")
    drain_path  = _PROJECT_ROOT / "data" / "drainage_proxy.json"
    precip_path = _PROJECT_ROOT / "data" / "precipitation_grid.geojson"
    output_path = _PROJECT_ROOT / "data" / "flood_susceptibility.json"

    logger.info("Master dataset : %s", master_path)
    logger.info("Drainage proxy : %s  (exists: %s)", drain_path,  drain_path.exists())
    logger.info("Precipitation  : %s  (exists: %s)", precip_path, precip_path.exists())

    # Load inputs
    logger.info("Loading master dataset …")
    gdf = gpd.read_file(str(master_path))
    logger.info("Loaded %d cells.", len(gdf))

    drain  = _load_json(drain_path, "Drainage proxy")
    precip = _load_precip_geojson(precip_path)
    logger.info("Drainage data: %d cells | Precipitation data: %d cells",
                len(drain), len(precip))

    if not drain:
        logger.warning(
            "No drainage proxy data. FSI will use DEM, NDBI, and precipitation only. "
            "Run: python -m metadata.drainage_proxy"
        )
    if not precip:
        logger.warning(
            "No precipitation data. FSI will use DEM, NDBI, and drainage only. "
            "Run: python -m ingestion.fetch_precipitation"
        )

    # Compute city-wide stats
    logger.info("Computing city-wide FSI statistics …")
    city_stats = compute_fsi_city_stats(gdf, drain, precip)
    logger.info("FSI city stats: %s", list(city_stats.keys()))

    # Batch FSI
    logger.info("Computing FSI for %d cells …", len(gdf))
    fsi_series = compute_fsi_batch(gdf, city_stats, drain, precip)
    logger.info(
        "FSI stats: min=%.1f  max=%.1f  mean=%.1f  median=%.1f",
        fsi_series.min(), fsi_series.max(),
        fsi_series.mean(), fsi_series.median(),
    )

    # Build output
    output: dict[str, dict] = {}
    status_counter: Counter = Counter()

    for idx, row in gdf.iterrows():
        cell_id = row.get("cell_id", str(idx))
        fsi     = float(fsi_series.loc[idx])
        status  = get_fsi_status(fsi)

        dp = drain.get(cell_id, {})
        pp = precip.get(cell_id, {})

        narrative = generate_fsi_narrative(
            cell_id=cell_id,
            fsi=fsi,
            status=status,
            dem=row.get("mean_dem"),
            ndbi=row.get("mean_ndbi"),
            drain_distance_km=dp.get("drain_distance_km"),
            cumul_precip=pp.get("cumul_precip"),
            city_stats=city_stats,
        )

        output[cell_id] = {
            "flood_susceptibility_score": round(fsi, 2),
            "flood_susceptibility_status": status,
            "drain_distance_km":   dp.get("drain_distance_km"),
            "drain_feature_count": dp.get("drain_feature_count"),
            "cumul_precip_mm":     pp.get("cumul_precip"),
            "mean_precip_mm_day":  pp.get("mean_precip"),
            "fsi_narrative":       narrative,
        }
        status_counter[status] += 1

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - t_start
    logger.info("Wrote FSI for %d cells → %s (%.2fs)", len(output), output_path, elapsed)

    logger.info("FSI Status distribution:")
    for label in ["Severe", "High", "Moderate", "Low"]:
        count = status_counter.get(label, 0)
        pct   = count / len(output) * 100 if output else 0
        logger.info("  %-10s : %4d cells  (%.1f%%)", label, count, pct)

    logger.info("=== FSI generation complete! ===")


if __name__ == "__main__":
    main()
