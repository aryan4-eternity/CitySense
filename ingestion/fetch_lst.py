"""
fetch_lst.py
============
Pulls Landsat 8/9 thermal data for the pre-monsoon window defined in
config/config.yaml, applies full emissivity correction to convert brightness
temperature to true land surface temperature (LST) in degrees Celsius,
reduces to mean per grid cell, and saves data/lst_grid.geojson.

Usage:
    python ingestion/fetch_lst.py            (from project root)
    python -m ingestion.fetch_lst            (from project root)

Prerequisites:
    - Earth Engine authenticated  (python -c "import ee; ee.Authenticate()")
    - Virtual environment active with all requirements installed
    - data/grid.geojson must already exist (run generate_grid.py first)

Physics:
    LST(K) = BT / (1 + (lambda * BT / rho) * ln(epsilon))
    where:
        BT       = Brightness temperature from ST_B10 (Kelvin)
        lambda   = 10.9e-6 m   (centre wavelength of TIRS Band 10)
        rho      = 1.438e-2 mK (= h*c / k_B)
        epsilon  = 0.004 * Pv + 0.986  (emissivity)
        Pv       = ((NDVI - NDVImin) / (NDVImax - NDVImin))^2
        NDVImin  = 0.2, NDVImax = 0.5  (standard thresholds)
"""

import os
import sys
import math
import time
from typing import Any
import ee
import geopandas as gpd
import pandas as pd
from config_loader import load_config

# ---------------------------------------------------------------------------
# 0. Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))

# ---------------------------------------------------------------------------
# Physical constants for LST calculation
# ---------------------------------------------------------------------------
LAMBDA_TIRS = 10.9e-6      # Centre wavelength of Landsat TIRS Band 10 (m)
RHO = 1.438e-2             # h * c / k_B  (m K)
NDVI_MIN = 0.2             # Bare soil / low vegetation threshold
NDVI_MAX = 0.5             # Dense vegetation threshold

# Landsat Collection 2 Level-2 scale factors
SR_SCALE = 0.0000275       # Surface reflectance scale
SR_OFFSET = -0.2           # Surface reflectance offset
ST_SCALE = 0.00341802      # Surface temperature scale
ST_OFFSET = 149.0          # Surface temperature offset (result in Kelvin)


# =====================================================================
# STEP 1 -- Read configuration
# =====================================================================
def get_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    """Extract the configured LST settings into a flat mapping."""
    aoi = cfg["aoi"]
    return {
        "west":  aoi["west"],
        "south": aoi["south"],
        "east":  aoi["east"],
        "north": aoi["north"],
        "start_date": cfg["time_window"]["start"],
        "end_date":   cfg["time_window"]["end"],
        "project": cfg["gee"].get("project", None),
        "l8_collection": cfg["gee"]["landsat8_collection"],
        "l9_collection": cfg["gee"]["landsat9_collection"],
        "scale": cfg["gee"]["reduction_scales_m"]["lst"],
        "grid_path": os.path.join(PROJECT_ROOT, cfg["output_paths"]["grid"]),
        "lst_output": os.path.join(
            PROJECT_ROOT,
            cfg["output_paths"].get("lst_grid", "data/lst_grid.geojson"),
        ),
    }


# =====================================================================
# STEP 2 -- Initialize Earth Engine and create AOI rectangle
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
            print("ERROR: Could not initialize Earth Engine.")
            print('       Run  python -c "import ee; ee.Authenticate()"  first.')
            print(f"       Project: {project}")
            raise SystemExit(1) from exc
    print(f"[OK] Earth Engine initialized (project={project})")


def make_aoi(west: float, south: float, east: float, north: float) -> ee.Geometry:
    """Create an ee.Geometry.Rectangle from bounding-box coordinates."""
    return ee.Geometry.Rectangle([west, south, east, north])


# =====================================================================
# STEP 3 -- Cloud masking for Landsat Collection 2 QA_PIXEL
# =====================================================================
def mask_landsat_clouds(image: ee.Image) -> ee.Image:
    """
    Mask clouds, cloud shadows, cirrus, and fill in a Landsat C2 L2 image
    using the QA_PIXEL band.

    QA_PIXEL bit flags (Collection 2):
        Bit 0  -- Fill
        Bit 1  -- Dilated cloud
        Bit 2  -- Cirrus (high confidence)
        Bit 3  -- Cloud
        Bit 4  -- Cloud shadow

    If ANY of bits 0-4 are set, the pixel is masked out.
    """
    qa = image.select("QA_PIXEL")

    # Create a combined bitmask for bits 0 through 4
    # fill(1) + dilated_cloud(2) + cirrus(4) + cloud(8) + cloud_shadow(16) = 31
    unwanted_bits = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4)

    # Keep only pixels where ALL these bits are zero
    mask = qa.bitwiseAnd(unwanted_bits).eq(0)

    return image.updateMask(mask)


