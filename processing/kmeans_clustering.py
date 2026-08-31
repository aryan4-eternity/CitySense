"""
kmeans_clustering.py
====================
Applies K-Means clustering to the 4 core indicators (LST, NDVI, NDBI, DEM)
to segment the city into distinct urban typologies (e.g., "Dense Hot Built-up", 
"Cool Green Park", "Coastal Residential").

Steps:
1. Impute missing values (median).
2. Normalize features using MinMaxScaler to [0,1].
3. Determine optimal k (optional/exploratory, here we use silhouette score 
   but hardcode k=4 for interpretability).
4. Fit K-Means with k=4.
5. Assign descriptive labels to the clusters based on their centroids.
6. Save cluster assignments back to data/cells_master.geojson.

Usage:
    python processing/kmeans_clustering.py
"""

import os
import logging
import geopandas as gpd
import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import MinMaxScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from config_loader import load_config

logger = logging.getLogger("CitySense.processing.kmeans_clustering")

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))


def assign_cluster_labels(centroids: pd.DataFrame) -> dict:
    """
    Given the centroids of the clusters (in scaled 0-1 space),
    heuristically assign a human-readable name to each cluster.
    """
    # This is a heuristic based on Mumbai's typical feature space.
    # High LST + High NDBI + Low NDVI = Dense Urban Heat
    # High NDVI + Low LST = Green/Forested
    # Low DEM (coast) + Moderate/High NDBI = Coastal/Lowland Urban
    
    labels = {}
    for i, row in centroids.iterrows():
        name_parts = []
        
        if row["mean_ndvi"] > 0.6:
            name_parts.append("Green/Forested")
        elif row["mean_ndbi"] > 0.6 and row["mean_lst"] > 0.6:
            name_parts.append("Dense Urban Heat")
        elif row["mean_dem"] < 0.2:
            name_parts.append("Coastal/Lowland Urban")
        else:
            name_parts.append("Mixed/Transitional")
            
        labels[i] = f"Cluster {i}: {' - '.join(name_parts)}"
        
    return labels


def main() -> None:
    logger.info("=== City Sense -- Week 6: K-Means Clustering ===")

    cfg = load_config()
    master_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["master_data"])
    models_dir = os.path.join(PROJECT_ROOT, "models")
    os.makedirs(models_dir, exist_ok=True)
    kmeans_path = os.path.join(models_dir, "kmeans_model.pkl")
    plot_path = os.path.join(PROJECT_ROOT, "data", "kmeans_silhouette.png")

    # ---- 1. Load Data ------------------------------------------------------
    gdf = gpd.read_file(master_path)
    logger.info("Loaded %d cells from %s", len(gdf), master_path)

    features = ["mean_lst", "mean_ndvi", "mean_ndbi", "mean_dem"]
    df = gdf[features].copy()
    df = df.fillna(df.median())

    # ---- 2. Normalisation --------------------------------------------------
    logger.info("Normalising features for clustering...")
    scaler = MinMaxScaler()
    df_scaled = scaler.fit_transform(df)

    # ---- 3. Silhouette Analysis (Exploratory) ------------------------------
    logger.info("Running silhouette analysis to evaluate k (2 to 6)...")
    k_values = range(2, 7)
    silhouette_scores = []
    
    # Optional: Set a fixed random state for reproducibility
    seed = 42

    for k in k_values:
        kmeans = KMeans(n_clusters=k, random_state=seed, n_init="auto")
        labels = kmeans.fit_predict(df_scaled)
        score = silhouette_score(df_scaled, labels)
        silhouette_scores.append(score)
        logger.info("  k=%d | Silhouette Score = %.4f", k, score)

    # Find the best k based strictly on silhouette score (though we might override)
    best_k = k_values[np.argmax(silhouette_scores)]
    logger.info("Best k by silhouette score: %d", best_k)
    
    # We will enforce k=4 for this project as it usually gives the most interpretable 
    # urban typologies (Green, High Density, Lowland, Transitional)
    chosen_k = 4
    
    # Plot silhouette scores
    plt.figure(figsize=(8, 5))
    plt.plot(k_values, silhouette_scores, marker='o', linestyle='-', color='b')
    plt.axvline(x=chosen_k, color='r', linestyle='--', label=f'Chosen k={chosen_k}')
    plt.title('Silhouette Score vs. Number of Clusters (k)')
    plt.xlabel('Number of clusters (k)')
    plt.ylabel('Silhouette Score')
    plt.legend()
    plt.grid(True)
    plt.savefig(plot_path)
    logger.info("Saved silhouette plot to %s", plot_path)
    plt.close()

    # ---- 4. Fit Final K-Means ----------------------------------------------
    logger.info("Fitting final K-Means model with k=%d...", chosen_k)
    kmeans = KMeans(n_clusters=chosen_k, random_state=seed, n_init="auto")
    cluster_labels = kmeans.fit_predict(df_scaled)
    
    # Extract centroids (in scaled space)
    centroids = pd.DataFrame(kmeans.cluster_centers_, columns=features)
    
    logger.info("Cluster Centroids (Scaled 0-1):")
    # Log the centroids line by line for better readability
    for row in str(centroids).split('\n'):
        logger.info(row)

    # ---- 5. Assign Descriptive Labels --------------------------------------
    label_mapping = assign_cluster_labels(centroids)
    logger.info("Assigned typologies:")
    for k, v in label_mapping.items():
        logger.info("  %s", v)
        
    # Map the numeric labels to string descriptions
    gdf["cluster_id"] = cluster_labels
    gdf["cluster"] = gdf["cluster_id"].map(label_mapping)

    # ---- 6. Save outputs ---------------------------------------------------
    gdf.to_file(master_path, driver="GeoJSON")
    logger.info("Updated master dataset with 'cluster' assignments.")

    joblib.dump(kmeans, kmeans_path)
    
    logger.info("Cluster distribution:")
    dist = gdf["cluster"].value_counts()
    for name, count in dist.items():
        logger.info("  %s: %d cells", name, count)

    logger.info("=== K-Means Clustering complete! ===")


if __name__ == "__main__":
    main()
