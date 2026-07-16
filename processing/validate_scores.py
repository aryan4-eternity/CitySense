"""
validate_scores.py
==================
Validates the scoring and clustering results from Week 5:
  - Score distribution histograms
  - Risk vs Sustainability scatter plot
  - Risk Score choropleth map
  - Sustainability Score choropleth map
  - Cluster map
  - Geographic coherence check

Usage:
    python processing/validate_scores.py     (from project root)
"""

import os
import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from config_loader import load_config

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))


def main() -> None:
    """Create validation diagnostics for the scored and clustered dataset."""
    print("=" * 60)
    print("  City Sense -- Week 5: Validation & Visualization")
    print("=" * 60)

    cfg = load_config()
    master_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["master_data"])

    # ---- Load master dataset -----------------------------------------------
    gdf = gpd.read_file(master_path)
    print(f"\nLoaded {len(gdf)} cells")
    print(f"Columns: {list(gdf.columns)}")

    # ---- Descriptive statistics --------------------------------------------
    print("\n> Score Statistics:")
    for col in ["risk_score", "sustainability_score"]:
        print(f"\n  {col}:")
        print(f"    Min   : {gdf[col].min():.2f}")
        print(f"    Max   : {gdf[col].max():.2f}")
        print(f"    Mean  : {gdf[col].mean():.2f}")
        print(f"    Median: {gdf[col].median():.2f}")
        print(f"    Std   : {gdf[col].std():.2f}")

    # =====================================================================
    # Plot 1: Score Distributions (side by side histograms)
    # =====================================================================
    print("\n> Generating score distribution histograms...")
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].hist(gdf["risk_score"], bins=30, color="indianred", edgecolor="black",
                 alpha=0.8)
    axes[0].set_title("Risk Score Distribution", fontsize=13, fontweight="bold")
    axes[0].set_xlabel("Risk Score (0-100)", fontsize=11)
    axes[0].set_ylabel("Number of Cells", fontsize=11)
    axes[0].axvline(gdf["risk_score"].mean(), color="black", linestyle="--",
                    label=f"Mean: {gdf['risk_score'].mean():.1f}")
    axes[0].legend()

    axes[1].hist(gdf["sustainability_score"], bins=30, color="seagreen",
                 edgecolor="black", alpha=0.8)
    axes[1].set_title("Sustainability Score Distribution", fontsize=13,
                      fontweight="bold")
    axes[1].set_xlabel("Sustainability Score (0-100)", fontsize=11)
    axes[1].set_ylabel("Number of Cells", fontsize=11)
    axes[1].axvline(gdf["sustainability_score"].mean(), color="black",
                    linestyle="--",
                    label=f"Mean: {gdf['sustainability_score'].mean():.1f}")
    axes[1].legend()

    plt.tight_layout()
    path_dist = os.path.join(PROJECT_ROOT, cfg["output_paths"]["score_distributions"])
    plt.savefig(path_dist, dpi=150)
    print(f"  [OK] Saved: {path_dist}")
    plt.close()

    # =====================================================================
    # Plot 2: Risk vs Sustainability Scatter
    # =====================================================================
    print("> Generating risk vs sustainability scatter...")
    fig, ax = plt.subplots(1, 1, figsize=(8, 7))

    scatter = ax.scatter(
        gdf["risk_score"], gdf["sustainability_score"],
        c=gdf["risk_score"], cmap="RdYlGn_r", s=12, alpha=0.7, edgecolors="none",
    )
    # Perfect inverse line
    ax.plot([0, 100], [100, 0], "k--", linewidth=1.5, alpha=0.5,
            label="Perfect inverse (y = 100 - x)")
    ax.set_xlabel("Risk Score", fontsize=12)
    ax.set_ylabel("Sustainability Score", fontsize=12)
    ax.set_title("Risk vs Sustainability Score", fontsize=14, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    cbar = fig.colorbar(scatter, ax=ax, shrink=0.7)
    cbar.set_label("Risk Score", fontsize=10)

    plt.tight_layout()
    path_scatter = os.path.join(PROJECT_ROOT, cfg["output_paths"]["score_scatter"])
    plt.savefig(path_scatter, dpi=150)
    print(f"  [OK] Saved: {path_scatter}")
    plt.close()

    # =====================================================================
    # Plot 3: Risk Score Map
    # =====================================================================
    print("> Generating risk score map...")
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    gdf.plot(column="risk_score", cmap="YlOrRd", edgecolor="gray",
             linewidth=0.2, ax=ax, vmin=0, vmax=100, legend=False)
    sm = plt.cm.ScalarMappable(cmap="YlOrRd",
                               norm=mcolors.Normalize(vmin=0, vmax=100))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label("Risk Score (0-100)", fontsize=11)
    ax.set_title("Mumbai -- Risk Score Map", fontsize=14, fontweight="bold")
    ax.set_xlabel("Longitude", fontsize=11)
    ax.set_ylabel("Latitude", fontsize=11)
    ax.ticklabel_format(useOffset=False)
    plt.tight_layout()
    path_risk = os.path.join(PROJECT_ROOT, cfg["output_paths"]["risk_map"])
    plt.savefig(path_risk, dpi=150, bbox_inches="tight")
    print(f"  [OK] Saved: {path_risk}")
    plt.close()

    # =====================================================================
    # Plot 4: Sustainability Score Map
    # =====================================================================
    print("> Generating sustainability score map...")
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    gdf.plot(column="sustainability_score", cmap="YlGn", edgecolor="gray",
             linewidth=0.2, ax=ax, vmin=0, vmax=100, legend=False)
    sm = plt.cm.ScalarMappable(cmap="YlGn",
                               norm=mcolors.Normalize(vmin=0, vmax=100))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label("Sustainability Score (0-100)", fontsize=11)
    ax.set_title("Mumbai -- Sustainability Score Map", fontsize=14,
                 fontweight="bold")
    ax.set_xlabel("Longitude", fontsize=11)
    ax.set_ylabel("Latitude", fontsize=11)
    ax.ticklabel_format(useOffset=False)
    plt.tight_layout()
    path_sust = os.path.join(PROJECT_ROOT, cfg["output_paths"]["sustainability_map"])
    plt.savefig(path_sust, dpi=150, bbox_inches="tight")
    print(f"  [OK] Saved: {path_sust}")
    plt.close()

    # =====================================================================
    # Plot 5: Cluster Map
    # =====================================================================
    print("> Generating cluster map...")
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))

    # Use a categorical colormap
    n_clusters = gdf["cluster"].nunique()
    colors = plt.cm.Set2(np.linspace(0, 1, n_clusters))

    for i, (cluster_id, group) in enumerate(gdf.groupby("cluster")):
        label = group["cluster_label"].iloc[0]
        group.plot(ax=ax, color=colors[i], edgecolor="gray", linewidth=0.2,
                   label=f"C{cluster_id}: {label}")

    ax.set_title("Mumbai -- K-Means Cluster Map", fontsize=14, fontweight="bold")
    ax.set_xlabel("Longitude", fontsize=11)
    ax.set_ylabel("Latitude", fontsize=11)
    ax.ticklabel_format(useOffset=False)
    ax.legend(loc="lower left", fontsize=8, framealpha=0.9)
    plt.tight_layout()
    path_cluster = os.path.join(PROJECT_ROOT, cfg["output_paths"]["cluster_map"])
    plt.savefig(path_cluster, dpi=150, bbox_inches="tight")
    print(f"  [OK] Saved: {path_cluster}")
    plt.close()

    # =====================================================================
    # Geographic coherence check
    # =====================================================================
    print("\n> Geographic coherence check:")
    print("  Checking cluster spatial distribution...")
    for c in sorted(gdf["cluster"].unique()):
        subset = gdf[gdf["cluster"] == c]
        centroids = subset.geometry.centroid
        lat_range = centroids.y.max() - centroids.y.min()
        lon_range = centroids.x.max() - centroids.x.min()
        label = subset["cluster_label"].iloc[0]
        print(f"  Cluster {c} ({label}):")
        print(f"    Cells: {len(subset)}, "
              f"Lat spread: {lat_range:.3f} deg, "
              f"Lon spread: {lon_range:.3f} deg")

    # Final column check
    expected = ["cell_id", "mean_ndvi", "mean_lst", "mean_ndbi", "mean_dem",
                "uhi_intensity", "risk_score", "sustainability_score",
                "cluster", "cluster_label", "geometry"]
    actual = list(gdf.columns)
    missing = [c for c in expected if c not in actual]
    if missing:
        print(f"\n  [WARNING] Missing expected columns: {missing}")
    else:
        print(f"\n  [OK] All expected columns present in master dataset.")

    print("\n" + "=" * 60)
    print("  [OK] All validation plots generated!")
    print("=" * 60)


if __name__ == "__main__":
    main()