# =====================================================================
# STEP 4 -- Emissivity-corrected LST calculation
# =====================================================================
def add_lst(image: ee.Image) -> ee.Image:
    """
    Compute Land Surface Temperature (LST) in Celsius from a Landsat C2 L2
    image using emissivity correction.

    Steps:
        1. Scale ST_B10 to get brightness temperature (BT) in Kelvin.
        2. Scale SR_B4 (Red) and SR_B5 (NIR) to surface reflectance.
        3. Compute NDVI from the scaled reflectance bands.
        4. Derive proportion of vegetation (Pv) and emissivity (epsilon).
        5. Apply the mono-window LST equation.
        6. Convert Kelvin -> Celsius and add as band 'lst'.

    Returns
    -------
    ee.Image
        The input image with an added 'lst' band (degrees Celsius).
    """
    # --- 1. Brightness temperature in Kelvin from ST_B10 ---
    bt = image.select("ST_B10").multiply(ST_SCALE).add(ST_OFFSET)

    # --- 2. Surface reflectance (scaled) ---
    red = image.select("SR_B4").multiply(SR_SCALE).add(SR_OFFSET)
    nir = image.select("SR_B5").multiply(SR_SCALE).add(SR_OFFSET)

    # --- 3. NDVI ---
    ndvi = nir.subtract(red).divide(nir.add(red)).rename("ndvi_lst")

    # --- 4. Proportion of vegetation (Pv) and emissivity (epsilon) ---
    # Clamp NDVI to [NDVI_MIN, NDVI_MAX] before computing Pv
    ndvi_clamped = ndvi.clamp(NDVI_MIN, NDVI_MAX)
    pv = ndvi_clamped.subtract(NDVI_MIN).divide(NDVI_MAX - NDVI_MIN).pow(2)

    # Emissivity: epsilon = 0.004 * Pv + 0.986
    epsilon = pv.multiply(0.004).add(0.986)

    # --- 5. LST in Kelvin ---
    # LST(K) = BT / (1 + (lambda * BT / rho) * ln(epsilon))
    #
    # Precompute the ratio lambda / rho (dimensionless when BT in K):
    #   lambda / rho = 10.9e-6 / 1.438e-2 = 7.578e-4  (1/K)
    lambda_over_rho = LAMBDA_TIRS / RHO  # ~7.578e-4

    ln_epsilon = epsilon.log()  # natural log of emissivity

    # denominator = 1 + (lambda/rho) * BT * ln(epsilon)
    denominator = bt.multiply(lambda_over_rho).multiply(ln_epsilon).add(1)

    lst_kelvin = bt.divide(denominator)

    # --- 6. Convert to Celsius ---
    lst_celsius = lst_kelvin.subtract(273.15).rename("lst")

    return image.addBands(lst_celsius)


# =====================================================================
# STEP 5 -- Build merged Landsat 8 + 9 composite with LST
# =====================================================================
def get_landsat_lst_composite(
    aoi: ee.Geometry,
    start_date: str,
    end_date: str,
    l8_id: str,
    l9_id: str,
) -> tuple:
    """
    Merge Landsat 8 and 9 collections, apply cloud masking, take the
    median composite, compute LST, and clip to AOI.

    Returns
    -------
    tuple of (ee.Image, ee.Number)
        (LST composite with band 'lst' in Celsius, total scene count)
    """
    # Load and filter both collections
    l8 = (
        ee.ImageCollection(l8_id)
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
    )
    l9 = (
        ee.ImageCollection(l9_id)
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
    )

    # Merge into one collection
    merged = l8.merge(l9)
    scene_count = merged.size()

    # Apply cloud masking to every image
    masked = merged.map(mask_landsat_clouds)

    # Take the median composite of all bands needed for LST
    # (ST_B10 for brightness temp, SR_B4 & SR_B5 for NDVI/emissivity)
    composite = masked.select(["ST_B10", "SR_B4", "SR_B5"]).median()

    # Compute LST on the composite
    composite_with_lst = add_lst(composite)

    # Keep only the LST band, clip to AOI
    lst_image = composite_with_lst.select("lst").clip(aoi)

    return lst_image, scene_count


# =====================================================================
# STEP 6 -- Load fishnet grid as ee.FeatureCollection
# =====================================================================
def load_grid_as_ee_fc(grid_path: str) -> tuple:
    """
    Read the local GeoJSON grid and convert to ee.FeatureCollection,
    preserving cell_id property.
    """
    gdf = gpd.read_file(grid_path)
    print(f"[OK] Loaded grid: {len(gdf)} cells from {grid_path}")

    features = []
    for _, row in gdf.iterrows():
        geom = ee.Geometry(row.geometry.__geo_interface__)
        feat = ee.Feature(geom, {"cell_id": row["cell_id"]})
        features.append(feat)

    fc = ee.FeatureCollection(features)
    return fc, gdf


# =====================================================================
# STEP 7 -- Reduce LST composite to grid cell means
# =====================================================================
def reduce_lst_to_grid(
    lst_image: ee.Image,
    grid_fc: ee.FeatureCollection,
    scale: int = 100,
) -> ee.FeatureCollection:
    """
    Compute the mean LST within each grid cell using reduceRegions.

    Parameters
    ----------
    lst_image : ee.Image
        Single-band LST composite (Celsius).
    grid_fc : ee.FeatureCollection
        Grid cells with cell_id property.
    scale : int
        Pixel resolution in metres. TIRS native resolution is ~100 m
        (resampled to 30 m in Level-2). Using 100 m for performance.
    """
    reduced = lst_image.reduceRegions(
        collection=grid_fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
    )
    return reduced


