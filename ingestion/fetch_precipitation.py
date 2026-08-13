"""
fetch_precipitation.py
======================
Pulls CHIRPS daily precipitation data from Google Earth Engine for the
Mumbai AOI during the **monsoon season** (June–September), computes
mean daily rainfall and cumulative monsoon total per grid cell, and
saves the result as data/precipitation_grid.geojson.

SEASONAL NOTE — IMPORTANT
--------------------------
The existing pipeline imagery window (config.yaml `time_window`) covers
March–May 2023 — Mumbai's dry/pre-monsoon season. Precipitation as a
flood driver must be measured during the monsoon (June–September).
This script therefore uses a **separate, fixed monsoon window**
(MONSOON_START / MONSOON_END below) rather than the config time_window.
This seasonal split is intentional and documented in
CITYSENSE_TECHNICAL_DOCUMENTATION.md §FSI.

The other FSI inputs (DEM, NDBI, drainage proxy) are season-independent
and may be drawn from the main pipeline outputs without seasonal conflict.

DATA SOURCE
-----------
UCSB-CHG/CHIRPS/DAILY — Climate Hazards Group InfraRed Precipitation
with Station data. Daily, ~5.5 km resolution, 1981–present.
DOI: 10.1038/sdata.2015.66

Usage:
    python ingestion/fetch_precipitation.py    (from project root)
    python -m ingestion.fetch_precipitation
"""

from __future__ import annotations

import os
import sys
import time
import logging
from typing import Any

import ee
import geopandas as gpd

_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, os.pardir))
sys.path.insert(0, _PROJECT_ROOT)

from config_loader import load_config

logger = logging.getLogger("CitySense.ingestion.fetch_precipitation")

# ---------------------------------------------------------------------------
# Monsoon window — Mumbai peak flood season.
# Using 2023 to match the rest of the pipeline's imagery year.
# ---------------------------------------------------------------------------
MONSOON_START = "2023-06-01"
MONSOON_END   = "2023-09-30"

CHIRPS_COLLECTION = "UCSB-CHG/CHIRPS/DAILY"


# ---------------------------------------------------------------------------
# EE helpers — mirroring the pattern in fetch_ndvi.py / fetch_lst.py
# ---------------------------------------------------------------------------

def init_ee(project: str | None = None) -> None:
    """Initialize Earth Engine."""
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
            logger.critical("Run: python -c \"import ee; ee.Authenticate()\"")
            raise SystemExit(1) from exc
    logger.info("Earth Engine initialized (project=%s)", project)


def make_aoi(west: float, south: float, east: float, north: float) -> ee.Geometry:
    return ee.Geometry.Rectangle([west, south, east, north])


def load_grid_as_ee_fc(grid_path: str) -> tuple[ee.FeatureCollection, gpd.GeoDataFrame]:
    """Load grid GeoJSON and convert to ee.FeatureCollection."""
    gdf = gpd.read_file(grid_path)
    logger.info("Loaded grid: %d cells from %s", len(gdf), grid_path)
    features = []
    for _, row in gdf.iterrows():
        geom = ee.Geometry(row.geometry.__geo_interface__)
        feat = ee.Feature(geom, {"cell_id": row["cell_id"]})
        features.append(feat)
    return ee.FeatureCollection(features), gdf


# ---------------------------------------------------------------------------
# Precipitation composite
# ---------------------------------------------------------------------------

def get_chirps_precipitation(
    aoi: ee.Geometry,
    start_date: str,
    end_date: str,
) -> tuple[ee.Image, ee.Image, int]:
    """
    Build mean-daily and cumulative monsoon precipitation images from CHIRPS.

    Parameters
    ----------
    aoi        : ee.Geometry
    start_date : ISO date string (MONSOON_START)
    end_date   : ISO date string (MONSOON_END)

    Returns
    -------
    (mean_daily_img, cumulative_img, n_days)
        mean_daily_img  : mean daily rainfall mm/day, clipped to AOI, band 'mean_precip'
        cumulative_img  : cumulative monsoon total mm, clipped to AOI, band 'cumul_precip'
        n_days          : number of days in the collection
    """
    chirps = (
        ee.ImageCollection(CHIRPS_COLLECTION)
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
        .select("precipitation")
    )

    n_days = chirps.size().getInfo()
    logger.info("CHIRPS images found: %d days in [%s, %s]", n_days, start_date, end_date)

    if n_days == 0:
        raise RuntimeError(
            f"No CHIRPS data found for {start_date}–{end_date} over the AOI. "
            "Check GEE project permissions and AOI coordinates."
        )

    mean_daily = (
        chirps.mean()
        .rename("mean_precip")
        .clip(aoi)
    )

    cumulative = (
        chirps.sum()
        .rename("cumul_precip")
        .clip(aoi)
    )

    return mean_daily, cumulative, n_days


# ---------------------------------------------------------------------------
# Reduce to grid cells
# ---------------------------------------------------------------------------

