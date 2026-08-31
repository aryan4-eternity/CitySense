"""
train_explainability.py
========================
Indicator Attribution Layer — Sensitivity Analysis of the Composite Risk Index

PURPOSE AND SCOPE
-----------------
This module performs a *sensitivity analysis* of the PCA-derived composite
risk index using a Random Forest surrogate model and SHAP (SHapley Additive
exPlanations).

IMPORTANT — what this analysis is and is not:

  IS:   A decomposition of the composite risk index. The Random Forest is
        trained to reconstruct risk_score (itself a linear PCA combination of
        the four raw indicators). SHAP values therefore quantify how much each
        raw indicator *contributes to the composite index* for each grid cell,
        revealing whether heat stress (LST/UHI), vegetation loss (NDVI), or
        built-up density (NDBI) dominates a particular cell's score.

  IS NOT: An independent explainable-AI model. Because the target variable
        (risk_score) is derived from the same four input features, the expected
        R² is near 1.0 by construction — it confirms that the RF has
        approximated the PCA formula, not that it has discovered hidden
        real-world drivers of urban risk.

This is analogous to the sensitivity analysis of composite indicators
described in OECD (2008) "Handbook on Composite Indicators", §6: using
variable-importance methods to decompose index components rather than to
make causal or predictive claims.

WHAT THE OUTPUTS MEAN
---------------------
  top_positive_driver   The raw indicator that most strongly *pushes a cell's
                        risk score upward* within the composite index formula.
  top_positive_shap     Magnitude of that contribution (SHAP units ≈ risk
                        score points on a 0-100 scale).
  top_negative_driver   The indicator that most strongly *suppresses* the score.
  explanation_text      Human-readable attribution sentence, e.g.:
                          "Risk index dominated by high LST (+16.2) and
                           attenuated by low NDBI (-0.3)."
                        This describes *index composition*, not causal claims.

Outputs:
    models/risk_model.pkl       – trained Random Forest surrogate
    models/explain_scaler.pkl   – fitted StandardScaler
    data/feature_importance.png – indicator contribution bar chart
    data/shap_summary.png       – SHAP attribution summary plot
    data/top_driver_map.png     – spatial map of dominant indicator per cell
    data/cells_master.geojson   – enriched with attribution columns

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
    """Compose a per-cell indicator attribution sentence.

    The sentence describes which raw indicator most strongly drives this
    cell's composite risk index score *upward* and which attenuates it.
    This is an index-decomposition statement, not a causal explanation of
    real-world risk.

    Example output:
        "Risk index dominated by high LST (+19.01) and attenuated by
         low NDBI (-0.33)."
    """
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
        return "No dominant indicator identified in composite index"

    drivers = " and attenuated by ".join(parts) if len(parts) == 2 else parts[0]
    risk = row.get("risk_score", 0)
    level = "High" if risk >= 65 else ("Moderate" if risk >= 40 else "Low")
    return f"{level} composite risk index — dominated by {drivers}"


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main() -> None:
    """Train the RF surrogate model and compute per-cell indicator attribution."""
    logger.info("=== City Sense – Indicator Attribution (Sensitivity Analysis) ===")
    logger.info("NOTE: RF trained to reconstruct PCA risk index from same features.")
    logger.info("      R²~1 is expected by construction. SHAP = index decomposition.")

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
    # 5. Evaluate surrogate fit
    # NOTE: R²~1 is expected because the target (risk_score) is a linear
    # combination of the same features. This confirms the RF approximates
    # the PCA formula accurately — it does not validate predictive power
    # against an independent outcome.
    # ------------------------------------------------------------------
    y_pred = rf.predict(X_test_sc)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    logger.info("Surrogate fit (RF reconstructing PCA index — R²~1 expected by construction):")
    logger.info("  R² Score             : %.4f  (confirms RF≈PCA formula, not independent validation)", r2)
    logger.info("  Mean Absolute Error  : %.4f  (index score points, 0-100 scale)", mae)
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
    ax.set_title("Indicator Contribution to Composite Risk Index (RF Surrogate)", fontsize=13,
                 fontweight="bold")
    ax.set_ylabel("Attribution Importance")
    for bar, val in zip(bars, importances[sorted_idx]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{val:.3f}", ha="center", va="bottom", fontsize=10)
    plt.tight_layout()
    imp_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["feature_importance"])
    fig.savefig(imp_path, dpi=150)
    plt.close(fig)
    logger.info("[OK] Saved → %s", imp_path)

    # ------------------------------------------------------------------
    # 7. SHAP attribution values
    # SHAP here decomposes the composite index into per-indicator
    # contributions. These values show which raw indicator explains
    # each cell's position in the 0-100 risk index space.
    # They do NOT identify independent causal drivers of urban risk.
    # ------------------------------------------------------------------
    logger.info("Computing SHAP attribution values (TreeExplainer, full dataset) …")
    X_full_sc = scaler.transform(X)
    explainer = shap.TreeExplainer(rf)
    shap_values = explainer.shap_values(X_full_sc)
    logger.info("SHAP values shape: %s", shap_values.shape)

    # ── SHAP attribution summary plot ─────────────────────────────────
    logger.info("Generating SHAP attribution summary plot …")
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
    # 8. Per-cell indicator attribution
    # top_positive_driver: indicator with the highest positive SHAP value
    #   → most strongly drives this cell's score UPWARD in the index
    # top_negative_driver: indicator with the most negative SHAP value
    #   → most strongly suppresses this cell's score in the index
    # ------------------------------------------------------------------
    logger.info("Extracting per-cell indicator attribution …")

    top_pos_driver = []
    top_pos_shap = []
    top_neg_driver = []
    top_neg_shap = []

    for i in range(len(gdf)):
        sv = shap_values[i]

        # ── dominant upward contributor (raises index score) ──
        pos_mask = sv > 0
        if pos_mask.any():
            idx_pos = np.argmax(sv)
            top_pos_driver.append(FEATURE_COLS[idx_pos])
            top_pos_shap.append(float(sv[idx_pos]))
        else:
            top_pos_driver.append(None)
            top_pos_shap.append(0.0)

        # ── dominant downward contributor (suppresses index score) ──
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

    # ── per-cell attribution text ──────────────────────────────────────
    gdf["explanation_text"] = gdf.apply(build_explanation_text, axis=1)

    # ------------------------------------------------------------------
    # 9. Save enriched GeoJSON
    # ------------------------------------------------------------------
    gdf.to_file(master_path, driver="GeoJSON")
    logger.info("[OK] Master GeoJSON updated → %s", master_path)
    logger.info("Attribution columns added: top_positive_driver, top_positive_shap, "
                "top_negative_driver, top_negative_shap, explanation_text")

    # ------------------------------------------------------------------
    # 10. Sample attribution outputs for log review
    # ------------------------------------------------------------------
    logger.info("Sample indicator attribution outputs:")
    samples = gdf.sample(
        n=min(model_config["sample_size"], len(gdf)),
        random_state=model_config["sample_seed"],
    )
    for _, row in samples.iterrows():
        cluster_val = row.get("cluster_label", row.get("cluster", "Unknown"))
        logger.info("  %s  risk=%5.1f  cluster=%s", row['cell_id'], row['risk_score'], cluster_val)
        logger.info("           ➜ %s", row['explanation_text'])

    # ------------------------------------------------------------------
    # 11. Consistency checks
    # These checks verify internal consistency of the attribution, not
    # external validity. LST dominating hot cells and NDVI dominating
    # green cells is expected from the PCA formula design.
    # ------------------------------------------------------------------
    logger.info("Internal consistency checks:")
    imp_rank = sorted(zip(FEATURE_COLS, importances),
                      key=lambda x: x[1], reverse=True)
    top_two = [f[0] for f in imp_rank[:2]]
    expected = {"mean_lst", "mean_ndvi"}
    if expected.issubset(set(top_two)):
        logger.info("✔ LST and NDVI are the top-2 index contributors — consistent with PCA loadings")
    else:
        logger.warning("⚠ Top-2 contributors are %s; expected LST & NDVI. Review PCA loadings.", top_two)

    hot_cells = gdf.nlargest(20, "mean_lst")
    lst_idx = FEATURE_COLS.index("mean_lst")
    hot_shap = shap_values[hot_cells.index, lst_idx]
    frac_pos = (hot_shap > 0).mean()
    logger.info("✔ %d%% of the 20 hottest cells have positive LST attribution "
                "(consistent with PCA loading direction)", frac_pos * 100)

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
    ax_map.set_title("Dominant Index Contributor per Cell (SHAP Attribution)",
                     fontsize=14, fontweight="bold")
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")

    patches = [mpatches.Patch(color=c, label=FEATURE_LABELS.get(f, f))
               for f, c in driver_colours.items()]
    ax_map.legend(handles=patches, loc="lower left", fontsize=9,
                  title="Dominant Contributor", title_fontsize=10)
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
    logger.info("=== Indicator Attribution (Sensitivity Analysis) complete! ===")


if __name__ == "__main__":
    main()