# =====================================================================
# STEP 8 -- Export to local GeoJSON via getInfo()
# =====================================================================
def export_to_geojson(
    reduced_fc: ee.FeatureCollection,
    local_gdf: gpd.GeoDataFrame,
    output_path: str,
) -> gpd.GeoDataFrame:
    """
    Retrieve reduced features from Earth Engine, merge mean_lst values
    onto the local GeoDataFrame, and save as GeoJSON.

    For ~836 cells this runs within getInfo() limits.
    """
    print("  Fetching results from Earth Engine (this may take 1-3 minutes)...")
    t0 = time.time()

    fc_dict = reduced_fc.getInfo()
    elapsed = time.time() - t0
    print(f"  [OK] Received {len(fc_dict['features'])} features in {elapsed:.1f}s")

    # Build lookup: cell_id -> mean LST
    lst_lookup = {}
    for feat in fc_dict["features"]:
        props = feat["properties"]
        cell_id = props.get("cell_id")
        mean_lst = props.get("mean")  # reduceRegions names it 'mean'
        lst_lookup[cell_id] = mean_lst

    # Merge into local GeoDataFrame
    local_gdf = local_gdf.copy()
    local_gdf["mean_lst"] = local_gdf["cell_id"].map(lst_lookup)

    # Report stats
    valid = local_gdf["mean_lst"].notna().sum()
    print(f"  Cells with valid LST: {valid}/{len(local_gdf)}")
    if valid > 0:
        print(f"  LST range: "
              f"{local_gdf['mean_lst'].min():.2f} - "
              f"{local_gdf['mean_lst'].max():.2f} C")
        print(f"  LST mean:  {local_gdf['mean_lst'].mean():.2f} C")

    # Sanity check: Mumbai pre-monsoon should be 25-50 C
    lst_min = local_gdf["mean_lst"].min()
    lst_max = local_gdf["mean_lst"].max()
    if lst_min < 10 or lst_max > 60:
        print("  [WARNING] LST values outside expected range (25-45 C).")
        print("            Check emissivity parameters or input data.")

    # Keep only required columns
    result = local_gdf[["cell_id", "mean_lst", "geometry"]].copy()

    # Save to GeoJSON
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    result.to_file(output_path, driver="GeoJSON")
    print(f"[OK] Saved LST grid to: {output_path}")

    return result


# =====================================================================
# MAIN
# =====================================================================
def main() -> None:
    """Fetch configured Landsat land-surface temperatures for the grid."""
    print("=" * 60)
    print("  City Sense -- Week 3: Fetch LST")
    print("=" * 60)

    # ---- Step 1: Configuration -------------------------------------------
    cfg = load_config()
    s = get_settings(cfg)
    print(f"\nAOI        : W={s['west']}, S={s['south']}, E={s['east']}, N={s['north']}")
    print(f"Time window: {s['start_date']} -> {s['end_date']}")
    print(f"Collections: {s['l8_collection']} + {s['l9_collection']}")
    print(f"Grid input : {s['grid_path']}")
    print(f"LST output : {s['lst_output']}")
    print()

    # ---- Step 2: Initialize Earth Engine ---------------------------------
    init_ee(project=s["project"])
    aoi_geom = make_aoi(s["west"], s["south"], s["east"], s["north"])

    # ---- Step 3-5: Build LST composite -----------------------------------
    print("> Building cloud-masked Landsat 8+9 LST composite...")
    lst_composite, scene_count = get_landsat_lst_composite(
        aoi=aoi_geom,
        start_date=s["start_date"],
        end_date=s["end_date"],
        l8_id=s["l8_collection"],
        l9_id=s["l9_collection"],
    )
    n_scenes = scene_count.getInfo()
    print(f"  Landsat 8+9 scenes matched: {n_scenes}")
    if n_scenes == 0:
        print("  [WARNING] No scenes found! Try widening the date range.")
        sys.exit(1)

    # ---- Step 6: Load grid as ee.FeatureCollection -----------------------
    print("\n> Loading grid into Earth Engine...")
    grid_fc, local_gdf = load_grid_as_ee_fc(s["grid_path"])

    # ---- Step 7: Reduce to grid cell means (scale=100m) ------------------
    print(f"\n> Reducing LST to grid cell means (scale={s['scale']} m)...")
    reduced_fc = reduce_lst_to_grid(lst_composite, grid_fc, scale=s["scale"])

    # ---- Step 8: Export to local GeoJSON ---------------------------------
    print("\n> Exporting results...")
    result_gdf = export_to_geojson(reduced_fc, local_gdf, s["lst_output"])

    print("\n" + "=" * 60)
    print("  [OK] Week 3 complete - LST layer generated!")
    print("=" * 60)


if __name__ == "__main__":
    main()
