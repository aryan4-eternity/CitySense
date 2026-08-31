"""
statistical_validation.py
==========================
Evaluates three classifiers against the 25 documented Mumbai flood
ground-truth locations in validation/ground_truth_locations.csv:

  1. Inverted DEM (raw elevation baseline — physical prior only)
  2. Composite risk_score (existing EHI-based index, heat/ecology dominated)
  3. Flood Susceptibility Index — FSI (new, flood-specific sub-model)

METHODOLOGY — AVOIDING CIRCULARITY
-------------------------------------
FSI weights were set by domain reasoning, NOT fitted against the 25
flood points. This means the 25-point evaluation is genuinely
out-of-sample for FSI (and also for risk_score, which was never tuned
on these points either). No train/holdout split is used here because
n=25 is too small for a split to produce reliable holdout estimates —
acknowledging this limitation explicitly is more defensible than
performing a split that would leave only 7 holdout points.

METRICS REPORTED
-----------------
For each classifier, at the optimal threshold (maximising F1):
  - AUC-ROC    : area under the ROC curve
  - Average Precision (AP) : area under the P-R curve
  - Precision, Recall, F1 at the optimal threshold
  - Number of true positives / false negatives

Labels: flood cells = 1, all other cells = 0.
Score for each cell = the classifier's continuous score for that cell
(higher = predicted more flood-prone).

Score derivation:
  - inv_dem_score    = 100 − min-max-normalised(mean_dem) × 100
  - risk_score       = risk_score column from cells_master.geojson
  - fsi_score        = flood_susceptibility_score from flood_susceptibility.json
                       (requires generate_flood_susceptibility.py to have been run)

IMPORTANT CAVEATS
-----------------
- 25 points is extremely small for AUC estimation. 95% CIs are wide.
  Results should be interpreted directionally, not as precise estimates.
- The 25 locations are a non-random convenience sample of the most
  documented flood spots — likely biased toward higher-visibility,
  higher-severity events in well-covered areas. This may inflate all
  three classifiers' apparent performance.
- See §15.2 and §FSI of CITYSENSE_TECHNICAL_DOCUMENTATION.md.

Outputs:
    validation/statistical_results.txt   — plain-text table for report
    validation/roc_curves.png            — ROC + PR curves for all three

Usage:
    python validation/statistical_validation.py    (from project root)
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from config_loader import load_config, project_path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("CitySense.validation.statistical_validation")


# ---------------------------------------------------------------------------
# Metric helpers (no sklearn dependency — computed from scratch)
# ---------------------------------------------------------------------------

def _roc_curve(y_true: np.ndarray, y_score: np.ndarray
               ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (fpr, tpr, thresholds) arrays."""
    thresholds = np.sort(np.unique(y_score))[::-1]
    fpr_list, tpr_list = [0.0], [0.0]

    n_pos = y_true.sum()
    n_neg = len(y_true) - n_pos

    for t in thresholds:
        pred = (y_score >= t).astype(int)
        tp   = ((pred == 1) & (y_true == 1)).sum()
        fp   = ((pred == 1) & (y_true == 0)).sum()
        tpr_list.append(tp / n_pos if n_pos > 0 else 0.0)
        fpr_list.append(fp / n_neg if n_neg > 0 else 0.0)

    fpr_list.append(1.0)
    tpr_list.append(1.0)
    return np.array(fpr_list), np.array(tpr_list), np.append(thresholds, thresholds[-1])


