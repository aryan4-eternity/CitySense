"""
ground_truth_check.py
=====================
Priority 2 — Ground-Truth Flood Validation

Spatially joins 25 documented chronic waterlogging locations against
cells_master.geojson and reports what fraction fall within the bottom
quartile of mean_dem (low-elevation cells) and the top quartile of
risk_score (high-risk cells).

METHODOLOGY NOTE
----------------
The 25 locations in validation/ground_truth_locations.csv are chronic
waterlogging spots repeatedly named in multi-year news reports (Times of
India, Indian Express, NDTV, Economic Times 2019–2025) and BMC's own
100-location flood-preparedness list (2020). They are not a random sample —
they represent the most severe and documented flood spots in Mumbai.

The validation asks: does the CitySense risk model assign elevated risk
and/or low-elevation scores to areas known to flood? This is a directional
consistency check, not a probability estimate. A high match rate increases
confidence that the model is spatially meaningful; a low rate would indicate
a mis-alignment worth investigating.

TWO METRICS REPORTED
--------------------
1. DEM quartile check: % of flood points falling in the bottom 25% of
   mean_dem (≤ Q25 elevation). Expectation: flood-prone areas should
   cluster at low elevation — this is a physically necessary (not just
   model-specific) condition.

2. Risk-score quartile check: % of flood points falling in the top 25% of
   risk_score (≥ Q75 risk). This tests whether the composite index
   captures flood-prone areas specifically.

Output
------
  validation/ground_truth_results.txt   — plain-text summary for report
  validation/ground_truth_map.png       — map showing flood points overlaid
                                          on risk_score choropleth with
                                          hit/miss colouring

Usage
-----
    python validation/ground_truth_check.py    (from project root)
    python -m validation.ground_truth_check    (from project root)
"""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from shapely.geometry import Point

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR  = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent

sys.path.insert(0, str(_PROJECT_ROOT))
from config_loader import load_config, project_path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("CitySense.validation.ground_truth_check")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_flood_points(csv_path: Path) -> gpd.GeoDataFrame:
    """Load the ground-truth CSV and convert to a GeoDataFrame (WGS-84)."""
    df = pd.read_csv(csv_path)
    geometry = [Point(lon, lat) for lon, lat in zip(df["lon"], df["lat"])]
    return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")


