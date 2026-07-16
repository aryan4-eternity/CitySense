"""
kmeans_clustering.py
====================
Runs K-Means clustering on the normalized indicators to discover natural
zone types across Mumbai. Uses silhouette score to pick the optimal k,
names each cluster based on its centroid characteristics, and saves
cluster assignments to the master dataset.

Usage:
    python processing/kmeans_clustering.py   (from project root)
"""

import os
import numpy as np
import geopandas as gpd
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from config_loader import load_config

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))

INDICATOR_COLS = ["mean_ndvi", "mean_lst", "mean_ndbi", "mean_dem"]
K_RANGE = range(2, 9)  # retained as a module-level compatibility constant


def name_cluster(centroid: dict) -> str:
    """
    Assign a descriptive label to a cluster based on its centroid values
    (in original / physical units).

    Heuristics:
        - High LST (>40) + low NDVI (<0.1) + high NDBI (>-0.02) => Heat-Stressed Urban
        - High NDVI (>0.25) + low LST (<38) + high DEM (>50) => Green Highland
        - Moderate everything => Mixed Transitional
        - Low LST (<33) + low NDVI (<0) => Coastal / Water-Adjacent
        - High NDVI (>0.15) + moderate LST => Green Residential
    """
    ndvi = centroid["mean_ndvi"]
    lst  = centroid["mean_lst"]
    ndbi = centroid["mean_ndbi"]
    dem  = centroid["mean_dem"]

    # Water-adjacent / coastal cells
    if ndvi < 0 and lst < 33:
        return "Coastal / Water-Adjacent"

    # Dense heat-stressed urban
    if lst > 40 and ndvi < 0.15 and ndbi > -0.03:
        return "Dense Heat-Stressed Urban"

    # Green highland (SGNP-type)
    if ndvi > 0.25 and dem > 40:
        return "Green Highland / Forest"

    # Green low-risk residential
    if ndvi > 0.15 and lst < 40:
        return "Green Low-Risk Residential"

    # Moderate / transitional
    if lst > 38 and ndvi < 0.15:
        return "Semi-Urban Moderate Risk"

    # Default
    return "Mixed Transitional"


def main() -> None:
    """Select and apply the configured K-Means clustering model."""
    print("=" * 60)
    print("  City Sense -- Week 5: K-Means Clustering")
    print("=" * 60)

    cfg = load_config()
    model_config = cfg["model"]["kmeans"]
    k_values = model_config["candidate_clusters"]
    master_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["master_data"])
    silhouette_png = os.path.join(PROJECT_ROOT, cfg["output_paths"]["silhouette_scores"])

    # ---- Load master dataset -----------------------------------------------
    gdf = gpd.read_file(master_path)
    print(f"\nLoaded {len(gdf)} cells from {master_path}")

    # ---- Normalize indicators (same scaling, original direction) -----------
    print("\n> Normalizing indicators for clustering...")
    X_raw = gdf[INDICATOR_COLS].values.copy()
    scaler = MinMaxScaler()
    X_norm = scaler.fit_transform(X_raw)
    print(f"  Features: {INDICATOR_COLS}")
    print(f"  Shape: {X_norm.shape}")

    # ---- Silhouette analysis for k = 2..8 ----------------------------------
    print(f"\n> Running silhouette analysis for k = {min(k_values)} to {max(k_values)}...")
    silhouette_scores = {}

    for k in k_values:
        km = KMeans(
            n_clusters=k,
            random_state=cfg["project"]["random_seed"],
            n_init=model_config["n_init"],
            max_iter=model_config["max_iter"],
        )
        labels = km.fit_predict(X_norm)
        sil = silhouette_score(X_norm, labels)
        silhouette_scores[k] = sil
        print(f"  k={k}: silhouette = {sil:.4f}")

    # Find optimal k (highest silhouette; smallest k on tie)
    best_k = max(silhouette_scores, key=silhouette_scores.get)
    best_sil = silhouette_scores[best_k]
    print(f"\n  >> Optimal k = {best_k} (silhouette = {best_sil:.4f})")

    # ---- Plot silhouette scores --------------------------------------------
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    ks = list(silhouette_scores.keys())
    sils = list(silhouette_scores.values())

    ax.plot(ks, sils, "o-", linewidth=2, markersize=8, color="steelblue")
    ax.axvline(x=best_k, color="red", linestyle="--", alpha=0.7,
               label=f"Best k = {best_k}")
    ax.set_xlabel("Number of Clusters (k)", fontsize=12)
    ax.set_ylabel("Silhouette Score", fontsize=12)
    ax.set_title("K-Means Silhouette Analysis", fontsize=14, fontweight="bold")
    ax.set_xticks(ks)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(silhouette_png, dpi=150)
    print(f"\n[OK] Silhouette plot saved to: {silhouette_png}")
    plt.close()

    # ---- Fit final K-Means with optimal k ----------------------------------
    print(f"\n> Fitting K-Means with k = {best_k}...")
    km_final = KMeans(
        n_clusters=best_k,
        random_state=cfg["project"]["random_seed"],
        n_init=model_config["n_init"],
        max_iter=model_config["max_iter"],
    )
    gdf["cluster"] = km_final.fit_predict(X_norm)

    # ---- Characterize clusters by raw indicator centroids -------------------
    print(f"\n> Cluster Centroids (original units):")
    print("-" * 75)
    header = f"{'Cluster':>8s} | {'Count':>5s} | {'NDVI':>8s} | {'LST(C)':>8s} | {'NDBI':>8s} | {'DEM(m)':>8s}"
    print(header)
    print("-" * 75)

    cluster_stats = {}
    for c in sorted(gdf["cluster"].unique()):
        subset = gdf[gdf["cluster"] == c]
        centroid = {
            "mean_ndvi": subset["mean_ndvi"].mean(),
            "mean_lst":  subset["mean_lst"].mean(),
            "mean_ndbi": subset["mean_ndbi"].mean(),
            "mean_dem":  subset["mean_dem"].mean(),
        }
        cluster_stats[c] = centroid
        print(f"  {c:>6d} | {len(subset):>5d} | "
              f"{centroid['mean_ndvi']:>8.4f} | "
              f"{centroid['mean_lst']:>8.2f} | "
              f"{centroid['mean_ndbi']:>8.4f} | "
              f"{centroid['mean_dem']:>8.1f}")
    print("-" * 75)

    # ---- Name clusters based on centroids -----------------------------------
    print(f"\n> Assigning descriptive cluster labels...")
    cluster_names = {}
    for c, centroid in cluster_stats.items():
        name = name_cluster(centroid)
        cluster_names[c] = name
        print(f"  Cluster {c}: {name}")

    gdf["cluster_label"] = gdf["cluster"].map(cluster_names)

    # ---- Save enriched dataset ---------------------------------------------
    gdf.to_file(master_path, driver="GeoJSON")
    print(f"\n[OK] Updated master file with cluster and cluster_label")
    print(f"     Saved to: {master_path}")

    # ---- Print final summary -----------------------------------------------
    print(f"\n> Final column list: {list(gdf.columns)}")
    print(f"\n> Cluster distribution:")
    for c in sorted(gdf["cluster"].unique()):
        count = (gdf["cluster"] == c).sum()
        label = cluster_names[c]
        pct = count / len(gdf) * 100
        print(f"  Cluster {c} ({label}): {count} cells ({pct:.1f}%)")

    print("\n" + "=" * 60)
    print("  [OK] K-Means Clustering complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
