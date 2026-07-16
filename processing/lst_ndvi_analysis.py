"""
lst_ndvi_analysis.py
====================
Computes Pearson correlation and linear regression between LST and NDVI
across all grid cells. Produces a scatter plot with regression line to
answer: "How much does green cover cool the city?"

The slope tells you how many degrees C the temperature changes per unit
NDVI increase. For each 0.1 NDVI increase, the cooling is slope * 0.1.

Usage:
    python processing/lst_ndvi_analysis.py   (from project root)
"""

import os
import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from config_loader import load_config

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))


def main() -> None:
    """Analyze the LST/NDVI relationship and save its configured plot."""
    print("=" * 60)
    print("  City Sense -- Week 4: LST-NDVI Correlation Analysis")
    print("=" * 60)

    cfg = load_config()
    master_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["master_data"])
    output_png = os.path.join(PROJECT_ROOT, cfg["output_paths"]["lst_ndvi_scatter"])

    # ---- Load master dataset -----------------------------------------------
    gdf = gpd.read_file(master_path)
    print(f"\nLoaded {len(gdf)} cells from {master_path}")

    # ---- Drop rows with NaN in either column --------------------------------
    mask = gdf["mean_lst"].notna() & gdf["mean_ndvi"].notna()
    valid_all = gdf[mask].copy()
    print(f"Valid cells (no NaN in LST or NDVI): {len(valid_all)}/{len(gdf)}")

    # ---- Filter to LAND-ONLY cells (NDVI > 0) ------------------------------
    # Water cells (NDVI < 0) have low LST due to ocean thermal moderation,
    # which skews the regression. We want the vegetation-cooling effect on land.
    valid = valid_all[valid_all["mean_ndvi"] > 0].copy()
    water_count = len(valid_all) - len(valid)
    print(f"Land cells (NDVI > 0):               {len(valid)} ({water_count} water cells excluded)")

    ndvi = valid["mean_ndvi"].values
    lst = valid["mean_lst"].values

    # ---- Pearson correlation ------------------------------------------------
    r, p_value = stats.pearsonr(ndvi, lst)
    print(f"\n> Pearson Correlation:")
    print(f"  r       = {r:.4f}")
    print(f"  p-value = {p_value:.2e}")
    if abs(r) > 0.5:
        strength = "strong"
    elif abs(r) > 0.3:
        strength = "moderate"
    else:
        strength = "weak"
    direction = "negative" if r < 0 else "positive"
    print(f"  Interpretation: {strength} {direction} correlation")

    # ---- Linear regression --------------------------------------------------
    slope, intercept, r_value, p_val, std_err = stats.linregress(ndvi, lst)
    r_squared = r_value ** 2

    print(f"\n> Linear Regression (LST = slope * NDVI + intercept):")
    print(f"  Slope     = {slope:.2f} C per unit NDVI")
    print(f"  Intercept = {intercept:.2f} C")
    print(f"  R-squared = {r_squared:.4f}")
    print(f"  Std error = {std_err:.2f}")

    # Practical interpretation
    cooling_per_01 = slope * 0.1
    print(f"\n> Practical interpretation:")
    print(f"  For each 0.1 increase in NDVI, LST changes by {cooling_per_01:.2f} C")
    if slope < 0:
        print(f"  => Green cover COOLS the city by ~{abs(cooling_per_01):.1f} C per 0.1 NDVI unit")
    else:
        print(f"  => Unexpected positive slope -- check data quality")

    # ---- Scatter plot with regression line -----------------------------------
    print(f"\n> Generating scatter plot...")
    fig, ax = plt.subplots(1, 1, figsize=(10, 7))

    # Scatter
    scatter = ax.scatter(
        ndvi, lst,
        c=lst,
        cmap="RdYlBu_r",
        s=15,
        alpha=0.7,
        edgecolors="none",
    )

    # Regression line
    x_line = np.linspace(ndvi.min(), ndvi.max(), 100)
    y_line = slope * x_line + intercept
    ax.plot(x_line, y_line, color="black", linewidth=2, linestyle="--",
            label=f"y = {slope:.1f}x + {intercept:.1f}")

    # Annotate equation and R-squared
    eq_text = (
        f"LST = {slope:.2f} * NDVI + {intercept:.2f}\n"
        f"R$^2$ = {r_squared:.4f}\n"
        f"r = {r:.4f}, p = {p_value:.2e}\n"
        f"Cooling: ~{abs(cooling_per_01):.1f} C per 0.1 NDVI"
    )
    ax.text(
        0.95, 0.95, eq_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.9),
    )

    # Colorbar
    cbar = fig.colorbar(scatter, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label("LST (C)", fontsize=11)

    # Labels
    ax.set_xlabel("Mean NDVI", fontsize=12)
    ax.set_ylabel("Mean LST (C)", fontsize=12)
    ax.set_title(
        "Mumbai -- LST vs NDVI Correlation (Pre-Monsoon 2023)\n"
        "How much does green cover cool the city?",
        fontsize=13, fontweight="bold",
    )
    ax.legend(loc="lower left", fontsize=10)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_png, dpi=150, bbox_inches="tight")
    print(f"[OK] Scatter plot saved to: {output_png}")
    plt.close()

    print("\n" + "=" * 60)
    print("  [OK] LST-NDVI analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