def _pr_curve(y_true: np.ndarray, y_score: np.ndarray
              ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (precision, recall, thresholds) arrays."""
    thresholds = np.sort(np.unique(y_score))[::-1]
    prec_list, rec_list = [], []

    n_pos = y_true.sum()

    for t in thresholds:
        pred = (y_score >= t).astype(int)
        tp = ((pred == 1) & (y_true == 1)).sum()
        fp = ((pred == 1) & (y_true == 0)).sum()
        fn = ((pred == 0) & (y_true == 1)).sum()
        prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        rec  = tp / n_pos     if n_pos       > 0 else 0.0
        prec_list.append(prec)
        rec_list.append(rec)

    return np.array(prec_list), np.array(rec_list), thresholds


def _auc(x: np.ndarray, y: np.ndarray) -> float:
    """Trapezoidal AUC."""
    return float(np.trapz(y, x))


def _average_precision(prec: np.ndarray, rec: np.ndarray) -> float:
    """Area under the P-R curve via trapezoidal rule."""
    # Sort by recall ascending
    order = np.argsort(rec)
    return float(np.trapz(prec[order], rec[order]))


def _best_f1_threshold(
    y_true: np.ndarray, y_score: np.ndarray
) -> tuple[float, float, float, float, int, int]:
    """
    Find the threshold that maximises F1.
    Returns (threshold, precision, recall, f1, tp, fn).
    """
    best = (0.0, 0.0, 0.0, 0.0, 0, int(y_true.sum()))
    n_pos = int(y_true.sum())

    for t in np.unique(y_score):
        pred = (y_score >= t).astype(int)
        tp = int(((pred == 1) & (y_true == 1)).sum())
        fp = int(((pred == 1) & (y_true == 0)).sum())
        fn = int(((pred == 0) & (y_true == 1)).sum())
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec  = tp / n_pos     if n_pos      > 0 else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        if f1 > best[3]:
            best = (float(t), prec, rec, f1, tp, fn)

    return best


# ---------------------------------------------------------------------------
# Spatial join: flood points → grid cells
# ---------------------------------------------------------------------------

def _join_flood_points(
    flood_csv: Path,
    gdf: gpd.GeoDataFrame,
) -> set[str]:
    """Return the set of cell_ids that contain at least one flood point."""
    df = pd.read_csv(flood_csv)
    flood_cells: set[str] = set()

    for _, row in df.iterrows():
        pt = Point(float(row["lon"]), float(row["lat"]))
        hits = gdf[gdf.geometry.contains(pt)]
        if not hits.empty:
            flood_cells.add(str(hits.iloc[0]["cell_id"]))
        else:
            # nearest-cell fallback within 2km
            gdf_copy = gdf.copy()
            gdf_copy["_d"] = gdf_copy.geometry.centroid.distance(pt)
            nearest = gdf_copy.nsmallest(1, "_d")
            if not nearest.empty and nearest.iloc[0]["_d"] < 0.02:
                flood_cells.add(str(nearest.iloc[0]["cell_id"]))

    return flood_cells


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=== CitySense — Statistical Flood Validation ===")

    cfg            = load_config()
    master_path    = project_path(cfg, "master_data")
    fsi_path       = _PROJECT_ROOT / "data" / "flood_susceptibility.json"
    flood_csv      = _SCRIPT_DIR / "ground_truth_locations.csv"
    out_txt        = _SCRIPT_DIR / "statistical_results.txt"
    out_png        = _SCRIPT_DIR / "roc_curves.png"

    # ── Load grid ────────────────────────────────────────────────────────
    logger.info("Loading master dataset …")
    gdf = gpd.read_file(str(master_path))
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    logger.info("Loaded %d cells.", len(gdf))

    # ── Load FSI scores ──────────────────────────────────────────────────
    fsi_data: dict[str, dict] = {}
    if fsi_path.exists():
        with fsi_path.open("r", encoding="utf-8") as f:
            fsi_data = json.load(f)
        logger.info("FSI data loaded: %d cells.", len(fsi_data))
    else:
        logger.warning(
            "flood_susceptibility.json not found. FSI classifier will be skipped. "
            "Run: python -m environment.generate_flood_susceptibility"
        )

    # ── Spatial join: flood points → cell labels ─────────────────────────
    logger.info("Joining flood ground-truth points to grid …")
    flood_cells = _join_flood_points(flood_csv, gdf)
    logger.info("%d of 25 flood points matched to %d unique cells.", 25, len(flood_cells))

    # ── Build score arrays ───────────────────────────────────────────────
    # For each cell: y=1 if it contains a flood point, else y=0
    cell_ids   = gdf["cell_id"].tolist()
    y_true     = np.array([1 if cid in flood_cells else 0 for cid in cell_ids])

    dem_vals   = gdf["mean_dem"].fillna(gdf["mean_dem"].median()).values
    dem_min, dem_max = dem_vals.min(), dem_vals.max()
    # inv_dem: higher score = lower elevation = more susceptible
    inv_dem_score = 100.0 * (1.0 - (dem_vals - dem_min) / (dem_max - dem_min + 1e-9))

    risk_score = gdf["risk_score"].fillna(50.0).values

    fsi_score  = None
    if fsi_data:
        fsi_score = np.array([
            fsi_data.get(cid, {}).get("flood_susceptibility_score", 50.0)
            for cid in cell_ids
        ])

    n_pos = int(y_true.sum())
    n_neg = int((y_true == 0).sum())
    logger.info("Labels: %d flood cells (positive) | %d non-flood cells (negative)",
                n_pos, n_neg)

    # ── Compute metrics for each classifier ──────────────────────────────
    classifiers: list[tuple[str, np.ndarray]] = [
        ("Inverted DEM (baseline)",   inv_dem_score),
        ("Composite Risk Score",      risk_score),
    ]
    if fsi_score is not None:
        classifiers.append(("Flood Susceptibility Index (FSI)", fsi_score))

    results: list[dict] = []
    for name, scores in classifiers:
        fpr, tpr, _   = _roc_curve(y_true, scores)
        prec, rec, _  = _pr_curve(y_true, scores)
        auc_roc       = _auc(fpr, tpr)
        avg_prec      = _average_precision(prec, rec)
        t_opt, p_opt, r_opt, f1_opt, tp, fn = _best_f1_threshold(y_true, scores)

        results.append({
            "name":    name,
            "auc_roc": auc_roc,
            "avg_prec": avg_prec,
            "precision": p_opt,
            "recall":    r_opt,
            "f1":        f1_opt,
            "tp":        tp,
            "fn":        fn,
            "threshold": t_opt,
            "fpr":  fpr,
            "tpr":  tpr,
            "prec": prec,
            "rec":  rec,
        })
        logger.info(
            "%-38s  AUC=%.3f  AP=%.3f  P=%.2f  R=%.2f  F1=%.2f  TP=%d  FN=%d",
            name, auc_roc, avg_prec, p_opt, r_opt, f1_opt, tp, fn,
        )

    # ── Write text report ────────────────────────────────────────────────
    lines = [
        "=" * 72,
        "CitySense — Statistical Flood Validation",
        "=" * 72,
        "",
        "METHODOLOGY",
        "-----------",
        "25 documented Mumbai flood locations (validation/ground_truth_locations.csv)",
        "spatial-joined to the 836-cell grid. Cells containing ≥1 flood point = 1;",
        "all other cells = 0.",
        "",
        f"Positive (flood) cells : {n_pos}",
        f"Negative cells         : {n_neg}",
        f"Base rate (prevalence) : {n_pos / (n_pos + n_neg):.3f}",
        "",
        "FSI weights were NOT fitted to these points (domain-weight only).",
        "All three classifiers are evaluated out-of-sample.",
        "n=25 is small — AUC estimates have wide uncertainty. Interpret directionally.",
        "",
        "RESULTS",
        "-------",
        f"  {'Classifier':<38}  {'AUC-ROC':>7}  {'Avg Prec':>8}  {'Precision':>9}  {'Recall':>6}  {'F1':>5}  {'TP':>3}/{n_pos}",
        "  " + "-" * 82,
    ]

    for r in results:
        lines.append(
            f"  {r['name']:<38}  {r['auc_roc']:>7.3f}  {r['avg_prec']:>8.3f}  "
            f"{r['precision']:>9.2f}  {r['recall']:>6.2f}  {r['f1']:>5.2f}  "
            f"{r['tp']:>3}/{n_pos}"
        )

    baseline_auc = results[0]["auc_roc"] if results else 0.5
    lines += [
        "",
        "INTERPRETATION",
        "--------------",
        "AUC > 0.5 indicates above-random discrimination. AUC = 1.0 is perfect.",
        "Average Precision summarises the P-R curve (relevant when classes are imbalanced).",
        f"Random baseline AUC: 0.500  |  Inverted-DEM baseline AUC: {baseline_auc:.3f}",
        "",
        "LIMITATIONS",
        "-----------",
        "1. n=25 flood points — too small for robust AUC estimation.",
        "   Treat as directional evidence, not a precise performance claim.",
        "2. Convenience sample biased toward well-reported flood locations.",
        "3. Coordinate accuracy ±200-500m; may miss or mis-assign cells.",
        "4. FSI precipitation component uses 2023 monsoon CHIRPS data if available;",
        "   degrades gracefully to DEM+NDBI+drainage if precipitation data absent.",
        "5. No train/holdout split — entire sample used for evaluation (see docstring).",
        "=" * 72,
    ]

    text = "\n".join(lines)
    out_txt.write_text(text, encoding="utf-8")
    print("\n" + text)
    logger.info("Text results → %s", out_txt)

    # ── Plot ROC + PR curves ─────────────────────────────────────────────
    colors = ["#ff3b5c", "#ffb340", "#00ff9f"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("#0a0f1a")

    for ax in (ax1, ax2):
        ax.set_facecolor("#0d1f35")
        ax.tick_params(colors="#7aa8cc", labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor("#1a3a5c")

    for i, r in enumerate(results):
        col = colors[i % len(colors)]
        ax1.plot(r["fpr"], r["tpr"], color=col, linewidth=2,
                 label=f"{r['name']} (AUC={r['auc_roc']:.3f})")
        # sort rec for PR curve
        order = np.argsort(r["rec"])
        ax2.plot(r["rec"][order], r["prec"][order], color=col, linewidth=2,
                 label=f"{r['name']} (AP={r['avg_prec']:.3f})")

    ax1.plot([0, 1], [0, 1], "--", color="#3a607f", linewidth=1, label="Random (AUC=0.500)")
    ax1.set_xlabel("False Positive Rate", color="#7aa8cc", fontsize=9)
    ax1.set_ylabel("True Positive Rate",  color="#7aa8cc", fontsize=9)
    ax1.set_title("ROC Curves — Flood Ground-Truth Validation",
                  color="white", fontsize=11, pad=8)
    ax1.legend(fontsize=8, facecolor="#0d1f35", labelcolor="white", edgecolor="#1a3a5c")

    ax2.axhline(n_pos / (n_pos + n_neg), linestyle="--", color="#3a607f",
                linewidth=1, label=f"Random baseline (AP≈{n_pos/(n_pos+n_neg):.3f})")
    ax2.set_xlabel("Recall",    color="#7aa8cc", fontsize=9)
    ax2.set_ylabel("Precision", color="#7aa8cc", fontsize=9)
    ax2.set_title("Precision-Recall Curves — Flood Ground-Truth Validation",
                  color="white", fontsize=11, pad=8)
    ax2.legend(fontsize=8, facecolor="#0d1f35", labelcolor="white", edgecolor="#1a3a5c")

    fig.suptitle("CitySense — Statistical Flood Classifier Comparison\n"
                 f"n=25 ground-truth flood locations (out-of-sample, non-fitted)",
                 color="white", fontsize=12, y=1.01)
    plt.tight_layout()
    fig.savefig(str(out_png), dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    logger.info("ROC/PR plot → %s", out_png)
    logger.info("=== Statistical validation complete! ===")


if __name__ == "__main__":
    main()
