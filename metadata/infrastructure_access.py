"""
infrastructure_access.py
========================
Computes per-cell infrastructure access distances using OSM data
queried via the Overpass API.

OUTPUT FIELDS (per cell)
------------------------
  hospital_dist_km    Distance to nearest hospital or clinic (km)
  school_dist_km      Distance to nearest school (km)
  park_dist_km        Distance to nearest park or recreation ground (km)
  transit_dist_km     Distance to nearest railway/metro station (km)

FRAMING NOTE
------------
These are objective distance-to-infrastructure metrics. They measure
access gaps — not the quality of residents or housing. A cell with
"hospital_dist_km = 4.2" has a hospital 4.2 km away; this is a
factual statement about infrastructure proximity, not a value judgment.

Labels in the IAI use "Low infrastructure access" (describing what is
absent) rather than characterizing the community itself.

OSM completeness caveat: formal hospitals, schools, and railway
stations are reliably mapped in Mumbai. Small clinics, informal
schools, and community parks may be under-mapped in some areas.

Usage
-----
    python -m metadata.infrastructure_access    (from project root)
    python metadata/infrastructure_access.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import geopandas as gpd

_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from config_loader import load_config, project_path
from geo_utils import query_overpass, haversine_distance

logger = logging.getLogger("CitySense.metadata.infrastructure_access")

# ---------------------------------------------------------------------------
# Query configuration
# ---------------------------------------------------------------------------
_RADIUS_KM = 2.0
_RADIUS_M  = int(_RADIUS_KM * 1000)
_DEFAULT_DIST_KM = 6.0   # returned when no feature found within radius

# Facility categories — each is a list of (key, value) OSM tag pairs
_FACILITY_TAGS: dict[str, list[tuple[str, str]]] = {
    "hospital": [
        ("amenity", "hospital"),
        ("amenity", "clinic"),
        ("amenity", "health_post"),
    ],
    "school": [
        ("amenity", "school"),
        ("amenity", "college"),
        ("amenity", "university"),
    ],
    "park": [
        ("leisure", "park"),
        ("leisure", "garden"),
        ("landuse", "recreation_ground"),
        ("leisure", "playground"),
    ],
    "transit": [
        ("railway", "station"),
        ("station", "subway"),
        ("railway", "halt"),
        ("amenity", "bus_station"),
    ],
}


# ---------------------------------------------------------------------------
# Overpass query builder
# ---------------------------------------------------------------------------

def _build_query(lat: float, lon: float, radius_m: int,
                 tags: list[tuple[str, str]]) -> str:
    """Build Overpass QL for multiple tags around a point."""
    parts: list[str] = []
    for key, val in tags:
        parts.append(f'node["{key}"="{val}"](around:{radius_m},{lat},{lon});')
        parts.append(f'way["{key}"="{val}"](around:{radius_m},{lat},{lon});')
    return f"[out:json][timeout:30];({''.join(parts)});out center;"


def _nearest_km(response: dict[str, Any] | None,
                cell_lat: float, cell_lon: float) -> float:
    """Return distance to nearest element in the Overpass response."""
    if not response or not response.get("elements"):
        return _DEFAULT_DIST_KM
    min_d = _DEFAULT_DIST_KM
    for el in response["elements"]:
        el_lat = el.get("lat") or (el.get("center") or {}).get("lat")
        el_lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if el_lat is None or el_lon is None:
            continue
        d = haversine_distance(cell_lat, cell_lon, float(el_lat), float(el_lon))
        if d < min_d:
            min_d = d
    return round(min_d, 4)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("=== CitySense — Infrastructure Access Queries ===")

    cfg         = load_config()
    master_path = project_path(cfg, "master_data")
    cache_dir   = _PROJECT_ROOT / "data" / "geo"
    cache_path  = cache_dir / "infrastructure_cache.json"
    output_path = _PROJECT_ROOT / "data" / "infrastructure_access.json"

    cache_dir.mkdir(parents=True, exist_ok=True)

    # Load checkpoint cache
    if cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as f:
            cache: dict[str, dict] = json.load(f)
        logger.info("Loaded cache: %d cells already processed.", len(cache))
    else:
        cache = {}

    # Load grid centroids
    gdf = gpd.read_file(str(master_path))
    projected    = gdf.to_crs(epsg=32643)
    centroids_g  = projected.geometry.centroid.to_crs(epsg=4326)
    gdf["centroid_lon"] = centroids_g.x
    gdf["centroid_lat"] = centroids_g.y

    pending = [row for _, row in gdf.iterrows() if row["cell_id"] not in cache]
    logger.info("Total: %d | Cached: %d | To query: %d",
                len(gdf), len(gdf) - len(pending), len(pending))

    for i, row in enumerate(pending):
        cell_id = row["cell_id"]
        lat     = float(row["centroid_lat"])
        lon     = float(row["centroid_lon"])

        if (i + 1) % 50 == 0:
            logger.info("  Progress: %d/%d …", i + 1, len(pending))
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(cache, f)

        cell_data: dict[str, float] = {}
        for facility, tags in _FACILITY_TAGS.items():
            q        = _build_query(lat, lon, _RADIUS_M, tags)
            response = query_overpass(q, max_retries=2)
            dist     = _nearest_km(response, lat, lon)
            cell_data[f"{facility}_dist_km"] = dist

        cache[cell_id] = cell_data

    # Final save
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

    # Build output from cache
    output: dict[str, dict] = {}
    for _, row in gdf.iterrows():
        cid = row["cell_id"]
        output[cid] = cache.get(cid, {
            "hospital_dist_km": _DEFAULT_DIST_KM,
            "school_dist_km":   _DEFAULT_DIST_KM,
            "park_dist_km":     _DEFAULT_DIST_KM,
            "transit_dist_km":  _DEFAULT_DIST_KM,
        })

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Summary
    for key in ("hospital_dist_km", "school_dist_km",
                "park_dist_km", "transit_dist_km"):
        vals = [v[key] for v in output.values() if key in v]
        within = sum(1 for v in vals if v < _DEFAULT_DIST_KM)
        logger.info("  %-22s  mean=%.2f km  within %.1f km: %d/%d",
                    key, sum(vals)/len(vals) if vals else 0,
                    _RADIUS_KM, within, len(vals))

    logger.info("Wrote → %s", output_path)
    logger.info("=== Infrastructure access complete! ===")


if __name__ == "__main__":
    main()