def reduce_to_grid(
    mean_img: ee.Image,
    cumul_img: ee.Image,
    grid_fc: ee.FeatureCollection,
    scale: int = 5566,  # CHIRPS native resolution ~5.5km, use 5566m
) -> ee.FeatureCollection:
    """
    Reduce mean and cumulative precipitation images to per-cell means.

    CHIRPS resolution is ~5.5 km. Mumbai's 1km grid cells are smaller than
    one CHIRPS pixel, so each cell will typically inherit the value of the
    single CHIRPS pixel it falls in. This is physically correct — all cells
    in the same ~5.5km CHIRPS pixel receive the same precipitation value.
    """
    combined = mean_img.addBands(cumul_img)
    reduced = combined.reduceRegions(
        collection=grid_fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
    )
    return reduced


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_to_geojson(
    reduced_fc: ee.FeatureCollection,
    local_gdf: gpd.GeoDataFrame,
    output_path: str,
) -> gpd.GeoDataFrame:
    """Retrieve results from EE and save as GeoJSON."""
    logger.info("Fetching precipitation results from Earth Engine …")
    t0 = time.time()
    fc_dict = reduced_fc.getInfo()
    elapsed = time.time() - t0
    logger.info("Received %d features in %.1fs", len(fc_dict["features"]), elapsed)

    # Build lookups
    mean_lookup:  dict[str, float] = {}
    cumul_lookup: dict[str, float] = {}

    for feat in fc_dict["features"]:
        props   = feat["properties"]
        cell_id = props.get("cell_id")
        # reduceRegions with multiple bands returns one mean per band
        mean_lookup[cell_id]  = props.get("mean_precip")
        cumul_lookup[cell_id] = props.get("cumul_precip")

    local_gdf = local_gdf.copy()
    local_gdf["mean_precip"]  = local_gdf["cell_id"].map(mean_lookup)
    local_gdf["cumul_precip"] = local_gdf["cell_id"].map(cumul_lookup)

    valid_mean  = local_gdf["mean_precip"].notna().sum()
    valid_cumul = local_gdf["cumul_precip"].notna().sum()
    logger.info("Cells with valid mean_precip:  %d/%d", valid_mean,  len(local_gdf))
    logger.info("Cells with valid cumul_precip: %d/%d", valid_cumul, len(local_gdf))

    if valid_mean > 0:
        logger.info(
            "mean_precip  range: %.2f – %.2f mm/day  (mean %.2f)",
            local_gdf["mean_precip"].min(),
            local_gdf["mean_precip"].max(),
            local_gdf["mean_precip"].mean(),
        )
        logger.info(
            "cumul_precip range: %.1f – %.1f mm  (mean %.1f)",
            local_gdf["cumul_precip"].min(),
            local_gdf["cumul_precip"].max(),
            local_gdf["cumul_precip"].mean(),
        )

    result = local_gdf[["cell_id", "mean_precip", "cumul_precip", "geometry"]].copy()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    result.to_file(output_path, driver="GeoJSON")
    logger.info("Saved precipitation grid → %s", output_path)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Fetch CHIRPS monsoon precipitation per grid cell."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("=== CitySense — Fetch Precipitation (CHIRPS monsoon %s–%s) ===",
                MONSOON_START, MONSOON_END)
    logger.info("NOTE: monsoon window is independent of config.yaml time_window "
                "(dry-season). This is intentional — see module docstring.")

    cfg          = load_config()
    aoi_cfg      = cfg["aoi"]
    gee_project  = cfg["gee"].get("project")
    grid_path    = os.path.join(_PROJECT_ROOT, cfg["output_paths"]["grid"])
    output_path  = os.path.join(_PROJECT_ROOT,
                                cfg["output_paths"].get(
                                    "precipitation_grid",
                                    "data/precipitation_grid.geojson"))

    logger.info("GEE project : %s", gee_project)
    logger.info("Grid input  : %s", grid_path)
    logger.info("Output      : %s", output_path)

    # Init EE
    init_ee(project=gee_project)

    aoi = make_aoi(
        aoi_cfg["west"], aoi_cfg["south"],
        aoi_cfg["east"], aoi_cfg["north"],
    )

    # Build CHIRPS composite
    logger.info("Building CHIRPS precipitation composite …")
    mean_img, cumul_img, n_days = get_chirps_precipitation(
        aoi, MONSOON_START, MONSOON_END
    )
    logger.info("Monsoon window: %d days of CHIRPS data.", n_days)

    # Load grid and reduce
    logger.info("Loading grid and reducing to cell means …")
    grid_fc, local_gdf = load_grid_as_ee_fc(grid_path)

    logger.info("Reducing (scale=5566m — CHIRPS native resolution) …")
    reduced_fc = reduce_to_grid(mean_img, cumul_img, grid_fc)

    # Export
    export_to_geojson(reduced_fc, local_gdf, output_path)

    logger.info("=== Precipitation fetch complete! ===")


if __name__ == "__main__":
    main()
