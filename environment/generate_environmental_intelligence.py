"""
generate_environmental_intelligence.py
=======================================
Pipeline stage: orchestrates the Phase 2 Environmental Intelligence modules
to enrich every grid cell with interpreted environmental analytics and writes
the results to ``data/environmental_intelligence.json``.

This stage is READ-ONLY with respect to ``cells_master.geojson`` — it never
modifies the master dataset.

Output format (one entry per cell_id)
--------------------------------------
{
    "environmental_health": 71.4,
    "environmental_status": "Moderate",
    "city_rank_lst":   93.0,
    "city_rank_ndvi":  18.0,
    "city_rank_ndbi":  78.0,
    "city_rank_uhi":   88.0,
    "city_rank_dem":   22.0,
    "city_rank_risk":  85.0,
    "mean_lst_vs_city_avg":      4.3,
    "mean_ndvi_vs_city_avg":    -0.15,
    "mean_ndbi_vs_city_avg":     0.12,
    "uhi_intensity_vs_city_avg": 3.1,
    "mean_lst_pct_diff":         12.0,
    "mean_ndvi_pct_diff":       -44.0,
    "mean_ndbi_pct_diff":        27.0,
    "uhi_intensity_pct_diff":    18.0,
    "detected_conditions":       ["Urban Heat Island", "Low Vegetation"],
    "primary_issue":             "Urban Heat Island",
    "secondary_issue":           "Low Vegetation",
    "spatial_context":           "This grid is hotter than 93% ...",
    "environmental_summary":     "This grid experiences ..."
}

Usage
-----
    python -m environment.generate_environmental_intelligence   (from project root)
    python environment/generate_environmental_intelligence.py
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import Counter
from pathlib import Path

import geopandas as gpd

from config_loader import load_config, project_path
from environment.comparative_analysis import compute_city_stats, compute_cell_comparisons
from environment.environmental_health import compute_ehi, compute_ehi_batch, get_environmental_status
from environment.indicator_interpreter import (
    detect_conditions,
    generate_spatial_context,
    get_primary_and_secondary_issues,
)
from environment.environmental_summary import generate_summary

logger = logging.getLogger("CitySense.environment.generate_environmental_intelligence")

# Columns that must be present in the master dataset for this stage to run
_REQUIRED_COLUMNS: list[str] = [
    "cell_id",
    "mean_lst",
    "mean_ndvi",
    "mean_ndbi",
    "mean_dem",
    "uhi_intensity",
    "risk_score",
]


def _validate_master(gdf: gpd.GeoDataFrame) -> None:
    """Raise ValueError if any required column is absent."""
    missing = [c for c in _REQUIRED_COLUMNS if c not in gdf.columns]
    if missing:
        raise ValueError(
            f"cells_master.geojson is missing required columns: {missing}. "
            "Ensure all upstream pipeline stages have been run before this stage."
        )


def main() -> None:
    """Compute environmental intelligence for all cells and write JSON output."""
    logger.info("=== City Sense – Phase 2: Generate Environmental Intelligence ===")
    t_start = time.time()

    # ── 1. Load configuration and resolve paths ───────────────────────────
    cfg = load_config()

    master_path = project_path(cfg, "master_data")
    output_path = project_path(cfg, "environmental_intelligence")

    logger.info("Master dataset : %s", master_path)
    logger.info("Output path    : %s", output_path)

    # ── 2. Load master dataset ────────────────────────────────────────────
    if not master_path.exists():
        logger.error("Master dataset not found at '%s'. Run all upstream stages first.", master_path)
        return

    gdf = gpd.read_file(str(master_path))
    logger.info("Loaded %d cells from master dataset.", len(gdf))

    try:
        _validate_master(gdf)
    except ValueError as exc:
        logger.error("%s", exc)
        return

    # ── 3. Compute city-wide statistics (once for the whole dataset) ───────
    logger.info("Computing city-wide statistics …")
    city_stats = compute_city_stats(gdf)
    logger.info(
        "City stats computed for indicators: %s",
        list(city_stats.keys()),
    )

    # ── 4. Batch-compute EHI (vectorised) ─────────────────────────────────
    logger.info("Computing Environmental Health Index (batch) …")
    ehi_series = compute_ehi_batch(gdf, city_stats)
    logger.info(
        "EHI stats: min=%.1f  max=%.1f  mean=%.1f  median=%.1f",
        ehi_series.min(), ehi_series.max(),
        ehi_series.mean(), ehi_series.median(),
    )

    # ── 5. Per-cell enrichment ─────────────────────────────────────────────
    logger.info("Enriching %d cells …", len(gdf))
    output: dict[str, dict] = {}
    status_counter: Counter = Counter()
    issue_counter: Counter = Counter()

    for idx, row in gdf.iterrows():
        cell_id = row["cell_id"]
        ehi = float(ehi_series.loc[idx])
        status = get_environmental_status(ehi)

        # Per-cell comparative analytics
        comparisons = compute_cell_comparisons(row, city_stats, gdf)

        # Condition detection
        conditions = detect_conditions(comparisons, ehi)
        primary_issue, secondary_issue = get_primary_and_secondary_issues(conditions, ehi)

        # Spatial context and narrative summary
        spatial_ctx = generate_spatial_context(comparisons, row)
        summary = generate_summary(row, ehi, status, conditions, comparisons)

        # Build output record
        record: dict = {
            "environmental_health": round(ehi, 2),
            "environmental_status": status,
            # City ranks
            "city_rank_lst":  comparisons.get("city_rank_lst",  50.0),
            "city_rank_ndvi": comparisons.get("city_rank_ndvi", 50.0),
            "city_rank_ndbi": comparisons.get("city_rank_ndbi", 50.0),
            "city_rank_uhi":  comparisons.get(
                "city_rank_uhi",
                comparisons.get("city_rank_uhi_intensity", 50.0),
            ),
            "city_rank_dem":  comparisons.get("city_rank_dem",  50.0),
            "city_rank_risk": comparisons.get(
                "city_rank_risk",
                comparisons.get("city_rank_risk_score", 50.0),
            ),
            # Absolute deviations from city mean
            "mean_lst_vs_city_avg":       comparisons.get("mean_lst_vs_city_avg",       0.0),
            "mean_ndvi_vs_city_avg":      comparisons.get("mean_ndvi_vs_city_avg",      0.0),
            "mean_ndbi_vs_city_avg":      comparisons.get("mean_ndbi_vs_city_avg",      0.0),
            "uhi_intensity_vs_city_avg":  comparisons.get("uhi_intensity_vs_city_avg",  0.0),
            "mean_dem_vs_city_avg":       comparisons.get("mean_dem_vs_city_avg",       0.0),
            # Percentage deviations
            "mean_lst_pct_diff":          comparisons.get("mean_lst_pct_diff",          0.0),
            "mean_ndvi_pct_diff":         comparisons.get("mean_ndvi_pct_diff",         0.0),
            "mean_ndbi_pct_diff":         comparisons.get("mean_ndbi_pct_diff",         0.0),
            "uhi_intensity_pct_diff":     comparisons.get("uhi_intensity_pct_diff",     0.0),
            "mean_dem_pct_diff":          comparisons.get("mean_dem_pct_diff",          0.0),
            # Conditions
            "detected_conditions": conditions,
            "primary_issue":       primary_issue,
            "secondary_issue":     secondary_issue,
            # Narrative
            "spatial_context":        spatial_ctx,
            "environmental_summary":  summary,
        }

        output[cell_id] = record
        status_counter[status] += 1
        if primary_issue:
            issue_counter[primary_issue] += 1

    # ── 6. Write output JSON ───────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(output_path), "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - t_start
    logger.info("Wrote environmental intelligence for %d cells → %s", len(output), output_path)
    logger.info("Completed in %.2f seconds.", elapsed)

    # ── 7. Summary log ────────────────────────────────────────────────────
    logger.info("Environmental Status distribution:")
    for label in ["Excellent", "Good", "Moderate", "Poor", "Critical"]:
        count = status_counter.get(label, 0)
        pct = count / len(output) * 100 if output else 0
        logger.info("  %-12s : %4d cells  (%.1f%%)", label, count, pct)

    if issue_counter:
        logger.info("Top primary environmental issues:")
        for issue, count in issue_counter.most_common(5):
            logger.info("  %-30s : %d cells", issue, count)
    else:
        logger.info("No primary issues detected across any cells.")

    logger.info("=== Environmental Intelligence generation complete! ===")


if __name__ == "__main__":
    # Allow running as a standalone script from the project root
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from utils import setup_logging
    setup_logging()
    main()
