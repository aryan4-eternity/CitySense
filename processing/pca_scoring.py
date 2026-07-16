"""
pca_scoring.py
==============
Computes Risk Score and Sustainability Score for each grid cell using
PCA-derived weights from the four indicators (NDVI, LST, NDBI, DEM).

Method:
    1. Normalize all indicators to [0, 1] with MinMaxScaler.
    2. Align directions for risk (high LST/NDBI = risky, low NDVI/DEM = risky):
       invert NDVI and DEM so all variables increase with risk.
    3. Run PCA on the 4 risk-aligned variables.
    4. Use absolute PC1 loadings as weights for a weighted linear combination.
    5. Risk Score = weighted sum, rescaled to 0-100.
    6. Sustainability Score = 100 - Risk Score (perfectly inverse by design).

Why PCA weights?
    PCA identifies the direction of maximum variance in the data. The PC1
    loadings tell us which indicators contribute most to differentiating
    cells. Using these as weights is data-driven rather than arbitrary.

Usage:
    python processing/pca_scoring.py         (from project root)
"""

import os
import pickle
import numpy as np
import geopandas as gpd
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.decomposition import PCA
from config_loader import load_config

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))

INDICATOR_COLS = ["mean_ndvi", "mean_lst", "mean_ndbi", "mean_dem"]


def main() -> None:
    """Calculate PCA-derived risk and sustainability scores."""
    print("=" * 60)
    print("  City Sense -- Week 5: PCA Scoring")
    print("=" * 60)

    cfg = load_config()
    master_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["master_data"])
    scaler_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["pca_scaler"])

    # ---- Load master dataset -----------------------------------------------
    gdf = gpd.read_file(master_path)
    print(f"\nLoaded {len(gdf)} cells from {master_path}")
    print(f"Columns: {list(gdf.columns)}")

    # ---- Extract and normalize indicators ----------------------------------
    print("\n> Step 1: Normalizing indicators to [0, 1]...")
    X_raw = gdf[INDICATOR_COLS].values.copy()

    scaler = MinMaxScaler()
    X_norm = scaler.fit_transform(X_raw)

    # Save scaler for future use
    os.makedirs(os.path.dirname(scaler_path), exist_ok=True)
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    print(f"  [OK] Scaler saved to: {scaler_path}")

    # Create a DataFrame for clarity
    norm_df = pd.DataFrame(X_norm, columns=[
        "ndvi_norm", "lst_norm", "ndbi_norm", "dem_norm"
    ])

    print("\n  Normalized ranges (should all be 0-1):")
    for col in norm_df.columns:
        print(f"    {col}: {norm_df[col].min():.3f} - {norm_df[col].max():.3f}")

    # ---- Align directions for Risk Score -----------------------------------
    # Risk increases with: high LST (+), high NDBI (+), low NDVI (-), low DEM (-)
    # Invert NDVI and DEM so all four increase with risk
    print("\n> Step 2: Aligning variable directions for risk...")
    risk_aligned = norm_df.copy()
    risk_aligned["ndvi_norm"] = 1 - norm_df["ndvi_norm"]  # invert: low NDVI = high risk
    risk_aligned["dem_norm"]  = 1 - norm_df["dem_norm"]    # invert: low DEM = high risk
    # LST and NDBI already aligned (high = risky)

    print("  Direction alignment:")
    print("    ndvi_norm -> INVERTED (low vegetation = high risk)")
    print("    lst_norm  -> kept (high temperature = high risk)")
    print("    ndbi_norm -> kept (high built-up = high risk)")
    print("    dem_norm  -> INVERTED (low elevation = high risk)")

    # ---- PCA on risk-aligned variables -------------------------------------
    print("\n> Step 3: Running PCA on risk-aligned variables...")
    X_risk = risk_aligned.values

    pca = PCA(n_components=cfg["model"]["pca_components"])
    pca.fit(X_risk)

    print(f"\n  Explained variance ratios:")
    for i, var in enumerate(pca.explained_variance_ratio_):
        bar = "#" * int(var * 50)
        print(f"    PC{i+1}: {var:.4f} ({var*100:.1f}%)  {bar}")
    print(f"    Total (PC1+PC2): {sum(pca.explained_variance_ratio_[:2]):.4f}")

    # PC1 loadings
    loadings = pca.components_[0]
    feature_names = ["ndvi(inv)", "lst", "ndbi", "dem(inv)"]
    print(f"\n  PC1 Loadings:")
    for name, loading in zip(feature_names, loadings):
        print(f"    {name:12s}: {loading:+.4f}")

    # ---- Compute weights from absolute PC1 loadings ------------------------
    print("\n> Step 4: Computing PCA-derived weights...")
    abs_loadings = np.abs(loadings)
    weights = abs_loadings / abs_loadings.sum()  # normalize to sum to 1

    print(f"  Weights (from |PC1 loadings|, normalized to sum=1):")
    for name, w in zip(feature_names, weights):
        print(f"    {name:12s}: {w:.4f} ({w*100:.1f}%)")

    # ---- Calculate Risk Score (0-100) --------------------------------------
    print("\n> Step 5: Computing Risk Score...")
    risk_raw = X_risk @ weights  # weighted sum
    # Rescale to 0-100
    risk_min, risk_max = risk_raw.min(), risk_raw.max()
    risk_score = (risk_raw - risk_min) / (risk_max - risk_min) * 100

    gdf["risk_score"] = risk_score

    print(f"  Risk Score statistics:")
    print(f"    Min   : {risk_score.min():.2f}")
    print(f"    Max   : {risk_score.max():.2f}")
    print(f"    Mean  : {risk_score.mean():.2f}")
    print(f"    Median: {np.median(risk_score):.2f}")
    print(f"    Std   : {risk_score.std():.2f}")

    # ---- Calculate Sustainability Score ------------------------------------
    # Sustainability = 100 - Risk (perfectly inverse by design)
    # This is equivalent to using the same weights on sustainability-aligned
    # variables (inverted LST and NDBI, original NDVI and DEM).
    print("\n> Step 6: Computing Sustainability Score (= 100 - Risk)...")
    gdf["sustainability_score"] = 100 - risk_score

    print(f"  Sustainability Score statistics:")
    print(f"    Min   : {gdf['sustainability_score'].min():.2f}")
    print(f"    Max   : {gdf['sustainability_score'].max():.2f}")
    print(f"    Mean  : {gdf['sustainability_score'].mean():.2f}")

    # ---- Save the enriched dataset -----------------------------------------
    gdf.to_file(master_path, driver="GeoJSON")
    print(f"\n[OK] Updated master file with risk_score and sustainability_score")
    print(f"     Saved to: {master_path}")

    # ---- Save PCA model for reference --------------------------------------
    pca_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["pca_model"])
    with open(pca_path, "wb") as f:
        pickle.dump({"pca": pca, "weights": weights, "feature_names": feature_names}, f)
    print(f"[OK] PCA model saved to: {pca_path}")

    print("\n" + "=" * 60)
    print("  [OK] PCA Scoring complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
