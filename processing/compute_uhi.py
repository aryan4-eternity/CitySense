"""
compute_uhi.py
==============
Computes the Urban Heat Island (UHI) intensity for each cell by comparing
its LST to a rural/green baseline (Sanjay Gandhi National Park).

UHI_intensity = LST_cell - LST_baseline_mean

Adds 'uhi_intensity' column to data/cells_master.geojson and creates a map.

Usage:
    python processing/compute_uhi.py
"""

import os
import logging
import geopandas as gpd
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from config_loader import load_config

logger = logging.getLogger("CitySense.processing.compute_uhi")

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))


def main() -> None:
    """Compute Urban Heat Island intensity relative to a green baseline."""
    logger.info("=== City Sense -- Week 5: Compute UHI Intensity ===")

    cfg = load_config()
    master_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["master_data"])
    output_png = os.path.join(PROJECT_ROOT, "data", "uhi_map.png")
    baseline = cfg["processing"]["uhi_baseline"]

    # ---- 1. Load data ------------------------------------------------------
    gdf = gpd.read_file(master_path)
    logger.info("Loaded %d cells from %s", len(gdf), master_path)

    # ---- 2. Define baseline zone (SGNP) ------------------------------------
    b_minx, b_maxx = baseline["lon_min"], baseline["lon_max"]
    b_miny, b_maxy = baseline["lat_min"], baseline["lat_max"]
    logger.info("Baseline zone defined as: lon [%s, %s], lat [%s, %s]", b_minx, b_maxx, b_miny, b_maxy)

    # Find centroids to see which cells fall in the baseline box
    centroids = gdf.geometry.centroid
    in_baseline = (
        (centroids.x >= b_minx) & (centroids.x <= b_maxx) &
        (centroids.y >= b_miny) & (centroids.y <= b_maxy)
    )

    baseline_cells = gdf[in_baseline]
    logger.info("Selected %d cells as the baseline reference.", len(baseline_cells))

    if len(baseline_cells) == 0:
        logger.error("No cells found in the baseline bounding box. Check coordinates.")
        return

    # ---- 3. Compute baseline mean LST --------------------------------------
    ref_temp = baseline_cells["mean_lst"].mean()
    logger.info("Rural/Green reference temperature (mean): %.2f C", ref_temp)

    # ---- 4. Calculate UHI intensity ----------------------------------------
    gdf["uhi_intensity"] = gdf["mean_lst"] - ref_temp

    logger.info("UHI Intensity stats:")
    logger.info("  Min : %.2f C", gdf["uhi_intensity"].min())
    logger.info("  Max : %.2f C", gdf["uhi_intensity"].max())
    logger.info("  Mean: %.2f C", gdf["uhi_intensity"].mean())

    # Verification: built-up cells should have positive UHI
    hot_cells = gdf[gdf["uhi_intensity"] > 5.0]
    logger.info("Number of cells with UHI > +5 C: %d", len(hot_cells))
    if "mean_ndbi" in gdf.columns:
        hot_ndbi_mean = hot_cells["mean_ndbi"].mean()
        logger.info("Mean NDBI of these hot cells: %.3f (expect positive/high)", hot_ndbi_mean)

    # ---- 5. Save updated master data ---------------------------------------
    gdf.to_file(master_path, driver="GeoJSON")
    logger.info("Updated master dataset with 'uhi_intensity' column.")

    # ---- 6. Generate UHI Map -----------------------------------------------
    logger.info("Generating UHI map...")
    fig, ax = plt.subplots(1, 1, figsize=(10, 10))

    # A diverging colormap is perfect for UHI:
    # Blue for cooler than ref, White for neutral, Red for hotter
    # We centre the colormap at 0.
    vmin = -3.0
    vmax = 12.0
    
    # Create a custom normalization centered at 0
    class MidpointNormalize(mcolors.Normalize):
        def __init__(self, vmin=None, vmax=None, midpoint=None, clip=False):
            self.midpoint = midpoint
            mcolors.Normalize.__init__(self, vmin, vmax, clip)

        def __call__(self, value, clip=None):
            x, y = [self.vmin, self.midpoint, self.vmax], [0, 0.5, 1]
            return np.ma.masked_array(np.interp(value, x, y))

    import numpy as np
    norm = MidpointNormalize(vmin=vmin, vmax=vmax, midpoint=0)

    # Fill NaN with 0 for plotting safety
    plot_data = gdf.copy()
    plot_data["uhi_intensity"] = plot_data["uhi_intensity"].fillna(0)

    plot_data.plot(
        column="uhi_intensity",
        cmap="coolwarm",
        norm=norm,
        edgecolor="none",
        ax=ax,
        legend=False,
    )

    # Add colorbar
    sm = plt.cm.ScalarMappable(cmap="coolwarm", norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label("UHI Intensity (C)", fontsize=12)

    # Add a rectangle showing the baseline area
    from matplotlib.patches import Rectangle
    rect = Rectangle(
        (b_minx, b_miny), b_maxx - b_minx, b_maxy - b_miny,
        linewidth=2, edgecolor='darkgreen', facecolor='none', linestyle='--'
    )
    ax.add_patch(rect)
    ax.annotate("Baseline\n(SGNP)", xy=(b_maxx, b_maxy), xytext=(b_maxx+0.01, b_maxy),
                color='darkgreen', weight='bold', fontsize=9)

    ax.set_title("Mumbai UHI Intensity (Relative to SGNP Baseline)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.ticklabel_format(useOffset=False)

    plt.tight_layout()
    plt.savefig(output_png, dpi=150, bbox_inches="tight")
    logger.info("Saved UHI map to: %s", output_png)
    plt.close()

    logger.info("=== UHI computation complete! ===")


if __name__ == "__main__":
    main()
