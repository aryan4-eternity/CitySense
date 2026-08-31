"""
lst_ndvi_analysis.py
====================
Performs a statistical correlation analysis between LST (temperature) 
and NDVI (vegetation) across the Mumbai grid.

Outputs a scatter plot with a linear regression line to data/lst_ndvi_scatter.png
and prints statistical metrics (Pearson r, slope, R^2) to console.

Usage:
    python processing/lst_ndvi_analysis.py
"""

import os
import logging
import geopandas as gpd
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from config_loader import load_config

logger = logging.getLogger("CitySense.processing.lst_ndvi_analysis")

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))


def main() -> None:
    """Analyze the statistical relationship between LST and NDVI."""
    logger.info("=== City Sense -- Week 5: LST-NDVI Correlation Analysis ===")

    cfg = load_config()
    master_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["master_data"])
    output_png = os.path.join(PROJECT_ROOT, "data", "lst_ndvi_scatter.png")

    # ---- 1. Load and clean data --------------------------------------------
    gdf = gpd.read_file(master_path)
    logger.info("Loaded %d cells from %s", len(gdf), master_path)

    # We need both NDVI and LST for this analysis
    df = gdf[["mean_ndvi", "mean_lst"]].dropna()
    logger.info("Cells with both valid NDVI and LST: %d", len(df))

    if len(df) < 10:
        logger.error("Not enough valid data points for analysis.")
        return

    x = df["mean_ndvi"].values
    y = df["mean_lst"].values

    # ---- 2. Statistical Correlation (Pearson) ------------------------------
    r, p_value = stats.pearsonr(x, y)
    logger.info("--- Pearson Correlation ---")
    logger.info("r       = %.4f", r)
    logger.info("p-value = %.2e", p_value)

    if p_value < 0.05:
        logger.info("Result: Statistically significant correlation.")
    else:
        logger.info("Result: Correlation is NOT statistically significant.")

    # ---- 3. Linear Regression ----------------------------------------------
    slope, intercept, r_value, p_value_lr, std_err = stats.linregress(x, y)
    r_squared = r_value ** 2

    logger.info("--- Linear Regression (LST ~ NDVI) ---")
    logger.info("Equation: LST = %.2f * NDVI + %.2f", slope, intercept)
    logger.info("R-squared: %.4f", r_squared)
    
    # Practical interpretation
    logger.info("--- Interpretation ---")
    if slope < 0:
        cooling = abs(slope) * 0.1  # Cooling per 0.1 increase in NDVI
        logger.info("A 0.1 increase in NDVI is associated with a %.2f C decrease in LST.", cooling)
    else:
        logger.warning("Unexpected positive slope. Vegetation does not appear to have a cooling effect here.")

    # ---- 4. Visualisation --------------------------------------------------
    logger.info("Generating scatter plot...")
    
    # Use seaborn for a nice scatter plot with a regression line
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(9, 7))

    # Density scatter plot (color by density)
    # This helps when there are many overlapping points
    from scipy.stats import gaussian_kde
    xy = np.vstack([x, y])
    z = gaussian_kde(xy)(xy)
    
    # Sort points by density so densest are plotted last
    idx = z.argsort()
    x_plt, y_plt, z_plt = x[idx], y[idx], z[idx]

    sc = ax.scatter(x_plt, y_plt, c=z_plt, s=20, cmap="viridis", alpha=0.8, edgecolor="none")
    
    # Add regression line
    x_line = np.linspace(x.min(), x.max(), 100)
    y_line = slope * x_line + intercept
    ax.plot(x_line, y_line, color='red', linewidth=2, 
            label=f"Fit: LST = {slope:.1f}*NDVI + {intercept:.1f}\n$R^2$ = {r_squared:.2f}")

    # Add colorbar for point density
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("Point Density", rotation=270, labelpad=15)

    # Annotations and labels
    ax.set_xlabel("Mean NDVI (Vegetation Index)", fontsize=12)
    ax.set_ylabel("Mean LST (°C) (Temperature)", fontsize=12)
    ax.set_title("LST vs. NDVI in Mumbai (Pre-Monsoon 2023)", fontsize=14, fontweight="bold")
    ax.legend(loc="upper right", fontsize=11, frameon=True, facecolor="white")

    # Add a text box with the correlation coefficient
    textstr = f"Pearson r: {r:.2f}\n(p < 0.001)" if p_value < 0.001 else f"Pearson r: {r:.2f}\n(p = {p_value:.3f})"
    props = dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='gray')
    ax.text(0.05, 0.05, textstr, transform=ax.transAxes, fontsize=11,
            verticalalignment='bottom', bbox=props)

    plt.tight_layout()
    plt.savefig(output_png, dpi=150)
    logger.info("Saved scatter plot to: %s", output_png)
    plt.close()

    logger.info("=== LST-NDVI analysis complete! ===")


if __name__ == "__main__":
    main()
