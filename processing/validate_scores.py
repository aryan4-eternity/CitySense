"""
validate_scores.py
==================
Generates visual validations (histograms, scatter plots, boxplots) of the 
final risk scores and clusters to ensure they make logical sense before 
they are loaded into the dashboard.

Outputs PNGs to the data/ directory.

Usage:
    python processing/validate_scores.py
"""

import os
import logging
import geopandas as gpd
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from config_loader import load_config

logger = logging.getLogger("CitySense.processing.validate_scores")

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))


def main() -> None:
    logger.info("=== City Sense -- Score & Cluster Validation ===")

    cfg = load_config()
    master_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["master_data"])
    
    # Check if data exists
    if not os.path.exists(master_path):
        logger.error("Master dataset not found. Run previous pipeline steps first.")
        return

    # ---- 1. Load Data ------------------------------------------------------
    gdf = gpd.read_file(master_path)
    logger.info("Loaded %d cells from %s", len(gdf), master_path)

    # Required columns
    req_cols = ["risk_score", "mean_lst", "mean_ndvi", "cluster"]
    for col in req_cols:
        if col not in gdf.columns:
            logger.warning("Required column '%s' is missing! Skipping validation.", col)
            return

    # Set seaborn theme
    sns.set_theme(style="whitegrid")

    # ---- 2. Risk Score Distribution ----------------------------------------
    logger.info("Generating Risk Score distribution plot...")
    plt.figure(figsize=(8, 5))
    sns.histplot(gdf["risk_score"], bins=30, kde=True, color="crimson")
    plt.title("Distribution of Environmental Risk Scores in Mumbai", fontsize=14, fontweight="bold")
    plt.xlabel("Risk Score (0-100)")
    plt.ylabel("Number of Grid Cells")
    
    dist_path = os.path.join(PROJECT_ROOT, "data", "val_risk_distribution.png")
    plt.savefig(dist_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("  -> Saved %s", dist_path)

    # ---- 3. Risk vs LST (Sanity Check) -------------------------------------
    # Higher LST should generally correlate with higher risk
    logger.info("Generating Risk vs LST scatter plot...")
    plt.figure(figsize=(8, 6))
    sns.scatterplot(data=gdf, x="mean_lst", y="risk_score", alpha=0.6, color="darkred")
    
    # Add trendline
    import numpy as np
    x = gdf["mean_lst"].dropna()
    y = gdf.loc[x.index, "risk_score"]
    if len(x) > 0:
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)
        plt.plot(x, p(x), "r--", alpha=0.8)
        
    plt.title("Sanity Check: Risk Score vs Land Surface Temp", fontsize=14, fontweight="bold")
    plt.xlabel("Mean LST (°C)")
    plt.ylabel("Risk Score (0-100)")
    
    lst_path = os.path.join(PROJECT_ROOT, "data", "val_risk_vs_lst.png")
    plt.savefig(lst_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("  -> Saved %s", lst_path)

    # ---- 4. Risk by Cluster Typology ---------------------------------------
    logger.info("Generating Risk by Cluster boxplot...")
    plt.figure(figsize=(10, 6))
    
    # Order clusters by their median risk score for a better looking plot
    cluster_order = gdf.groupby("cluster")["risk_score"].median().sort_values().index
    
    sns.boxplot(data=gdf, x="risk_score", y="cluster", order=cluster_order, palette="viridis")
    plt.title("Risk Score Distribution Across Urban Typologies", fontsize=14, fontweight="bold")
    plt.xlabel("Risk Score (0-100)")
    plt.ylabel("")
    
    cluster_path = os.path.join(PROJECT_ROOT, "data", "val_risk_by_cluster.png")
    plt.savefig(cluster_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("  -> Saved %s", cluster_path)
    
    # ---- 5. Indicator Profiling by Cluster ---------------------------------
    logger.info("Generating Indicator Profiles by Cluster...")
    # Normalize indicators to 0-1 just for the radar/profile chart
    features = ["mean_lst", "mean_ndvi", "mean_ndbi", "mean_dem"]
    df_profile = gdf[features + ["cluster"]].copy()
    
    for f in features:
        min_val = df_profile[f].min()
        max_val = df_profile[f].max()
        df_profile[f] = (df_profile[f] - min_val) / (max_val - min_val)
        
    # Get mean of normalized features per cluster
    cluster_means = df_profile.groupby("cluster")[features].mean()
    
    # Plot heatmap profile
    plt.figure(figsize=(10, 6))
    sns.heatmap(cluster_means, annot=True, cmap="YlGnBu", fmt=".2f", linewidths=.5)
    plt.title("Normalized Indicator Profile per Cluster (0=Low, 1=High)", fontsize=14, fontweight="bold")
    plt.ylabel("")
    
    # Clean up x-axis labels
    plt.xticks(ticks=[0.5, 1.5, 2.5, 3.5], labels=["LST (Heat)", "NDVI (Greenery)", "NDBI (Built-up)", "DEM (Elevation)"])
    
    profile_path = os.path.join(PROJECT_ROOT, "data", "val_cluster_profiles.png")
    plt.savefig(profile_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("  -> Saved %s", profile_path)

    logger.info("=== Validation plots complete! ===")


if __name__ == "__main__":
    main()