def _join_to_grid(
    flood_gdf: gpd.GeoDataFrame,
    grid_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Spatial join: for each flood point find the grid cell it falls in.

    Falls back to nearest-cell lookup (within 1.5 km) for any point that
    misses the grid (e.g. sits exactly on a cell boundary or slightly
    outside the AOI extent due to coordinate rounding).
    """
    grid_gdf = grid_gdf.copy()
    grid_gdf["_cell_index"] = grid_gdf.index

    joined = gpd.sjoin(
        flood_gdf,
        grid_gdf[["_cell_index", "cell_id", "mean_dem", "risk_score", "geometry"]],
        how="left",
        predicate="within",
    )

    # Any points that didn't match (index_right is NaN) — nearest fallback
    unmatched_mask = joined["index_right"].isna()
    n_unmatched = unmatched_mask.sum()
    if n_unmatched > 0:
        logger.warning(
            "%d flood points did not fall within any grid cell — "
            "using nearest-cell fallback (max 1.5 km).",
            n_unmatched,
        )
        unmatched = flood_gdf[unmatched_mask.values].copy()
        for idx, row in unmatched.iterrows():
            pt = row.geometry
            grid_gdf["_dist"] = grid_gdf.geometry.centroid.distance(pt)
            nearest = grid_gdf.nsmallest(1, "_dist").iloc[0]
            if nearest["_dist"] < 0.015:   # ~1.5 km in degrees
                joined.at[idx, "index_right"]  = nearest["_cell_index"]
                joined.at[idx, "cell_id"]      = nearest["cell_id"]
                joined.at[idx, "mean_dem"]     = nearest["mean_dem"]
                joined.at[idx, "risk_score"]   = nearest["risk_score"]
            else:
                logger.warning(
                    "  Point '%s' (%.4f, %.4f) has no grid cell within 1.5 km — excluded.",
                    row.get("location_name", idx), pt.y, pt.x,
                )

    return joined.drop(columns=["index_right", "_cell_index"], errors="ignore")


def _compute_quartile_stats(
    joined: gpd.GeoDataFrame,
    grid_gdf: gpd.GeoDataFrame,
) -> dict:
    """Compute the two validation metrics plus supporting statistics."""
    valid = joined.dropna(subset=["mean_dem", "risk_score"])
    n_total   = len(joined)
    n_matched = len(valid)

    # City-wide quartile thresholds (from full grid, not just matched points)
    # For DEM: exclude cells with mean_dem == 0 (sea/tidal flat cells)
    # so the quartile reflects the land-area elevation distribution.
    land_dem = grid_gdf["mean_dem"][grid_gdf["mean_dem"] > 0]
    dem_q25   = float(land_dem.quantile(0.25)) if len(land_dem) > 0 else float(grid_gdf["mean_dem"].quantile(0.25))
    dem_q75   = float(land_dem.quantile(0.75)) if len(land_dem) > 0 else float(grid_gdf["mean_dem"].quantile(0.75))
    risk_q75  = float(grid_gdf["risk_score"].quantile(0.75))
    risk_q25  = float(grid_gdf["risk_score"].quantile(0.25))

    # Metric 1: % flood points in bottom quartile of elevation (DEM ≤ Q25)
    n_low_dem     = int((valid["mean_dem"]   <= dem_q25).sum())
    pct_low_dem   = n_low_dem / n_matched * 100 if n_matched else 0.0

    # Metric 2: % flood points in top quartile of risk score (risk ≥ Q75)
    n_high_risk   = int((valid["risk_score"] >= risk_q75).sum())
    pct_high_risk = n_high_risk / n_matched * 100 if n_matched else 0.0

    # Both conditions met simultaneously
    n_both  = int(((valid["mean_dem"] <= dem_q25) & (valid["risk_score"] >= risk_q75)).sum())
    pct_both = n_both / n_matched * 100 if n_matched else 0.0

    return {
        "n_total":       n_total,
        "n_matched":     n_matched,
        "dem_q25":       dem_q25,
        "dem_q75":       dem_q75,
        "risk_q75":      risk_q75,
        "risk_q25":      risk_q25,
        "n_low_dem":     n_low_dem,
        "pct_low_dem":   pct_low_dem,
        "n_high_risk":   n_high_risk,
        "pct_high_risk": pct_high_risk,
        "n_both":        n_both,
        "pct_both":      pct_both,
        "mean_dem_flood":      float(valid["mean_dem"].mean()),
        "mean_risk_flood":     float(valid["risk_score"].mean()),
        "mean_dem_city":       float(grid_gdf["mean_dem"].mean()),
        "mean_risk_city":      float(grid_gdf["risk_score"].mean()),
        "valid":               valid,
    }


# ---------------------------------------------------------------------------
# Output: text summary
# ---------------------------------------------------------------------------

def _write_text_summary(stats: dict, out_path: Path) -> str:
    """Write and return the plain-text validation summary."""
    valid = stats["valid"]

    lines = [
        "=" * 68,
        "CitySense — Ground-Truth Flood Validation Summary",
        "=" * 68,
        "",
        "DATA SOURCE",
        "-----------",
        "25 chronic waterlogging locations compiled from multi-year news",
        "reports (Times of India, Indian Express, NDTV, Economic Times,",
        "Mumbai Mirror, 2019-2025) and BMC's 100-location flood-preparedness",
        "list (2020). Locations represent the most consistently documented",
        "flood-prone spots in Mumbai — not a random or exhaustive sample.",
        "",
        "SPATIAL MATCHING",
        "----------------",
        f"  Total flood points:    {stats['n_total']}",
        f"  Matched to grid cell:  {stats['n_matched']}",
        "",
        "CITY-WIDE QUARTILE THRESHOLDS",
        "-----------------------------",
        f"  DEM  Q25 (bottom 25% elevation):  {stats['dem_q25']:.2f} m",
        f"  DEM  Q75 (top 25% elevation):     {stats['dem_q75']:.2f} m",
        f"  Risk Q75 (top 25% risk score):    {stats['risk_q75']:.2f} / 100",
        "",
        "METRIC 1 — Elevation (DEM) Check",
        "---------------------------------",
        f"  Flood points in bottom 25% elevation (DEM ≤ {stats['dem_q25']:.1f} m):",
        f"    {stats['n_low_dem']} / {stats['n_matched']}  "
        f"= {stats['pct_low_dem']:.1f}%",
        f"  (City average DEM: {stats['mean_dem_city']:.1f} m  |  "
        f"Flood-point average DEM: {stats['mean_dem_flood']:.1f} m)",
        "",
        "METRIC 2 — Risk Score Check",
        "---------------------------",
        f"  Flood points in top 25% risk score (score ≥ {stats['risk_q75']:.1f}):",
        f"    {stats['n_high_risk']} / {stats['n_matched']}  "
        f"= {stats['pct_high_risk']:.1f}%",
        f"  (City average risk: {stats['mean_risk_city']:.1f}  |  "
        f"Flood-point average risk: {stats['mean_risk_flood']:.1f})",
        "",
        "BOTH CONDITIONS MET (low elevation AND high risk)",
        "--------------------------------------------------",
        f"  {stats['n_both']} / {stats['n_matched']}  = {stats['pct_both']:.1f}%",
        "",
        "PER-LOCATION DETAIL",
        "-------------------",
    ]

    # Per-location table
    lines.append(
        f"  {'Location':<40} {'DEM(m)':>7} {'Risk':>6} {'LowElev':>8} {'HighRisk':>9}"
    )
    lines.append("  " + "-" * 75)
    for _, row in valid.iterrows():
        low_elev  = "✓" if row["mean_dem"]   <= stats["dem_q25"]  else " "
        high_risk = "✓" if row["risk_score"] >= stats["risk_q75"] else " "
        lines.append(
            f"  {str(row['location_name']):<40} "
            f"{row['mean_dem']:>7.1f} "
            f"{row['risk_score']:>6.1f} "
            f"{'['+low_elev+']':>8} "
            f"{'['+high_risk+']':>9}"
        )

    lines += [
        "",
        "INTERPRETATION",
        "--------------",
        "DEM check measures a physically necessary condition: flood-prone",
        "areas must be low-lying. A high match rate confirms the CitySense",
        "grid captures topographic flood susceptibility.",
        "",
        "Risk-score check measures whether the composite index specifically",
        "elevates known flood spots. Because the risk index is dominated by",
        "heat indicators (LST 50% combined), not flood indicators, lower",
        "match rates here are expected and do not invalidate the index —",
        "they confirm it is a heat-and-ecology composite, not a flood model.",
        "",
        "LIMITATIONS",
        "-----------",
        "1. The 25 locations are a convenience sample of the most-reported",
        "   flood spots, biased toward high-profile and well-documented areas.",
        "   Less-covered low-income neighbourhoods may be under-represented.",
        "2. Coordinates are geocoded from place names, not from official",
        "   inundation surveys. Accuracy is ±200–500 m typical for",
        "   street-level locations.",
        "3. The 1 km² grid cell resolution means a single cell may contain",
        "   both flood-prone and non-flood-prone sub-areas.",
        "=" * 68,
    ]

    text = "\n".join(lines)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return text


# ---------------------------------------------------------------------------
# Output: map
# ---------------------------------------------------------------------------

def _make_map(
    grid_gdf: gpd.GeoDataFrame,
    valid: gpd.GeoDataFrame,
    stats: dict,
    out_path: Path,
) -> None:
    """Plot risk-score choropleth with flood points coloured by hit/miss."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 9))
    fig.patch.set_facecolor("#0a0f1a")

    # ── Panel 1: DEM check ──────────────────────────────────────────────────
    ax1 = axes[0]
    ax1.set_facecolor("#0a0f1a")
    grid_gdf.plot(
        ax=ax1,
        column="mean_dem",
        cmap="Blues",
        edgecolor="none",
        alpha=0.75,
        legend=False,
    )

    hit_dem  = valid[valid["mean_dem"] <= stats["dem_q25"]]
    miss_dem = valid[valid["mean_dem"] >  stats["dem_q25"]]
    hit_dem.plot( ax=ax1, color="#00ff9f", markersize=55, marker="o", zorder=5, label="Low elevation ✓") if len(hit_dem) > 0 else None
    miss_dem.plot(ax=ax1, color="#ff3b5c", markersize=55, marker="X", zorder=5, label="Not low elevation") if len(miss_dem) > 0 else None

    ax1.set_title(
        f"Metric 1 — DEM Elevation Check\n"
        f"{stats['n_low_dem']}/{stats['n_matched']} flood spots in bottom 25% elevation "
        f"({stats['pct_low_dem']:.0f}%)",
        color="white", fontsize=11, pad=8,
    )
    ax1.set_xlabel("Longitude", color="#7aa8cc", fontsize=8)
    ax1.set_ylabel("Latitude",  color="#7aa8cc", fontsize=8)
    ax1.tick_params(colors="#7aa8cc", labelsize=7)
    for spine in ax1.spines.values():
        spine.set_edgecolor("#1a3a5c")
    ax1.legend(loc="lower left", fontsize=8, facecolor="#0d1f35", labelcolor="white",
               edgecolor="#1a3a5c")

    # ── Panel 2: Risk score check ───────────────────────────────────────────
    ax2 = axes[1]
    ax2.set_facecolor("#0a0f1a")
    grid_gdf.plot(
        ax=ax2,
        column="risk_score",
        cmap="RdYlGn_r",
        edgecolor="none",
        alpha=0.75,
        legend=False,
        vmin=0, vmax=100,
    )

    hit_risk  = valid[valid["risk_score"] >= stats["risk_q75"]]
    miss_risk = valid[valid["risk_score"] <  stats["risk_q75"]]
    hit_risk.plot( ax=ax2, color="#00ff9f", markersize=55, marker="o", zorder=5, label="High risk ✓") if len(hit_risk) > 0 else None
    miss_risk.plot(ax=ax2, color="#ff3b5c", markersize=55, marker="X", zorder=5, label="Not high risk") if len(miss_risk) > 0 else None

    ax2.set_title(
        f"Metric 2 — Risk Score Check\n"
        f"{stats['n_high_risk']}/{stats['n_matched']} flood spots in top 25% risk score "
        f"({stats['pct_high_risk']:.0f}%)",
        color="white", fontsize=11, pad=8,
    )
    ax2.set_xlabel("Longitude", color="#7aa8cc", fontsize=8)
    ax2.set_ylabel("Latitude",  color="#7aa8cc", fontsize=8)
    ax2.tick_params(colors="#7aa8cc", labelsize=7)
    for spine in ax2.spines.values():
        spine.set_edgecolor("#1a3a5c")
    ax2.legend(loc="lower left", fontsize=8, facecolor="#0d1f35", labelcolor="white",
               edgecolor="#1a3a5c")

    # ── Shared title ────────────────────────────────────────────────────────
    fig.suptitle(
        "CitySense — Ground-Truth Flood Validation\n"
        "25 Documented Chronic Waterlogging Locations vs. Model Grid",
        color="white", fontsize=13, y=1.01,
    )

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    logger.info("[OK] Validation map saved → %s", out_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> dict:
    """Run the full ground-truth validation and write outputs."""
    logger.info("=== CitySense — Ground-Truth Flood Validation ===")

    cfg = load_config()
    master_path = project_path(cfg, "master_data")
    csv_path    = _SCRIPT_DIR / "ground_truth_locations.csv"
    txt_out     = _SCRIPT_DIR / "ground_truth_results.txt"
    map_out     = _SCRIPT_DIR / "ground_truth_map.png"

    # Load inputs
    logger.info("Loading master dataset …")
    grid_gdf = gpd.read_file(str(master_path))
    if grid_gdf.crs is None:
        grid_gdf.set_crs(epsg=4326, inplace=True)

    logger.info("Loading flood ground-truth locations …")
    flood_gdf = _load_flood_points(csv_path)
    logger.info("  %d flood points loaded.", len(flood_gdf))

    # Check required columns
    for col in ("mean_dem", "risk_score"):
        if col not in grid_gdf.columns:
            logger.error(
                "Column '%s' missing from master dataset. "
                "Run the full pipeline first.", col
            )
            return {}

    # Spatial join
    logger.info("Spatial join: flood points → grid cells …")
    joined = _join_to_grid(flood_gdf, grid_gdf)

    # Compute stats
    stats = _compute_quartile_stats(joined, grid_gdf)

    # Log key results
    logger.info(
        "RESULT — DEM check:  %d/%d (%.1f%%) flood points in bottom 25%% elevation",
        stats["n_low_dem"], stats["n_matched"], stats["pct_low_dem"],
    )
    logger.info(
        "RESULT — Risk check: %d/%d (%.1f%%) flood points in top 25%% risk score",
        stats["n_high_risk"], stats["n_matched"], stats["pct_high_risk"],
    )
    logger.info(
        "RESULT — Both:       %d/%d (%.1f%%) flood points meet both conditions",
        stats["n_both"], stats["n_matched"], stats["pct_both"],
    )

    # Write outputs
    logger.info("Writing text summary → %s", txt_out)
    summary = _write_text_summary(stats, txt_out)
    print("\n" + summary)

    logger.info("Generating validation map …")
    _make_map(grid_gdf, stats["valid"], stats, map_out)

    logger.info("=== Ground-truth validation complete! ===")
    return stats


if __name__ == "__main__":
    main()
