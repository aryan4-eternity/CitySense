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
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np


# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
LST_PATH = os.path.join(PROJECT_ROOT, "data", "lst_grid.geojson")
OUTPUT_PNG = os.path.join(PROJECT_ROOT, "data", "lst_validation.png")


def main():
    # ---- Load the LST grid -------------------------------------------------
    if not os.path.exists(LST_PATH):
        print(f"ERROR: LST file not found at {LST_PATH}")
        print("Run  python ingestion/fetch_lst.py  first.")
        return

    gdf = gpd.read_file(LST_PATH)
    print(f"Loaded {len(gdf)} cells from {LST_PATH}")
    print(f"Columns: {list(gdf.columns)}")

    # ---- Quick stats -------------------------------------------------------
    valid = gdf["mean_lst"].notna()
    print(f"\nValid LST values: {valid.sum()}/{len(gdf)}")
    if valid.sum() > 0:
        print(f"  Min   : {gdf.loc[valid, 'mean_lst'].min():.2f} C")
        print(f"  Max   : {gdf.loc[valid, 'mean_lst'].max():.2f} C")
        print(f"  Mean  : {gdf.loc[valid, 'mean_lst'].mean():.2f} C")
        print(f"  Median: {gdf.loc[valid, 'mean_lst'].median():.2f} C")

    # ---- Plausibility check ------------------------------------------------
    lst_min = gdf.loc[valid, "mean_lst"].min()
    lst_max = gdf.loc[valid, "mean_lst"].max()
    if lst_min >= 20 and lst_max <= 50:
        print("\n  [OK] LST values are in the expected range for Mumbai pre-monsoon.")
    else:
        print(f"\n  [NOTE] LST range ({lst_min:.1f} - {lst_max:.1f} C) is outside "
              "the typical 25-45 C band. Check data quality.")

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
    plt.savefig(OUTPUT_PNG, dpi=150, bbox_inches="tight")
    print(f"\n[OK] Validation plot saved to: {OUTPUT_PNG}")
    plt.close()


if __name__ == "__main__":
    main()
