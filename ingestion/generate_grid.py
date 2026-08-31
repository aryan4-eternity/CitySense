"""
generate_grid.py
================
Reads the AOI bounds and grid cell size from config/config.yaml,
creates a fishnet grid (~1 km × 1 km) over Mumbai,
assigns each cell a unique cell_id, clips to the AOI bounding box,
and saves the result as data/grid.geojson.

Usage:
    python -m ingestion.generate_grid        (from project root)
    python ingestion/generate_grid.py        (from project root)
"""

import logging
import os
import numpy as np
import geopandas as gpd
from shapely.geometry import box, Polygon
from config_loader import load_config

logger = logging.getLogger("CitySense.ingestion.generate_grid")

# ---------------------------------------------------------------------------
# 1. Resolve paths – make sure project resources can be found regardless of
#    the script is invoked.
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))


def create_fishnet_grid(
    west: float, south: float, east: float, north: float, cell_size: float
) -> gpd.GeoDataFrame:
    """
    Create a fishnet (rectangular) grid of cells over the given bounding box.

    Parameters
    ----------
    west, south, east, north : float
        Bounding-box coordinates in decimal degrees.
    cell_size : float
        Cell size in decimal degrees (≈ 0.01° ≈ 1 km at Mumbai's latitude).

    Returns
    -------
    geopandas.GeoDataFrame
        A GeoDataFrame with columns ``cell_id`` and ``geometry``.
    """
    # Generate the edges of every row and column
    x_coords = np.arange(west, east, cell_size)
    y_coords = np.arange(south, north, cell_size)

    polygons = []
    cell_ids = []

    for row_idx, y in enumerate(y_coords):
        for col_idx, x in enumerate(x_coords):
            # Build the cell polygon
            cell = box(
                x,                              # min x
                y,                              # min y
                min(x + cell_size, east),        # max x (clipped to AOI east)
                min(y + cell_size, north),       # max y (clipped to AOI north)
            )
            polygons.append(cell)
            cell_ids.append(f"r{row_idx}_c{col_idx}")

    # Assemble into a GeoDataFrame with WGS-84 CRS
    gdf = gpd.GeoDataFrame(
        {"cell_id": cell_ids},
        geometry=polygons,
        crs="EPSG:4326",
    )
    return gdf


def clip_to_aoi(
    gdf: gpd.GeoDataFrame,
    west: float, south: float, east: float, north: float,
) -> gpd.GeoDataFrame:
    """
    Clip the grid to the AOI bounding box.
    (In this case the grid is already built within the bbox, so this is a
    safety step that removes any cells that might fall outside.)
    """
    aoi_box = box(west, south, east, north)
    clipped = gdf[gdf.geometry.intersects(aoi_box)].copy()
    clipped.reset_index(drop=True, inplace=True)
    return clipped


def main() -> None:
    """Generate and persist the configured fishnet grid."""
    # ---- Load configuration ------------------------------------------------
    cfg = load_config()

    aoi = cfg["aoi"]
    west, south = aoi["west"], aoi["south"]
    east, north = aoi["east"], aoi["north"]
    cell_size = cfg["grid"]["cell_size_deg"]
    output_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["grid"])

    logger.info("AOI  : W=%s, S=%s, E=%s, N=%s", west, south, east, north)
    logger.info("Cell : %s deg ~ 1 km", cell_size)

    # ---- Generate the fishnet grid -----------------------------------------
    grid = create_fishnet_grid(west, south, east, north, cell_size)
    logger.info("Total cells generated: %d", len(grid))

    # ---- Clip to AOI -------------------------------------------------------
    grid = clip_to_aoi(grid, west, south, east, north)
    logger.info("Cells after clipping : %d", len(grid))

    # ---- Save to GeoJSON ---------------------------------------------------
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    grid.to_file(output_path, driver="GeoJSON")
    logger.info("Grid saved to: %s", output_path)


if __name__ == "__main__":
    main()
