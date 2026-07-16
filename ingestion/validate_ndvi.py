"""
validate_ndvi.py
================
Loads data/ndvi_grid.geojson, plots the grid colored by mean_ndvi
using a green colour map, adds a colourbar, and saves the figure
as data/ndvi_validation.png.

Expected visual:
    - Sanjay Gandhi National Park (north-central) → dark green (high NDVI)
    - Dense built-up areas → light/yellow tones (low NDVI)

Usage:
    python ingestion/validate_ndvi.py        (from project root)
    python -m ingestion.validate_ndvi        (from project root)
"""

import os
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend — safe for scripts
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from config_loader import load_config


# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
def main() -> None:
    """Create a visual validation plot for the configured NDVI output."""
    config = load_config()
    ndvi_path = os.path.join(PROJECT_ROOT, config["output_paths"]["ndvi_grid"])
    output_png = os.path.join(PROJECT_ROOT, config["output_paths"]["ndvi_validation"])
    # ---- Load the NDVI grid ------------------------------------------------
    if not os.path.exists(ndvi_path):
        print(f"ERROR: NDVI file not found at {ndvi_path}")
        print("Run  python ingestion/fetch_ndvi.py  first.")
        return

    gdf = gpd.read_file(ndvi_path)
    print(f"Loaded {len(gdf)} cells from {ndvi_path}")
    print(f"Columns: {list(gdf.columns)}")

    # ---- Quick stats -------------------------------------------------------
    valid = gdf["mean_ndvi"].notna()
    print(f"\nValid NDVI values: {valid.sum()}/{len(gdf)}")
    if valid.sum() > 0:
        print(f"  Min  : {gdf.loc[valid, 'mean_ndvi'].min():.4f}")
        print(f"  Max  : {gdf.loc[valid, 'mean_ndvi'].max():.4f}")
        print(f"  Mean : {gdf.loc[valid, 'mean_ndvi'].mean():.4f}")
        print(f"  Median: {gdf.loc[valid, 'mean_ndvi'].median():.4f}")

    # ---- Plot with greens colourmap ----------------------------------------
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))

    # Fill NaN values with 0 for plotting (they'll show as lightest colour)
    plot_data = gdf.copy()
    plot_data["mean_ndvi"] = plot_data["mean_ndvi"].fillna(0)

    # Use a greens colour map — low NDVI is light, high NDVI is dark green
    vmin = 0.0
    vmax = max(plot_data["mean_ndvi"].max(), 0.6)  # floor at 0.6 for scale

    plot_data.plot(
        column="mean_ndvi",
        cmap="Greens",
        edgecolor="gray",
        linewidth=0.2,
        ax=ax,
        vmin=vmin,
        vmax=vmax,
        legend=False,
    )

    # ---- Add colour bar ----------------------------------------------------
    sm = plt.cm.ScalarMappable(
        cmap="Greens",
        norm=mcolors.Normalize(vmin=vmin, vmax=vmax),
    )
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label("Mean NDVI", fontsize=12)

    # ---- Labels and title --------------------------------------------------
    ax.set_title(
        "Mumbai AOI — Mean NDVI (Sentinel-2, Pre-Monsoon 2023)",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xlabel("Longitude", fontsize=11)
    ax.set_ylabel("Latitude", fontsize=11)
    ax.ticklabel_format(useOffset=False)

    # ---- Annotate key areas (approximate locations) ------------------------
    # Sanjay Gandhi National Park — roughly centred at (72.87, 19.21)
    ax.annotate(
        "Sanjay Gandhi\nNational Park",
        xy=(72.87, 19.21),
        xytext=(72.78, 19.24),
        fontsize=9,
        fontstyle="italic",
        color="darkgreen",
        arrowprops=dict(arrowstyle="->", color="darkgreen", lw=1.2),
    )

    plt.tight_layout()
    plt.savefig(output_png, dpi=150, bbox_inches="tight")
    print(f"\n[OK] Validation plot saved to: {output_png}")
    plt.close()


if __name__ == "__main__":
    main()
