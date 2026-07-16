"""
fetch_ndbi.py
=============
Pulls a cloud-masked Sentinel-2 NDBI (Normalized Difference Built-up Index)
composite for the pre-monsoon window, reduces to mean per grid cell, and
saves data/ndbi_grid.geojson.

NDBI = (B11 - B8) / (B11 + B8)
    B11 = SWIR1 (1610 nm, 20m resolution)
    B8  = NIR   (842 nm,  10m resolution)

Positive NDBI => built-up / impervious surfaces
Negative NDBI => vegetation / water

Usage:
    python ingestion/fetch_ndbi.py           (from project root)
"""

import os
import sys
import time
import logging
from typing import Any
import ee
import geopandas as gpd
from config_loader import load_config

logger = logging.getLogger("CitySense.ingestion.fetch_ndbi")

# ---------------------------------------------------------------------------
# 0. Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))


# =====================================================================
# Configuration
# =====================================================================
def get_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    """Flatten NDBI-related configuration for the ingestion stage."""
    aoi = cfg["aoi"]
    return {
        "west":  aoi["west"],
        "south": aoi["south"],
        "east":  aoi["east"],
        "north": aoi["north"],
        "start_date": cfg["time_window"]["start"],
        "end_date":   cfg["time_window"]["end"],
        "project": cfg["gee"].get("project", None),
        "s2_collection": cfg["gee"]["sentinel2_collection"],
        "max_cloud_pct": cfg["gee"]["max_cloud_percentage"],
        "scale": cfg["gee"]["reduction_scales_m"]["ndbi"],
        "grid_path": os.path.join(PROJECT_ROOT, cfg["output_paths"]["grid"]),
        "ndbi_output": os.path.join(
            PROJECT_ROOT,
            cfg["output_paths"].get("ndbi_grid", "data/ndbi_grid.geojson"),
        ),
    }


# =====================================================================
# Earth Engine init
# =====================================================================
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
            logger.critical("Could not initialize Earth Engine.")
            logger.critical('Run python -c "import ee; ee.Authenticate()" first.')
            raise SystemExit(1) from exc
    logger.info("Earth Engine initialized (project=%s)", project)


def make_aoi(west: float, south: float, east: float, north: float) -> ee.Geometry:
    """Create a rectangular Earth Engine geometry from AOI coordinates."""
    return ee.Geometry.Rectangle([west, south, east, north])


# =====================================================================
# Cloud masking (same as Week 2 -- Sentinel-2 QA60)
# =====================================================================
def mask_s2_clouds(image: ee.Image) -> ee.Image:
    """Mask opaque clouds (bit 10) and cirrus (bit 11) using QA60."""
    qa = image.select("QA60")
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = (
        qa.bitwiseAnd(cloud_bit_mask).eq(0)
        .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    )
    return image.updateMask(mask)


# =====================================================================
# NDBI composite
# =====================================================================
def get_s2_ndbi_composite(
    aoi: ee.Geometry,
    start_date: str,
    end_date: str,
    collection_id: str,
    max_cloud_pct: int = 20,
) -> tuple[ee.Image, ee.Number]:
    """
    Build a cloud-masked Sentinel-2 NDBI median composite.
    NDBI = (B11 - B8) / (B11 + B8)
    """
    s2 = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_pct))
    )
    scene_count = s2.size()

    # Cloud mask
    s2_masked = s2.map(mask_s2_clouds)

    # Compute NDBI for each image
    def add_ndbi(image: ee.Image) -> ee.Image:
        """Add the NDBI band to one cloud-masked Sentinel-2 image."""
        ndbi = image.normalizedDifference(["B11", "B8"]).rename("ndbi")
        return image.addBands(ndbi)

    s2_ndbi = s2_masked.map(add_ndbi)

    # Median composite, keep only NDBI band
    composite = s2_ndbi.select("ndbi").median().clip(aoi)

    return composite, scene_count


