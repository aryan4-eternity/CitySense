"""
fetch_ndvi.py
=============
Pulls a cloud-masked Sentinel-2 NDVI composite for the pre-monsoon window
defined in config.yaml, reduces it to mean values per grid cell, and saves
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
import yaml
import ee
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

# ---------------------------------------------------------------------------
# 0. Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")


def load_config(path: str = CONFIG_PATH) -> dict:
    """Load and return the YAML configuration file."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


# =====================================================================
# STEP 1 — Read configuration
# =====================================================================
def get_settings(cfg: dict) -> dict:
    """Extract all the settings we need from config.yaml into a flat dict."""
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
        "grid_path": os.path.join(PROJECT_ROOT, cfg["output_paths"]["grid"]),
        "ndvi_output": os.path.join(
            PROJECT_ROOT,
            cfg["output_paths"].get("ndvi_grid", "data/ndvi_grid.geojson"),
        ),
    }


# =====================================================================
# STEP 2 — Initialize Earth Engine and create AOI rectangle
# =====================================================================
def init_ee(project: str = None):
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
            print("ERROR: Could not initialize Earth Engine.")
            print("       Run  python -c \"import ee; ee.Authenticate()\"  first.")
            print(f"       Project: {project}")
            raise SystemExit(1) from exc
    print(f"[OK] Earth Engine initialized (project={project})")


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
    print(f"[OK] Loaded grid: {len(gdf)} cells from {grid_path}")

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
    print("  Fetching results from Earth Engine (this may take 1–3 minutes)...")
    t0 = time.time()

    # Retrieve the feature collection — returns a Python dict
    fc_dict = reduced_fc.getInfo()
    elapsed = time.time() - t0
    print(f"  [OK] Received {len(fc_dict['features'])} features in {elapsed:.1f}s")

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
    print(f"  Cells with valid NDVI: {valid}/{len(local_gdf)}")
    print(f"  NDVI range: "
          f"{local_gdf['mean_ndvi'].min():.4f} – "
          f"{local_gdf['mean_ndvi'].max():.4f}")
    print(f"  NDVI mean:  {local_gdf['mean_ndvi'].mean():.4f}")

    # Keep only the columns we need
    result = local_gdf[["cell_id", "mean_ndvi", "geometry"]].copy()

    # Save to GeoJSON
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    result.to_file(output_path, driver="GeoJSON")
    print(f"[OK] Saved NDVI grid to: {output_path}")

    return result


# =====================================================================
# MAIN
# =====================================================================
def main():
    print("=" * 60)
    print("  City Sense — Week 2: Fetch NDVI")
    print("=" * 60)

    # ---- Step 1: Configuration ---------------------------------------------
    cfg = load_config()
    s = get_settings(cfg)
    print(f"\nAOI        : W={s['west']}, S={s['south']}, E={s['east']}, N={s['north']}")
    print(f"Time window: {s['start_date']} -> {s['end_date']}")
    print(f"Collection : {s['s2_collection']}")
    print(f"Grid input : {s['grid_path']}")
    print(f"NDVI output: {s['ndvi_output']}")
    print()

    # ---- Step 2: Initialize Earth Engine -----------------------------------
    init_ee(project=s["project"])
    aoi_geom = make_aoi(s["west"], s["south"], s["east"], s["north"])

    # ---- Step 3: Build NDVI composite --------------------------------------
    print("> Building cloud-masked NDVI composite...")
    ndvi_composite, scene_count = get_s2_ndvi_composite(
        aoi=aoi_geom,
        start_date=s["start_date"],
        end_date=s["end_date"],
        collection_id=s["s2_collection"],
        max_cloud_pct=20,
    )
    n_scenes = scene_count.getInfo()
    print(f"  Sentinel-2 scenes matched: {n_scenes}")
    if n_scenes == 0:
        print("  [WARNING] No scenes found! Try widening the date range or "
              "increasing CLOUDY_PIXEL_PERCENTAGE threshold.")
        sys.exit(1)

    # ---- Step 4: Load grid as ee.FeatureCollection -------------------------
    print("\n> Loading grid into Earth Engine...")
    grid_fc, local_gdf = load_grid_as_ee_fc(s["grid_path"])

    # ---- Step 5: Reduce to grid cell means ---------------------------------
    print("\n> Reducing NDVI to grid cell means (scale=10 m)...")
    reduced_fc = reduce_ndvi_to_grid(ndvi_composite, grid_fc, scale=10)

    # ---- Step 6: Export to local GeoJSON -----------------------------------
    print("\n> Exporting results...")
    result_gdf = export_to_geojson(reduced_fc, local_gdf, s["ndvi_output"])

    print("\n" + "=" * 60)
    print("  [OK] Week 2 complete - NDVI layer generated!")
    print("=" * 60)


if __name__ == "__main__":
    main()
