"""
generate_infrastructure_access.py
===================================
Pipeline stage: computes IAI for all cells and writes
data/infrastructure_access_index.json.

Inputs (read-only):
    data/cells_master.geojson
    data/infrastructure_access.json    (from metadata/infrastructure_access.py)
    data/geo/geographic_metadata.json  (for population)

Output:
    data/infrastructure_access_index.json

Usage:
    python -m environment.generate_infrastructure_access
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
from environment.infrastructure_access_index import (
    compute_iai_city_stats,
    compute_iai_batch,
    get_iai_status,
    generate_iai_narrative,
)

logger = logging.getLogger("CitySense.environment.generate_infrastructure_access")


def _load_json(path: Path, label: str) -> dict:
    if not path.exists():
        logger.warning("%s not found at '%s' — proceeding without it.", label, path)
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("=== CitySense — Generate Infrastructure Access Index ===")
    t0 = time.time()

    cfg         = load_config()
    master_path = project_path(cfg, "master_data")
    infra_path  = _PROJECT_ROOT / "data" / "infrastructure_access.json"
    geo_path    = project_path(cfg, "geographic_metadata")
    out_path    = _PROJECT_ROOT / "data" / "infrastructure_access_index.json"

    gdf      = gpd.read_file(str(master_path))
    infra    = _load_json(infra_path, "Infrastructure access distances")
    geo_meta = _load_json(geo_path,   "Geographic metadata")

    logger.info("Loaded %d cells | infra=%d | geo_meta=%d",
                len(gdf), len(infra), len(geo_meta))

    city_stats = compute_iai_city_stats(gdf, infra, geo_meta)
    logger.info("City stats computed for: %s", list(city_stats.keys()))

    iai_series = compute_iai_batch(gdf, city_stats, infra, geo_meta)
    logger.info("IAI: min=%.1f  max=%.1f  mean=%.1f  median=%.1f",
                iai_series.min(), iai_series.max(),
                iai_series.mean(), iai_series.median())

    output: dict[str, dict] = {}
    status_counter: Counter = Counter()

    for idx, row in gdf.iterrows():
        cid    = row.get("cell_id", str(idx))
        iai    = float(iai_series.loc[idx])
        status = get_iai_status(iai)

        ir = infra.get(cid, {})
        narrative = generate_iai_narrative(
            iai, status,
            ir.get("hospital_dist_km"),
            ir.get("school_dist_km"),
            ir.get("park_dist_km"),
            ir.get("transit_dist_km"),
        )

        output[cid] = {
            "iai_score":            round(iai, 2),
            "iai_status":           status,
            "hospital_dist_km":     ir.get("hospital_dist_km"),
            "school_dist_km":       ir.get("school_dist_km"),
            "park_dist_km":         ir.get("park_dist_km"),
            "transit_dist_km":      ir.get("transit_dist_km"),
            "iai_narrative":        narrative,
        }
        status_counter[status] += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info("Wrote IAI for %d cells → %s (%.2fs)", len(output), out_path, time.time()-t0)
    for label in ["Excellent", "Good", "Moderate", "Low"]:
        count = status_counter.get(label, 0)
        logger.info("  %-10s : %4d cells  (%.1f%%)", label, count,
                    count / len(output) * 100 if output else 0)
    logger.info("=== IAI generation complete! ===")


if __name__ == "__main__":
    main()
