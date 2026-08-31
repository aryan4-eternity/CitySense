"""
validate_lst.py
===============
Loads data/lst_grid.geojson, plots the grid colored by mean_lst
using a temperature-appropriate colormap, adds a colorbar, and saves
the figure as data/lst_validation.png.

Expected visual:
    - Cooler tones in Sanjay Gandhi National Park (north) ~28-32 C
    - Hotter tones in dense built-up areas (Dadar, Kurla, etc.) ~38-45 C
    - Urban Heat Island (UHI) pattern clearly visible

Usage:
    python ingestion/validate_lst.py         (from project root)
    python -m ingestion.validate_lst         (from project root)
"""

import os
import logging
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from config_loader import load_config

logger = logging.getLogger("CitySense.ingestion.validate_lst")


# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
def main() -> None:
    """Create a visual validation plot for the configured LST output."""
    config = load_config()
    lst_path = os.path.join(PROJECT_ROOT, config["output_paths"]["lst_grid"])
    output_png = os.path.join(PROJECT_ROOT, config["output_paths"]["lst_validation"])
    # ---- Load the LST grid -------------------------------------------------
    if not os.path.exists(lst_path):
        logger.error("LST file not found at %s", lst_path)
        logger.error("Run python ingestion/fetch_lst.py first.")
        return

    gdf = gpd.read_file(lst_path)
    logger.info("Loaded %d cells from %s", len(gdf), lst_path)
    logger.info("Columns: %s", list(gdf.columns))

    # ---- Quick stats -------------------------------------------------------
    valid = gdf["mean_lst"].notna()
    logger.info("Valid LST values: %d/%d", valid.sum(), len(gdf))
    if valid.sum() > 0:
        logger.info("Min   : %.2f C", gdf.loc[valid, 'mean_lst'].min())
        logger.info("Max   : %.2f C", gdf.loc[valid, 'mean_lst'].max())
        logger.info("Mean  : %.2f C", gdf.loc[valid, 'mean_lst'].mean())
        logger.info("Median: %.2f C", gdf.loc[valid, 'mean_lst'].median())

    # ---- Plausibility check ------------------------------------------------
    lst_min = gdf.loc[valid, "mean_lst"].min()
    lst_max = gdf.loc[valid, "mean_lst"].max()
    if lst_min >= 20 and lst_max <= 50:
        logger.info("LST values are in the expected range for Mumbai pre-monsoon.")
    else:
        logger.warning(
            "LST range (%.1f - %.1f C) is outside the typical 25-45 C band. Check data quality.",
            lst_min, lst_max
        )

    # ---- Plot with temperature colormap ------------------------------------
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))

    # Fill NaN with the median for plotting
    plot_data = gdf.copy()
    median_val = plot_data["mean_lst"].median()
    plot_data["mean_lst"] = plot_data["mean_lst"].fillna(median_val)

    # Colour scale: use hot_r (reversed 'hot') for intuitive temp mapping
    # cool = blue/purple, warm = red/yellow
    vmin = plot_data["mean_lst"].quantile(0.02)
    vmax = plot_data["mean_lst"].quantile(0.98)

    plot_data.plot(
        column="mean_lst",
        cmap="RdYlBu_r",  # Red (hot) -> Yellow -> Blue (cool), reversed
        edgecolor="gray",
        linewidth=0.2,
        ax=ax,
        vmin=vmin,
        vmax=vmax,
        legend=False,
    )

    # ---- Add colour bar ----------------------------------------------------
    sm = plt.cm.ScalarMappable(
        cmap="RdYlBu_r",
        norm=mcolors.Normalize(vmin=vmin, vmax=vmax),
    )
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label("Mean LST (C)", fontsize=12)

    # ---- Labels and title --------------------------------------------------
    ax.set_title(
        "Mumbai AOI -- Land Surface Temperature (Landsat 8+9, Pre-Monsoon 2023)",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xlabel("Longitude", fontsize=11)
    ax.set_ylabel("Latitude", fontsize=11)
    ax.ticklabel_format(useOffset=False)

    # ---- Annotate key areas ------------------------------------------------
    # Sanjay Gandhi National Park (cooler)
    ax.annotate(
        "SGNP (cooler)",
        xy=(72.87, 19.21),
        xytext=(72.78, 19.24),
        fontsize=9,
        fontstyle="italic",
        color="navy",
        arrowprops=dict(arrowstyle="->", color="navy", lw=1.2),
    )

    # Dense built-up area (hotter)
    ax.annotate(
        "Built-up (hotter)",
        xy=(72.85, 19.03),
        xytext=(72.78, 18.96),
        fontsize=9,
        fontstyle="italic",
        color="darkred",
        arrowprops=dict(arrowstyle="->", color="darkred", lw=1.2),
    )

    plt.tight_layout()
    plt.savefig(output_png, dpi=150, bbox_inches="tight")
    logger.info("Validation plot saved to: %s", output_png)
    plt.close()


if __name__ == "__main__":
    main()
