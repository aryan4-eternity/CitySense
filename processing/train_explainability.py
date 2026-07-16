"""
train_explainability.py
========================
Week 6 – Explainability Layer

Trains a Random Forest Regressor to reconstruct risk_score from the four
raw indicators (mean_ndvi, mean_lst, mean_ndbi, mean_dem), then uses SHAP
to produce:
    • Global feature-importance bar chart
    • SHAP summary plot
    • Per-cell top positive / negative driver columns
    • Human-readable explanation_text per cell
    • A categorical map coloured by each cell's top positive driver

Outputs:
    models/risk_model.pkl          – trained Random Forest
    models/explain_scaler.pkl      – fitted StandardScaler
    data/feature_importance.png    – global importance chart
    data/shap_summary.png          – SHAP beeswarm / bar plot
    data/top_driver_map.png        – spatial map of dominant driver
    data/cells_master.geojson      – enriched with explanation columns

Usage:
    python processing/train_explainability.py   (from project root)
"""

import os
import pickle
import sys
import warnings
import logging

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for PNG output
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from config_loader import load_config

warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger("CitySense.processing.train_explainability")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))

FEATURE_COLS = ["mean_ndvi", "mean_lst", "mean_ndbi", "mean_dem"]

# Human-friendly labels used in explanation text
FEATURE_LABELS = {
    "mean_ndvi": "NDVI (vegetation)",
    "mean_lst":  "LST (temperature)",
    "mean_ndbi": "NDBI (built-up)",
    "mean_dem":  "DEM (elevation)",
}

# Direction hints – used to phrase the explanation naturally
RISK_DIRECTION = {
    "mean_ndvi": "low",   # low vegetation ↑ risk
    "mean_lst":  "high",  # high temp ↑ risk
    "mean_ndbi": "high",  # high built-up ↑ risk
    "mean_dem":  "low",   # low elevation ↑ risk
}


# ── helpers ────────────────────────────────────────────────────────────────
def _direction_phrase(feature: str, shap_val: float) -> str:
    """Return a short phrase like 'high LST' or 'low NDVI'."""
    label = FEATURE_LABELS.get(feature, feature)
    if shap_val >= 0:
        direction = RISK_DIRECTION.get(feature, "high")
    else:
        direction = "high" if RISK_DIRECTION.get(feature) == "low" else "low"
    return f"{direction} {label}"