# =====================================================================
# Load grid as ee.FeatureCollection
# =====================================================================
def load_grid_as_ee_fc(grid_path: str) -> tuple[ee.FeatureCollection, gpd.GeoDataFrame]:
    """Load the local grid and convert it to an Earth Engine collection."""
    gdf = gpd.read_file(grid_path)
    logger.info("Loaded grid: %d cells", len(gdf))

    features = []
    for _, row in gdf.iterrows():
        geom = ee.Geometry(row.geometry.__geo_interface__)
        feat = ee.Feature(geom, {"cell_id": row["cell_id"]})
        features.append(feat)

    return ee.FeatureCollection(features), gdf


# =====================================================================
# Reduce + Export
# =====================================================================
def reduce_and_export(
    image: ee.Image,
    grid_fc: ee.FeatureCollection,
    local_gdf: gpd.GeoDataFrame,
    output_path: str,
    band_name: str,
    scale: int = 10,
) -> gpd.GeoDataFrame:
    """Reduce image to grid cell means and export as GeoJSON."""
    reduced = image.reduceRegions(
        collection=grid_fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
    )

    logger.info("Fetching results from Earth Engine...")
    t0 = time.time()
    fc_dict = reduced.getInfo()
    elapsed = time.time() - t0
    logger.info("Received %d features in %.1fs", len(fc_dict['features']), elapsed)

    # Build lookup
    lookup = {}
    for feat in fc_dict["features"]:
        props = feat["properties"]
        lookup[props.get("cell_id")] = props.get("mean")

    # Merge into local GeoDataFrame
    local_gdf = local_gdf.copy()
    local_gdf[band_name] = local_gdf["cell_id"].map(lookup)

    valid = local_gdf[band_name].notna().sum()
    logger.info("Cells with valid %s: %d/%d", band_name, valid, len(local_gdf))
    if valid > 0:
        logger.info("Range: %.4f to %.4f", local_gdf[band_name].min(), local_gdf[band_name].max())
        logger.info("Mean:  %.4f", local_gdf[band_name].mean())

    result = local_gdf[["cell_id", band_name, "geometry"]].copy()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    result.to_file(output_path, driver="GeoJSON")
    logger.info("Saved to: %s", output_path)
    return result


# =====================================================================
# MAIN
# =====================================================================
def main() -> None:
    """Fetch configured Sentinel-2 NDBI values for every grid cell."""
    logger.info("=== City Sense -- Week 4: Fetch NDBI ===")

    cfg = load_config()
    s = get_settings(cfg)
    logger.info("AOI        : W=%s, S=%s, E=%s, N=%s", s['west'], s['south'], s['east'], s['north'])
    logger.info("Time window: %s -> %s", s['start_date'], s['end_date'])
    logger.info("Collection : %s", s['s2_collection'])

    init_ee(project=s["project"])
    aoi_geom = make_aoi(s["west"], s["south"], s["east"], s["north"])

    # Build NDBI composite
    logger.info("Building cloud-masked NDBI composite...")
    ndbi_composite, scene_count = get_s2_ndbi_composite(
        aoi_geom, s["start_date"], s["end_date"], s["s2_collection"], s["max_cloud_pct"]
    )
    n_scenes = scene_count.getInfo()
    logger.info("Sentinel-2 scenes matched: %d", n_scenes)
    if n_scenes == 0:
        logger.warning("No scenes found!")
        sys.exit(1)

    # Load grid and reduce
    logger.info("Loading grid and reducing NDBI to cell means (scale=10 m)...")
    grid_fc, local_gdf = load_grid_as_ee_fc(s["grid_path"])

    logger.info("Exporting results...")
    reduce_and_export(
        ndbi_composite, grid_fc, local_gdf,
        s["ndbi_output"], "mean_ndbi", scale=s["scale"]
    )

    logger.info("=== NDBI layer complete! ===")


if __name__ == "__main__":
    main()
