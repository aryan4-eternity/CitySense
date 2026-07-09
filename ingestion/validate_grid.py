"""
validate_grid.py
================
Loads data/grid.geojson, plots the grid cells colored by cell_id,
and saves the result as data/grid_validation.png.

Usage:
    python -m ingestion.validate_grid        (from project root)
    python ingestion/validate_grid.py        (from project root)
"""

import os
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for saving to file
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
GRID_PATH = os.path.join(PROJECT_ROOT, "data", "grid.geojson")
OUTPUT_PNG = os.path.join(PROJECT_ROOT, "data", "grid_validation.png")


def main():
    # ---- Load the grid GeoJSON ---------------------------------------------
    if not os.path.exists(GRID_PATH):
        print(f"ERROR: Grid file not found at {GRID_PATH}")
        print("Run  python ingestion/generate_grid.py  first.")
        return

    grid = gpd.read_file(GRID_PATH)
    print(f"Loaded {len(grid)} cells from {GRID_PATH}")
    print(grid.head())

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
    plt.savefig(OUTPUT_PNG, dpi=150)
    print(f"Validation plot saved to: {OUTPUT_PNG}")
    plt.close()


if __name__ == "__main__":
    main()
