"""
drainage_proxy.py
=================
Computes per-cell drainage infrastructure proxy indicators using OSM
waterway data queried via the Overpass API.

OUTPUT FIELDS (per cell)
------------------------
  drain_distance_km    Distance to the nearest mapped waterway/drain (km).
                       Smaller = closer to drainage infrastructure.
  drain_feature_count  Number of mapped drainage features within 1.5 km of
                       the cell centroid.

IMPORTANT CAVEATS
-----------------
OSM drainage tagging completeness varies significantly across Mumbai.
Formal municipal drains, canals, and natural streams are better mapped
than small residential drains or informal drainage channels. This proxy
measures *mapped drainage infrastructure density*, NOT actual municipal
drainage network capacity or storm-water system adequacy. Areas with
poor OSM coverage may appear falsely drain-distant. This limitation is
acknowledged explicitly in CITYSENSE_TECHNICAL_DOCUMENTATION.md §FSI.

The query tags used are:
  waterway = drain | canal | stream | river
  natural  = water  (water bodies — lakes, ponds, reservoirs)

These are queried within a 1.5 km radius of each cell centroid using
the same Overpass API infrastructure already used in landmark_detector.py.

Usage
-----
    python -m metadata.drainage_proxy    (from project root)
    python metadata/drainage_proxy.py
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

import geopandas as gpd

_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from config_loader import load_config, project_path
from geo_utils import query_overpass, haversine_distance

logger = logging.getLogger("CitySense.metadata.drainage_proxy")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_QUERY_RADIUS_KM = 1.5          # search radius around each cell centroid
_QUERY_RADIUS_M  = int(_QUERY_RADIUS_KM * 1000)

# OSM tags to query — waterway features and natural water bodies
_WATERWAY_TAGS = [
    ("waterway", "drain"),
    ("waterway", "canal"),
    ("waterway", "stream"),
    ("waterway", "river"),
    ("natural",  "water"),
]

_DEFAULT_MAX_DISTANCE_KM = 5.0  # assigned when no feature found within radius


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_overpass_query(lat: float, lon: float, radius_m: int) -> str:
    """Build Overpass QL query for waterway/water features around a point."""
    parts: list[str] = []
    for key, val in _WATERWAY_TAGS:
        parts.append(f'node["{key}"="{val}"](around:{radius_m},{lat},{lon});')
        parts.append(f'way["{key}"="{val}"](around:{radius_m},{lat},{lon});')
    inner = "".join(parts)
    return f"[out:json][timeout:30];({inner});out center;"


def _nearest_distance_and_count(
    response: dict[str, Any] | None,
    cell_lat: float,
    cell_lon: float,
) -> tuple[float, int]:
    """
    Extract nearest-feature distance and feature count from an Overpass response.

    Returns
    -------
    (distance_km, count)
        distance_km: distance to the nearest mapped waterway element (km).
            Returns _DEFAULT_MAX_DISTANCE_KM when no features are found,
            indicating likely absence of mapped drainage within the radius.
        count: number of distinct elements returned.
    """
    if not response or "elements" not in response:
        return _DEFAULT_MAX_DISTANCE_KM, 0

    elements = response["elements"]
    if not elements:
        return _DEFAULT_MAX_DISTANCE_KM, 0

    min_dist = _DEFAULT_MAX_DISTANCE_KM
    for el in elements:
        el_lat = el.get("lat") or (el.get("center", {}) or {}).get("lat")
        el_lon = el.get("lon") or (el.get("center", {}) or {}).get("lon")
        if el_lat is None or el_lon is None:
            continue
        dist = haversine_distance(cell_lat, cell_lon, float(el_lat), float(el_lon))
        if dist < min_dist:
            min_dist = dist

    return round(min_dist, 4), len(elements)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Query Overpass for drainage features per cell and write JSON output."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("=== CitySense — Drainage Proxy Computation ===")

    cfg          = load_config()
    master_path  = project_path(cfg, "master_data")
    cache_dir    = _PROJECT_ROOT / "data" / "geo"
    cache_path   = cache_dir / "drainage_cache.json"
    output_path  = _PROJECT_ROOT / "data" / "drainage_proxy.json"

    # Load existing cache to allow resuming interrupted runs
    cache_dir.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as f:
            cache: dict[str, dict] = json.load(f)
        logger.info("Loaded drainage cache: %d cells already processed.", len(cache))
    else:
        cache = {}

    # Load master dataset for cell centroids
    logger.info("Loading master dataset …")
    gdf = gpd.read_file(str(master_path))
    projected = gdf.to_crs(epsg=32643)
    centroids_proj = projected.geometry.centroid.to_crs(epsg=4326)
    gdf["centroid_lon"] = centroids_proj.x
    gdf["centroid_lat"] = centroids_proj.y

    total   = len(gdf)
    pending = [row for _, row in gdf.iterrows() if row["cell_id"] not in cache]
    logger.info(
        "Total cells: %d | Already cached: %d | To query: %d",
        total, total - len(pending), len(pending),
    )

    # Query Overpass for uncached cells
    for i, row in enumerate(pending):
        cell_id = row["cell_id"]
        lat     = float(row["centroid_lat"])
        lon     = float(row["centroid_lon"])

        if (i + 1) % 50 == 0:
            logger.info("  Progress: %d/%d cells queried …", i + 1, len(pending))
            # Save cache checkpoint every 50 cells
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(cache, f)

        query   = _build_overpass_query(lat, lon, _QUERY_RADIUS_M)
        response = query_overpass(query, max_retries=2)
        dist_km, count = _nearest_distance_and_count(response, lat, lon)

        cache[cell_id] = {
            "drain_distance_km":    dist_km,
            "drain_feature_count":  count,
        }

    # Final cache save
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
    logger.info("Drainage cache saved → %s", cache_path)

    # Build output JSON from cache
    output: dict[str, dict] = {}
    for _, row in gdf.iterrows():
        cell_id = row["cell_id"]
        if cell_id in cache:
            output[cell_id] = cache[cell_id]
        else:
            # Circuit-breaker fallback: cell not queried
            output[cell_id] = {
                "drain_distance_km":   _DEFAULT_MAX_DISTANCE_KM,
                "drain_feature_count": 0,
            }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Summary stats
    dists  = [v["drain_distance_km"] for v in output.values()]
    counts = [v["drain_feature_count"] for v in output.values()]
    cells_with_drain = sum(1 for d in dists if d < _DEFAULT_MAX_DISTANCE_KM)

    logger.info("Wrote drainage proxy for %d cells → %s", len(output), output_path)
    logger.info(
        "Drain distance: min=%.2f km  max=%.2f km  mean=%.2f km",
        min(dists), max(dists), sum(dists) / len(dists),
    )
    logger.info(
        "Cells with mapped drain within %.1f km: %d / %d (%.0f%%)",
        _QUERY_RADIUS_KM, cells_with_drain, len(output),
        cells_with_drain / len(output) * 100,
    )
    logger.info("Avg drain feature count: %.1f", sum(counts) / len(counts))
    logger.info("=== Drainage proxy complete! ===")


if __name__ == "__main__":
    main()
