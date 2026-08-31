"""
validate_grid.py
================
Loads data/grid.geojson, plots the grid cells colored by cell_id,
and saves the result as data/grid_validation.png.

Usage:
    python -m ingestion.validate_grid        (from project root)
    python ingestion/validate_grid.py        (from project root)
"""

import logging
import os
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for saving to file
import matplotlib.pyplot as plt
from config_loader import load_config

logger = logging.getLogger("CitySense.ingestion.validate_grid")

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
def main() -> None:
    """Create a visual validation plot for the configured grid output."""
    config = load_config()
    grid_path = os.path.join(PROJECT_ROOT, config["output_paths"]["grid"])
    output_png = os.path.join(PROJECT_ROOT, config["output_paths"]["grid_validation"])
    # ---- Load the grid GeoJSON ---------------------------------------------
    if not os.path.exists(grid_path):
        logger.error("Grid file not found at %s", grid_path)
        logger.error("Run  python ingestion/generate_grid.py  first.")
        return

    grid = gpd.read_file(grid_path)
    logger.info("Loaded %d cells from %s", len(grid), grid_path)
    logger.debug("Grid head:\n%s", str(grid.head()))

    # ---- Plot --------------------------------------------------------------
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))

    # Create a numeric index for coloring (matplotlib needs numeric values)
    grid["color_idx"] = range(len(grid))
    grid.plot(
        column="color_idx",
        cmap="viridis",
        edgecolor="black",
        linewidth=0.3,
        ax=ax,
        legend=False,
    )

    ax.set_title("Mumbai AOI – Fishnet Grid (colored by cell_id)", fontsize=14)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.ticklabel_format(useOffset=False)  # avoid scientific notation on axes

    plt.tight_layout()
    plt.savefig(output_png, dpi=150)
    logger.info("Validation plot saved to: %s", output_png)
    plt.close()


if __name__ == "__main__":
    main()
