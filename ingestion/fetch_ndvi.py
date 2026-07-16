"""
fetch_ndvi.py
=============
Pulls a cloud-masked Sentinel-2 NDVI composite for the pre-monsoon window
defined in config/config.yaml, reduces it to mean values per grid cell, and saves
the result as data/ndvi_grid.geojson.

Usage:
    python ingestion/fetch_ndvi.py          (from project root)
    python -m ingestion.fetch_ndvi          (from project root)

Prerequisites:
    - Earth Engine authenticated  (earthengine authenticate)
    - Virtual environment active with all requirements installed
    - data/grid.geojson must already exist (run generate_grid.py first)
"""

import os
import sys
import json
import time
import logging
from typing import Any
import ee
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from config_loader import load_config

logger = logging.getLogger("CitySense.ingestion.fetch_ndvi")

# ---------------------------------------------------------------------------
# 0. Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))


# =====================================================================
# STEP 1 — Read configuration
# =====================================================================
def get_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    """Extract the configured NDVI settings into a flat mapping."""
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
        "scale": cfg["gee"]["reduction_scales_m"]["ndvi"],
        "grid_path": os.path.join(PROJECT_ROOT, cfg["output_paths"]["grid"]),
        "ndvi_output": os.path.join(
            PROJECT_ROOT,
            cfg["output_paths"].get("ndvi_grid", "data/ndvi_grid.geojson"),
        ),
    }


# =====================================================================
# STEP 2 — Initialize Earth Engine and create AOI rectangle
# =====================================================================
def init_ee(project: str | None = None) -> None:
    """Initialize the Earth Engine API with the given GCP project."""
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
            logger.critical("Run python -c \"import ee; ee.Authenticate()\" first.")
            logger.critical("Project: %s", project)
            raise SystemExit(1) from exc
    logger.info("Earth Engine initialized (project=%s)", project)


def make_aoi(west: float, south: float, east: float, north: float) -> ee.Geometry:
    """Create an ee.Geometry.Rectangle from bounding-box coordinates."""
    return ee.Geometry.Rectangle([west, south, east, north])


# =====================================================================
# STEP 3 — Build cloud-masked Sentinel-2 NDVI composite
# =====================================================================
def mask_s2_clouds(image: ee.Image) -> ee.Image:
    """
    Mask clouds and cirrus in a Sentinel-2 image using the QA60 band.

    QA60 bit flags:
        Bit 10 — Opaque clouds
        Bit 11 — Cirrus
    If either bit is set the pixel is cloudy and should be masked out.
    """
    qa = image.select("QA60")

    # Bits 10 and 11 are clouds and cirrus respectively
    cloud_bit_mask = 1 << 10  # 1024
    cirrus_bit_mask = 1 << 11  # 2048

    # Both flags should be zero → clear pixel
    mask = (
        qa.bitwiseAnd(cloud_bit_mask).eq(0)
        .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    )
    return image.updateMask(mask)


def get_s2_ndvi_composite(
    aoi: ee.Geometry,
    start_date: str,
    end_date: str,
    collection_id: str = "COPERNICUS/S2_HARMONIZED",
    max_cloud_pct: int = 20,
) -> ee.Image:
    """
    Build a cloud-masked Sentinel-2 NDVI median composite.

    Parameters
    ----------
    aoi : ee.Geometry
        Area of interest.
    start_date, end_date : str
        ISO date strings (e.g. "2023-03-01").
    collection_id : str
        GEE Sentinel-2 collection ID.
    max_cloud_pct : int
        Maximum CLOUDY_PIXEL_PERCENTAGE per scene.

    Returns
    -------
    ee.Image
        Single-band image with band 'ndvi' (median composite), clipped to AOI.

    Notes
    -----
    Adjust *max_cloud_pct* upward (e.g. 30–40) if Sentinel-2 coverage is sparse
    in your date range, or widen the date window. A stricter threshold gives
    cleaner pixels but may leave gaps if there aren't enough clear acquisitions.
    """
    s2 = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_pct))
    )

    # Log how many scenes matched (will be printed via getInfo later)
    scene_count = s2.size()

    # Apply cloud mask to every scene
    s2_masked = s2.map(mask_s2_clouds)

    # Compute NDVI for each image: (B8 – B4) / (B8 + B4)
    def add_ndvi(image: ee.Image) -> ee.Image:
        """Add the NDVI band to one cloud-masked Sentinel-2 image."""
        ndvi = image.normalizedDifference(["B8", "B4"]).rename("ndvi")
        return image.addBands(ndvi)

    s2_ndvi = s2_masked.map(add_ndvi)

    # Take the median composite and keep only the NDVI band
    composite = s2_ndvi.select("ndvi").median().clip(aoi)

    return composite, scene_count


# =====================================================================
# STEP 4 — Load fishnet grid as ee.FeatureCollection
# =====================================================================
def load_grid_as_ee_fc(grid_path: str) -> ee.FeatureCollection:
    """
    Read the local GeoJSON grid file and convert it to an
    ee.FeatureCollection, preserving the cell_id property.
    """
    gdf = gpd.read_file(grid_path)
    logger.info("Loaded grid: %d cells from %s", len(gdf), grid_path)

    # Convert each row to an ee.Feature
    features = []
    for _, row in gdf.iterrows():
        geom = ee.Geometry(row.geometry.__geo_interface__)
        feat = ee.Feature(geom, {"cell_id": row["cell_id"]})
        features.append(feat)

    fc = ee.FeatureCollection(features)
    return fc, gdf


