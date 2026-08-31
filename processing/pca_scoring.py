"""
pca_scoring.py
==============
Applies Principal Component Analysis (PCA) to the 4 core indicators 
(LST, NDVI, NDBI, DEM) to derive a single, unified "Environmental Risk Score".

It also creates a "Sustainability Score" (which is simply 100 - Risk).

Steps:
1. Impute missing values (median).
2. Normalize features using MinMaxScaler to [0,1].
3. Align directions:
   - High LST, high NDBI = higher risk
   - High NDVI, high DEM = lower risk (so these are inverted before PCA)
4. Fit PCA (n_components=1) and extract the first principal component (PC1).
5. Scale PC1 to 0-100 to create the final Risk Score.
6. Save scaler, PCA model, and update master dataset.

Usage:
    python processing/pca_scoring.py
"""

import os
import logging
import geopandas as gpd
import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import MinMaxScaler
from sklearn.decomposition import PCA
from config_loader import load_config

logger = logging.getLogger("CitySense.processing.pca_scoring")

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))


def main() -> None:
    logger.info("=== City Sense -- Week 6: PCA Scoring ===")

    cfg = load_config()
    master_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["master_data"])
    
    models_dir = os.path.join(PROJECT_ROOT, "models")
    os.makedirs(models_dir, exist_ok=True)
    scaler_path = os.path.join(models_dir, "scaler.pkl")
    pca_path = os.path.join(models_dir, "pca_model.pkl")

    # ---- 1. Load Data ------------------------------------------------------
    gdf = gpd.read_file(master_path)
    logger.info("Loaded %d cells from %s", len(gdf), master_path)

    features = ["mean_lst", "mean_ndvi", "mean_ndbi", "mean_dem"]
    df = gdf[features].copy()

    # Impute missing values with median
    df = df.fillna(df.median())

    # ---- 2. Normalisation --------------------------------------------------
    logger.info("Normalising features to [0, 1] range...")
    scaler = MinMaxScaler()
    df_scaled_array = scaler.fit_transform(df)
    
    # Save the scaler for inference/dashboard later
    joblib.dump(scaler, scaler_path)
    logger.info("Saved MinMaxScaler to %s", scaler_path)

    df_scaled = pd.DataFrame(df_scaled_array, columns=features)
    
    logger.info("Scaled data ranges:")
    for col in features:
        logger.info("  %s: min=%.2f, max=%.2f", col, df_scaled[col].min(), df_scaled[col].max())

    # ---- 3. Align Directionality -------------------------------------------
    # We want PC1 to represent RISK.
    # Therefore, all features fed into PCA should theoretically positively correlate with risk.
    # LST (heat) and NDBI (built-up) already positively correlate with environmental risk.
    # NDVI (greenery) and DEM (elevation/flood protection) negatively correlate with risk.
    # So we invert NDVI and DEM:  val_inv = 1.0 - val
    
    logger.info("Aligning feature directions towards RISK...")
    logger.info("  - Inverting mean_ndvi (less greenery = higher risk)")
    logger.info("  - Inverting mean_dem (lower elevation = higher flood risk)")
    
    df_aligned = df_scaled.copy()
    df_aligned["mean_ndvi"] = 1.0 - df_aligned["mean_ndvi"]
    df_aligned["mean_dem"] = 1.0 - df_aligned["mean_dem"]

    # ---- 4. Fit PCA --------------------------------------------------------
    logger.info("Fitting PCA (n_components=1)...")
    pca = PCA(n_components=1)
    
    # Transform returns a 2D array, we just want the 1D column
    pc1 = pca.fit_transform(df_aligned)[:, 0]
    
    logger.info("PCA Explained Variance Ratio: %.4f (%.1f%%)", 
          pca.explained_variance_ratio_[0], pca.explained_variance_ratio_[0]*100)

    # Note: PCA signs are arbitrary. We check the loadings to ensure PC1 
    # actually represents increased risk.
    loadings = pca.components_[0]
    logger.info("Feature Loadings for PC1:")
    for i, col in enumerate(features):
        logger.info("  %s: %.4f", col, loadings[i])

    # If the sum of loadings is negative, it means PCA arbitrarily flipped the axis.
    # We flip it back so higher PC1 = higher risk.
    if np.sum(loadings) < 0:
        logger.info("  (Flipping PC1 sign so positive = higher risk)")
        pc1 = -pc1
        pca.components_[0] = -pca.components_[0]

    # ---- 5. Scale PC1 to Risk Score (0 - 100) ------------------------------
    # Min-max scale the PC1 array
    pc1_min, pc1_max = pc1.min(), pc1.max()
    risk_score = (pc1 - pc1_min) / (pc1_max - pc1_min) * 100.0

    gdf["risk_score"] = risk_score
    gdf["sustainability_score"] = 100.0 - risk_score

    logger.info("--- Risk Score Stats ---")
    logger.info("  Min: %.2f", gdf["risk_score"].min())
    logger.info("  Max: %.2f", gdf["risk_score"].max())
    logger.info("  Mean: %.2f", gdf["risk_score"].mean())
    logger.info("  Median: %.2f", gdf["risk_score"].median())
    
    logger.info("--- Sustainability Score Stats ---")
    logger.info("  Min: %.2f", gdf["sustainability_score"].min())
    logger.info("  Max: %.2f", gdf["sustainability_score"].max())
    logger.info("  Mean: %.2f", gdf["sustainability_score"].mean())
    logger.info("  Median: %.2f", gdf["sustainability_score"].median())

    # ---- 6. Save outputs ---------------------------------------------------
    gdf.to_file(master_path, driver="GeoJSON")
    logger.info("Updated master dataset with 'risk_score' and 'sustainability_score'.")

    # Save PCA model
    joblib.dump(pca, pca_path)
    logger.info("Saved PCA model to %s", pca_path)

    logger.info("=== PCA Scoring complete! ===")


if __name__ == "__main__":
    main()
