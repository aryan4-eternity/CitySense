"""
fetch_dem.py
============
Pulls SRTM elevation data, reduces to mean elevation per grid cell,
and saves data/dem_grid.geojson.

SRTM GL1 provides global elevation at ~30 m resolution.
Mumbai elevation ranges from ~0 m (coast) to ~450 m (hills in SGNP).

Usage:
    python ingestion/fetch_dem.py             (from project root)
"""

import os
import sys
import time
from typing import Any
import ee
import geopandas as gpd
from config_loader import load_config

# ---------------------------------------------------------------------------
# 0. Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))


def get_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    """Flatten DEM-related configuration for the ingestion stage."""
    aoi = cfg["aoi"]
    return {
        "west":  aoi["west"],
        "south": aoi["south"],
        "east":  aoi["east"],
        "north": aoi["north"],
        "project": cfg["gee"].get("project", None),
        "srtm_collection": cfg["gee"]["srtm_collection"],
        "scale": cfg["gee"]["reduction_scales_m"]["dem"],
        "grid_path": os.path.join(PROJECT_ROOT, cfg["output_paths"]["grid"]),
        "dem_output": os.path.join(
            PROJECT_ROOT,
            cfg["output_paths"].get("dem_grid", "data/dem_grid.geojson"),
        ),
    }


def init_ee(project: str | None = None) -> None:
    """Initialize the Earth Engine client for the configured project."""
    try:
        ee.Initialize(project=project)
    except Exception:
        try:
            ee.Initialize(
                project=project,
                opt_url="https://earthengine-highvolume.googleapis.com",
            )
        except Exception as exc:
            print("ERROR: Could not initialize Earth Engine.")
            raise SystemExit(1) from exc
    print(f"[OK] Earth Engine initialized (project={project})")


def make_aoi(west: float, south: float, east: float, north: float) -> ee.Geometry:
    """Create a rectangular Earth Engine geometry from AOI coordinates."""
    return ee.Geometry.Rectangle([west, south, east, north])


def load_grid_as_ee_fc(grid_path: str) -> tuple[ee.FeatureCollection, gpd.GeoDataFrame]:
    """Load the local grid and convert it to an Earth Engine collection."""
    gdf = gpd.read_file(grid_path)
    print(f"[OK] Loaded grid: {len(gdf)} cells")

    features = []
    for _, row in gdf.iterrows():
        geom = ee.Geometry(row.geometry.__geo_interface__)
        feat = ee.Feature(geom, {"cell_id": row["cell_id"]})
        features.append(feat)

    return ee.FeatureCollection(features), gdf


def main() -> None:
    """Fetch configured SRTM elevation values for every grid cell."""
    print("=" * 60)
    print("  City Sense -- Week 4: Fetch DEM (SRTM)")
    print("=" * 60)

    cfg = load_config()
    s = get_settings(cfg)
    print(f"\nAOI       : W={s['west']}, S={s['south']}, E={s['east']}, N={s['north']}")
    print(f"Collection: {s['srtm_collection']}")
    print()

    init_ee(project=s["project"])
    aoi_geom = make_aoi(s["west"], s["south"], s["east"], s["north"])

    # ---- Load SRTM elevation -----------------------------------------------
    print("> Loading SRTM elevation data...")
    srtm = ee.Image(s["srtm_collection"]).select("elevation").clip(aoi_geom)

    # ---- Load grid ----------------------------------------------------------
    print(f"\n> Loading grid and reducing DEM to cell means (scale={s['scale']} m)...")
    grid_fc, local_gdf = load_grid_as_ee_fc(s["grid_path"])

    # ---- Reduce to grid cell means -----------------------------------------
    reduced = srtm.reduceRegions(
        collection=grid_fc,
        reducer=ee.Reducer.mean(),
        scale=s["scale"],
    )

    # ---- Export via getInfo() -----------------------------------------------
    print("\n> Exporting results...")
    print("  Fetching results from Earth Engine...")
    t0 = time.time()
    fc_dict = reduced.getInfo()
    elapsed = time.time() - t0
    print(f"  [OK] Received {len(fc_dict['features'])} features in {elapsed:.1f}s")

    # Build lookup
    dem_lookup = {}
    for feat in fc_dict["features"]:
        props = feat["properties"]
        dem_lookup[props.get("cell_id")] = props.get("mean")

    local_gdf = local_gdf.copy()
    local_gdf["mean_dem"] = local_gdf["cell_id"].map(dem_lookup)

    valid = local_gdf["mean_dem"].notna().sum()
    print(f"  Cells with valid DEM: {valid}/{len(local_gdf)}")
    if valid > 0:
        print(f"  Elevation range: {local_gdf['mean_dem'].min():.1f} - "
              f"{local_gdf['mean_dem'].max():.1f} m")
        print(f"  Mean elevation:  {local_gdf['mean_dem'].mean():.1f} m")

    # Save
    result = local_gdf[["cell_id", "mean_dem", "geometry"]].copy()
    output_path = s["dem_output"]
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    result.to_file(output_path, driver="GeoJSON")
    print(f"[OK] Saved DEM grid to: {output_path}")

    print("\n" + "=" * 60)
    print("  [OK] DEM layer complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