# =====================================================================
# STEP 5 — Reduce NDVI composite to grid cell means
# =====================================================================
def reduce_ndvi_to_grid(
    ndvi_image: ee.Image,
    grid_fc: ee.FeatureCollection,
    scale: int = 10,
) -> ee.FeatureCollection:
    """
    Compute the mean NDVI within each grid cell using reduceRegions.

    Parameters
    ----------
    ndvi_image : ee.Image
        Single-band NDVI composite.
    grid_fc : ee.FeatureCollection
        Grid cells with cell_id property.
    scale : int
        Pixel resolution in metres (10 m for Sentinel-2 bands B4/B8).

    Returns
    -------
    ee.FeatureCollection
        Same grid features enriched with a 'mean' property (mean NDVI).
    """
    reduced = ndvi_image.reduceRegions(
        collection=grid_fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
    )
    return reduced


# =====================================================================
# STEP 6 — Export to local GeoJSON via getInfo()
# =====================================================================
def export_to_geojson(
    reduced_fc: ee.FeatureCollection,
    local_gdf: gpd.GeoDataFrame,
    output_path: str,
) -> gpd.GeoDataFrame:
    """
    Retrieve the reduced features from Earth Engine, merge the mean_ndvi
    values back onto the local GeoDataFrame (to preserve exact geometries
    and avoid serialisation round-trip issues), and save as GeoJSON.

    For ~600–800 cells this runs comfortably within getInfo() limits.
    If your grid has >5 000 cells, use ee.batch.Export.table.toDrive instead.
    """
    logger.info("Fetching results from Earth Engine (this may take 1–3 minutes)...")
    t0 = time.time()

    # Retrieve the feature collection — returns a Python dict
    fc_dict = reduced_fc.getInfo()
    elapsed = time.time() - t0
    logger.info("Received %d features in %.1fs", len(fc_dict['features']), elapsed)

    # Build a lookup: cell_id → mean NDVI value
    ndvi_lookup = {}
    for feat in fc_dict["features"]:
        props = feat["properties"]
        cell_id = props.get("cell_id")
        mean_ndvi = props.get("mean")  # reduceRegions names it 'mean'
        ndvi_lookup[cell_id] = mean_ndvi

    # Merge into the local GeoDataFrame
    local_gdf = local_gdf.copy()
    local_gdf["mean_ndvi"] = local_gdf["cell_id"].map(ndvi_lookup)

    # Report basic stats
    valid = local_gdf["mean_ndvi"].notna().sum()
    logger.info("Cells with valid NDVI: %d/%d", valid, len(local_gdf))
    logger.info("NDVI range: %.4f – %.4f", local_gdf['mean_ndvi'].min(), local_gdf['mean_ndvi'].max())
    logger.info("NDVI mean: %.4f", local_gdf['mean_ndvi'].mean())

    # Keep only the columns we need
    result = local_gdf[["cell_id", "mean_ndvi", "geometry"]].copy()

    # Save to GeoJSON
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    result.to_file(output_path, driver="GeoJSON")
    logger.info("Saved NDVI grid to: %s", output_path)

    return result


# =====================================================================
# MAIN
# =====================================================================
def main() -> None:
    """Fetch configured Sentinel-2 NDVI values for every grid cell."""
    logger.info("=== City Sense — Week 2: Fetch NDVI ===")

    # ---- Step 1: Configuration ---------------------------------------------
    cfg = load_config()
    s = get_settings(cfg)
    logger.info("AOI        : W=%s, S=%s, E=%s, N=%s", s['west'], s['south'], s['east'], s['north'])
    logger.info("Time window: %s -> %s", s['start_date'], s['end_date'])
    logger.info("Collection : %s", s['s2_collection'])
    logger.info("Grid input : %s", s['grid_path'])
    logger.info("NDVI output: %s", s['ndvi_output'])

    # ---- Step 2: Initialize Earth Engine -----------------------------------
    init_ee(project=s["project"])
    aoi_geom = make_aoi(s["west"], s["south"], s["east"], s["north"])

    # ---- Step 3: Build NDVI composite --------------------------------------
    logger.info("Building cloud-masked NDVI composite...")
    ndvi_composite, scene_count = get_s2_ndvi_composite(
        aoi=aoi_geom,
        start_date=s["start_date"],
        end_date=s["end_date"],
        collection_id=s["s2_collection"],
        max_cloud_pct=s["max_cloud_pct"],
    )
    n_scenes = scene_count.getInfo()
    logger.info("Sentinel-2 scenes matched: %d", n_scenes)
    if n_scenes == 0:
        logger.warning("No scenes found! Try widening the date range or increasing CLOUDY_PIXEL_PERCENTAGE threshold.")
        sys.exit(1)

    # ---- Step 4: Load grid as ee.FeatureCollection -------------------------
    logger.info("Loading grid into Earth Engine...")
    grid_fc, local_gdf = load_grid_as_ee_fc(s["grid_path"])

    # ---- Step 5: Reduce to grid cell means ---------------------------------
    logger.info("Reducing NDVI to grid cell means (scale=%d m)...", s['scale'])
    reduced_fc = reduce_ndvi_to_grid(ndvi_composite, grid_fc, scale=s["scale"])

    # ---- Step 6: Export to local GeoJSON -----------------------------------
    logger.info("Exporting results...")
    result_gdf = export_to_geojson(reduced_fc, local_gdf, s["ndvi_output"])

    logger.info("=== Week 2 complete - NDVI layer generated! ===")


if __name__ == "__main__":
    main()