def build_explanation_text(row: pd.Series) -> str:
    """Compose a human-readable sentence from the top driver columns."""
    parts = []
    if pd.notna(row.get("top_positive_driver")):
        phrase = _direction_phrase(row["top_positive_driver"],
                                  row["top_positive_shap"])
        parts.append(f"{phrase} (+{abs(row['top_positive_shap']):.2f})")
    if pd.notna(row.get("top_negative_driver")):
        phrase = _direction_phrase(row["top_negative_driver"],
                                  row["top_negative_shap"])
        parts.append(f"{phrase} ({row['top_negative_shap']:+.2f})")

    if not parts:
        return "No dominant driver identified"

    drivers = " and ".join(parts)
    risk = row.get("risk_score", 0)
    level = "High" if risk >= 65 else ("Moderate" if risk >= 40 else "Low")
    return f"{level} risk driven by {drivers}"


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main() -> None:
    """Train the configured surrogate model and generate explanations."""
    logger.info("=== City Sense – Week 6: Explainability Layer ===")

    cfg = load_config()
    model_config = cfg["model"]["explainability"]
    random_seed = cfg["project"]["random_seed"]
    master_path = os.path.join(PROJECT_ROOT,
                               cfg["output_paths"]["master_data"])
    model_dir = os.path.join(PROJECT_ROOT, cfg["output_paths"]["models_dir"])
    os.makedirs(model_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    logger.info("Loading master dataset …")
    gdf = gpd.read_file(master_path)
    logger.info("Loaded %d cells  |  columns: %s", len(gdf), list(gdf.columns))

    X = gdf[FEATURE_COLS].values.copy()
    y = gdf["risk_score"].values.copy()
    logger.info("Features shape: %s  |  Target range: [%.2f, %.2f]",
          X.shape, y.min(), y.max())

    # ------------------------------------------------------------------
    # 2. Train / test split
    # ------------------------------------------------------------------
    logger.info("Splitting data (test_size=%s, random_seed=%s) …", model_config['test_size'], random_seed)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=model_config["test_size"], random_state=random_seed
    )
    logger.info("Train: %d  |  Test: %d", X_train.shape[0], X_test.shape[0])

    # ------------------------------------------------------------------
    # 3. Scale features
    # ------------------------------------------------------------------
    logger.info("Fitting StandardScaler on training set …")
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc = scaler.transform(X_test)

    scaler_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["explain_scaler"])
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    logger.info("[OK] Scaler saved → %s", scaler_path)

    # ------------------------------------------------------------------
    # 4. Train Random Forest
    # ------------------------------------------------------------------
    logger.info("Training RandomForestRegressor (n_estimators=%s, max_depth=%s) …", 
          model_config['n_estimators'], model_config['max_depth'])
    rf = RandomForestRegressor(
        n_estimators=model_config["n_estimators"],
        max_depth=model_config["max_depth"],
        random_state=random_seed,
        n_jobs=-1,
    )
    rf.fit(X_train_sc, y_train)

    model_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["risk_model"])
    with open(model_path, "wb") as f:
        pickle.dump(rf, f)
    logger.info("[OK] Model saved → %s", model_path)

    # ------------------------------------------------------------------
    # 5. Evaluate
    # ------------------------------------------------------------------
    y_pred = rf.predict(X_test_sc)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    logger.info("Test-set evaluation:")
    logger.info("  R² Score             : %.4f", r2)
    logger.info("  Mean Absolute Error  : %.4f", mae)
    logger.info("  Root Mean Sq Error   : %.4f", rmse)

    # ------------------------------------------------------------------
    # 6. Feature importance bar chart
    # ------------------------------------------------------------------
    logger.info("Generating feature importance chart …")
    importances = rf.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]

    fig, ax = plt.subplots(figsize=(7, 4))
    colours = ["#2ecc71", "#e74c3c", "#e67e22", "#3498db"]
    bars = ax.bar(
        [FEATURE_COLS[i] for i in sorted_idx],
        importances[sorted_idx],
        color=[colours[i] for i in sorted_idx],
        edgecolor="white",
        linewidth=0.8,
    )
    ax.set_title("Global Feature Importance (Random Forest)", fontsize=13,
                 fontweight="bold")
    ax.set_ylabel("Importance")
    for bar, val in zip(bars, importances[sorted_idx]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{val:.3f}", ha="center", va="bottom", fontsize=10)
    plt.tight_layout()
    imp_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["feature_importance"])
    fig.savefig(imp_path, dpi=150)
    plt.close(fig)
    logger.info("[OK] Saved → %s", imp_path)

    # ------------------------------------------------------------------
    # 7. SHAP explanations
    # ------------------------------------------------------------------
    logger.info("Computing SHAP values (TreeExplainer, full dataset) …")
    X_full_sc = scaler.transform(X)
    explainer = shap.TreeExplainer(rf)
    shap_values = explainer.shap_values(X_full_sc)
    logger.info("SHAP values shape: %s", shap_values.shape)

    # ── SHAP summary plot ──────────────────────────────────────────────
    logger.info("Generating SHAP summary plot …")
    fig_shap, ax_shap = plt.subplots(figsize=(8, 5))
    shap.summary_plot(
        shap_values,
        features=X,
        feature_names=FEATURE_COLS,
        show=False,
        plot_size=None,
    )
    plt.tight_layout()
    shap_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["shap_summary"])
    plt.savefig(shap_path, dpi=150, bbox_inches="tight")
    plt.close("all")
    logger.info("[OK] Saved → %s", shap_path)

    # ------------------------------------------------------------------
    # 8. Per-cell top drivers
    # ------------------------------------------------------------------
    logger.info("Extracting per-cell top positive / negative drivers …")

    top_pos_driver = []
    top_pos_shap = []
    top_neg_driver = []
    top_neg_shap = []

    for i in range(len(gdf)):
        sv = shap_values[i]

        # ── top positive driver (pushes risk UP) ──
        pos_mask = sv > 0
        if pos_mask.any():
            idx_pos = np.argmax(sv)
            top_pos_driver.append(FEATURE_COLS[idx_pos])
            top_pos_shap.append(float(sv[idx_pos]))
        else:
            top_pos_driver.append(None)
            top_pos_shap.append(0.0)

        # ── top negative driver (pushes risk DOWN) ──
        neg_mask = sv < 0
        if neg_mask.any():
            idx_neg = int(np.argmin(sv))
            top_neg_driver.append(FEATURE_COLS[idx_neg])
            top_neg_shap.append(float(sv[idx_neg]))
        else:
            top_neg_driver.append(None)
            top_neg_shap.append(0.0)

    gdf["top_positive_driver"] = top_pos_driver
    gdf["top_positive_shap"] = top_pos_shap
    gdf["top_negative_driver"] = top_neg_driver
    gdf["top_negative_shap"] = top_neg_shap

    # ── human-readable explanation ─────────────────────────────────────
    gdf["explanation_text"] = gdf.apply(build_explanation_text, axis=1)

    # ------------------------------------------------------------------
    # 9. Save enriched GeoJSON
    # ------------------------------------------------------------------
    gdf.to_file(master_path, driver="GeoJSON")
    logger.info("[OK] Master GeoJSON updated → %s", master_path)
    logger.info("New columns: top_positive_driver, top_positive_shap, top_negative_driver, top_negative_shap, explanation_text")

    # ------------------------------------------------------------------
    # 10. Validation – print a few example cells
    # ------------------------------------------------------------------
    logger.info("Sample cell explanations:")
    samples = gdf.sample(
        n=min(model_config["sample_size"], len(gdf)),
        random_state=model_config["sample_seed"],
    )
    for _, row in samples.iterrows():
        cluster_val = row.get("cluster_label", row.get("cluster", "Unknown"))
        logger.info("  %s  risk=%5.1f  cluster=%s", row['cell_id'], row['risk_score'], cluster_val)
        logger.info("           ➜ %s", row['explanation_text'])

    # ------------------------------------------------------------------
    # 11. Domain-knowledge sanity checks
    # ------------------------------------------------------------------
    logger.info("Sanity checks:")
    imp_rank = sorted(zip(FEATURE_COLS, importances),
                      key=lambda x: x[1], reverse=True)
    top_two = [f[0] for f in imp_rank[:2]]
    expected = {"mean_lst", "mean_ndvi"}
    if expected.issubset(set(top_two)):
        logger.info("✔ LST and NDVI are the top-2 predictors – matches domain knowledge")
    else:
        logger.warning("⚠ Top-2 predictors are %s; expected LST & NDVI. Review if needed.", top_two)

    hot_cells = gdf.nlargest(20, "mean_lst")
    lst_idx = FEATURE_COLS.index("mean_lst")
    hot_shap = shap_values[hot_cells.index, lst_idx]
    frac_pos = (hot_shap > 0).mean()
    logger.info("✔ %d%% of the 20 hottest cells have positive LST SHAP (expected ~100%%)", frac_pos*100)

    # ------------------------------------------------------------------
    # 12. Top-driver categorical map
    # ------------------------------------------------------------------
    logger.info("Generating top-driver map …")
    driver_colours = {
        "mean_ndvi": "#27ae60",
        "mean_lst":  "#e74c3c",
        "mean_ndbi": "#f39c12",
        "mean_dem":  "#2980b9",
    }
    gdf["_driver_colour"] = gdf["top_positive_driver"].map(driver_colours)
    gdf["_driver_colour"] = gdf["_driver_colour"].fillna("#95a5a6")

    fig_map, ax_map = plt.subplots(figsize=(10, 10))
    gdf.plot(ax=ax_map, color=gdf["_driver_colour"], edgecolor="white",
             linewidth=0.3, alpha=0.85)
    ax_map.set_title("Top Positive Risk Driver per Cell",
                     fontsize=14, fontweight="bold")
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")

    patches = [mpatches.Patch(color=c, label=FEATURE_LABELS.get(f, f))
               for f, c in driver_colours.items()]
    ax_map.legend(handles=patches, loc="lower left", fontsize=9,
                  title="Top Driver", title_fontsize=10)
    plt.tight_layout()
    map_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["top_driver_map"])
    fig_map.savefig(map_path, dpi=150)
    plt.close(fig_map)
    logger.info("[OK] Saved → %s", map_path)

    # Clean up temp column
    gdf.drop(columns=["_driver_colour"], inplace=True)

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    logger.info("=== Week 6 Explainability Layer complete! ===")


if __name__ == "__main__":
    main()
