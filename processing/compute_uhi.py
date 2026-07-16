"""
compute_uhi.py
==============
Computes Urban Heat Island (UHI) intensity for each grid cell by comparing
its LST to a baseline "cool/green" reference zone (Sanjay Gandhi National
Park / Aarey Colony area).

UHI_intensity = cell_LST - rural_reference_temp

Also generates a UHI map showing the spatial distribution of heat island
intensity across Mumbai.

Usage:
    python processing/compute_uhi.py         (from project root)
"""

import os
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from config_loader import load_config

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))

# Sanjay Gandhi National Park / Aarey Colony baseline bounding box
# This covers the core forested area used as the "rural/green" reference
def main() -> None:
    """Add UHI intensity and its configured map artifact to the master data."""
    print("=" * 60)
    print("  City Sense -- Week 4: Compute UHI Intensity")
    print("=" * 60)

    cfg = load_config()
    master_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["master_data"])
    output_png = os.path.join(PROJECT_ROOT, cfg["output_paths"]["uhi_map"])
    park_bbox = cfg["uhi"]["reference_bbox"]

    # ---- Load master dataset -----------------------------------------------
    gdf = gpd.read_file(master_path)
    print(f"\nLoaded {len(gdf)} cells from {master_path}")
    print(f"Columns: {list(gdf.columns)}")

    # ---- Define baseline zone (SGNP) using centroid filter -----------------
    print(f"\n> Baseline zone (SGNP): "
          f"lon [{park_bbox['west']}, {park_bbox['east']}], "
          f"lat [{park_bbox['south']}, {park_bbox['north']}]")

    # Compute centroids for filtering
    centroids = gdf.geometry.centroid
    cx = centroids.x
    cy = centroids.y

    # Filter cells whose centroids fall within the park bounding box
    park_mask = (
        (cx >= park_bbox["west"]) & (cx <= park_bbox["east"]) &
        (cy >= park_bbox["south"]) & (cy <= park_bbox["north"])
    )
    park_cells = gdf[park_mask]
    print(f"  Baseline cells selected: {len(park_cells)}")

    if len(park_cells) == 0:
        print("  [ERROR] No cells found in the park bounding box!")
        print("  Adjust PARK_BBOX coordinates in compute_uhi.py.")
        return

    # ---- Compute rural reference temperature --------------------------------
    rural_ref_temp = park_cells["mean_lst"].mean()
    print(f"  Rural reference temperature (mean LST of SGNP cells): {rural_ref_temp:.2f} C")

    # ---- Compute UHI intensity for every cell --------------------------------
    gdf["uhi_intensity"] = gdf["mean_lst"] - rural_ref_temp

    # Stats
    print(f"\n> UHI Intensity Statistics:")
    print(f"  Min   : {gdf['uhi_intensity'].min():.2f} C")
    print(f"  Max   : {gdf['uhi_intensity'].max():.2f} C")
    print(f"  Mean  : {gdf['uhi_intensity'].mean():.2f} C")
    print(f"  Median: {gdf['uhi_intensity'].median():.2f} C")

    # Verify: park cells should have negative or near-zero UHI
    park_uhi_mean = gdf.loc[park_mask, "uhi_intensity"].mean()
    overall_lst_mean = gdf["mean_lst"].mean()
    print(f"\n  Verification:")
    print(f"    Mean LST (baseline/park): {rural_ref_temp:.2f} C")
    print(f"    Mean LST (all cells):     {overall_lst_mean:.2f} C")
    print(f"    Mean UHI (park cells):    {park_uhi_mean:.2f} C  (should be ~0)")
    print(f"    UHI difference (urban - park): {overall_lst_mean - rural_ref_temp:.2f} C")

    # ---- Save updated master file -------------------------------------------
    gdf.to_file(master_path, driver="GeoJSON")
    print(f"\n[OK] Updated master file with uhi_intensity: {master_path}")

    # ---- Plot UHI map -------------------------------------------------------
    print("\n> Generating UHI map...")
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))

    # Use a diverging colormap centered at 0
    vmax = max(abs(gdf["uhi_intensity"].quantile(0.02)),
               abs(gdf["uhi_intensity"].quantile(0.98)))
    vmin = -vmax

    gdf.plot(
        column="uhi_intensity",
        cmap="RdBu_r",  # Red = hot (positive UHI), Blue = cool (negative)
        edgecolor="gray",
        linewidth=0.2,
        ax=ax,
        vmin=vmin,
        vmax=vmax,
        legend=False,
    )

    # Colorbar
    sm = plt.cm.ScalarMappable(
        cmap="RdBu_r",
        norm=mcolors.Normalize(vmin=vmin, vmax=vmax),
    )
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label("UHI Intensity (C relative to SGNP baseline)", fontsize=11)

    # Draw the baseline bounding box
    from matplotlib.patches import Rectangle
    park_rect = Rectangle(
        (park_bbox["west"], park_bbox["south"]),
        park_bbox["east"] - park_bbox["west"],
        park_bbox["north"] - park_bbox["south"],
        linewidth=2, edgecolor="green", facecolor="none",
        linestyle="--", label="SGNP baseline zone",
    )
    ax.add_patch(park_rect)

    ax.set_title(
        "Mumbai -- Urban Heat Island Intensity (Pre-Monsoon 2023)",
        fontsize=14, fontweight="bold",
    )
    ax.set_xlabel("Longitude", fontsize=11)
    ax.set_ylabel("Latitude", fontsize=11)
    ax.ticklabel_format(useOffset=False)
    ax.legend(loc="lower left", fontsize=10)

    plt.tight_layout()
    plt.savefig(output_png, dpi=150, bbox_inches="tight")
    print(f"[OK] UHI map saved to: {output_png}")
    plt.close()

    print("\n" + "=" * 60)
    print("  [OK] UHI computation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
