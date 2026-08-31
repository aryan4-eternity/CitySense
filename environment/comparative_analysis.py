"""
comparative_analysis.py
=======================
Computes city-wide statistics and per-cell percentile rankings for all
environmental indicators.

All functions are pure (no side effects, no file I/O) so they can be
called from the pipeline stage or unit tests without any setup.

Public API
----------
compute_city_stats(gdf)              → dict of per-indicator statistics
compute_cell_comparisons(cell, ...)  → dict of ranks, deviations, pct diffs
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
import geopandas as gpd

logger = logging.getLogger("CitySense.environment.comparative_analysis")

# ---------------------------------------------------------------------------
# Indicators and their "direction" for percentile ranking
# ---------------------------------------------------------------------------
# rank_ascending=True  → higher raw value gets a higher rank (worse)
# rank_ascending=False → lower raw value gets a higher rank (worse for that indicator)
_INDICATOR_RANK_CONFIG: dict[str, bool] = {
    "mean_lst":      True,   # higher temp  → worse
    "mean_ndvi":     False,  # lower NDVI   → worse (rank 100 = most vegetated → best)
    "mean_ndbi":     True,   # higher NDBI  → worse
    "uhi_intensity": True,   # higher UHI   → worse
    "mean_dem":      False,  # lower DEM    → more flood-prone → worse
    "risk_score":    True,   # higher risk  → worse
}

# All indicators we compute stats for
_ALL_INDICATORS: list[str] = list(_INDICATOR_RANK_CONFIG.keys())


def compute_city_stats(gdf: gpd.GeoDataFrame) -> dict[str, dict[str, float]]:
    """Compute city-wide descriptive statistics for all environmental indicators.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        The master dataset containing all indicator columns.

    Returns
    -------
    dict
        Nested dict keyed by indicator name, each containing:
        ``mean``, ``median``, ``std``, ``min``, ``max``, ``p10``, ``p25``,
        ``p75``, ``p90``.  Missing or all-NaN columns are skipped with a
        warning rather than raising an exception.
    """
    stats: dict[str, dict[str, float]] = {}

    for col in _ALL_INDICATORS:
        if col not in gdf.columns:
            logger.warning("Column '%s' not found in GeoDataFrame — skipping city stats.", col)
            continue

        series = gdf[col].dropna()
        if series.empty:
            logger.warning("Column '%s' has no valid values — skipping city stats.", col)
            continue

        stats[col] = {
            "mean":   float(series.mean()),
            "median": float(series.median()),
            "std":    float(series.std()),
            "min":    float(series.min()),
            "max":    float(series.max()),
            "p10":    float(series.quantile(0.10)),
            "p25":    float(series.quantile(0.25)),
            "p75":    float(series.quantile(0.75)),
            "p90":    float(series.quantile(0.90)),
        }

    logger.debug("City stats computed for indicators: %s", list(stats.keys()))
    return stats


def _percentile_rank(value: float, series: pd.Series, ascending: bool) -> float:
    """Return the percentile rank (0–100) of *value* within *series*.

    Parameters
    ----------
    value : float
        The cell value to rank.
    series : pd.Series
        The city-wide values for the indicator (NaN already dropped).
    ascending : bool
        If True, higher values get a higher rank (e.g. LST: hotter = rank 100).
        If False, lower values get a higher rank — the series is inverted before
        ranking so that rank 100 still means "most concerning" for that indicator.
    """
    if series.empty:
        return 50.0  # neutral fallback

    if not ascending:
        # Invert: rank of original value in the inverted series
        # equivalent to (1 - cdf) * 100
        n_below = (series > value).sum()          # values worse (lower) than this
        n_equal = (series == value).sum()
        rank = (n_below + 0.5 * n_equal) / len(series) * 100.0
    else:
        n_below = (series < value).sum()
        n_equal = (series == value).sum()
        rank = (n_below + 0.5 * n_equal) / len(series) * 100.0

    return float(np.clip(rank, 0.0, 100.0))


def compute_cell_comparisons(
    cell: pd.Series,
    city_stats: dict[str, dict[str, float]],
    gdf: gpd.GeoDataFrame,
) -> dict[str, Any]:
    """Compute comparative analytics for a single grid cell.

    Percentile rank convention (consistent for all indicators):
    * Rank 100 → the cell is at the "worst" extreme for that indicator.
      - LST rank 100  = hottest cell in the city.
      - NDVI rank 100 = most vegetated cell (best for ecology).
      - NDBI rank 100 = most built-up cell.
      - DEM rank 100  = highest elevation cell (least flood-prone).
      - UHI rank 100  = highest UHI intensity.
      - risk rank 100 = highest risk score.

    Callers (indicator_interpreter, dashboard) must interpret the rank
    direction correctly using the ``_INDICATOR_RANK_CONFIG`` convention or
    the explicit ``city_rank_ndvi`` / ``city_rank_dem`` semantics documented
    in ``environment_templates.CONDITION_THRESHOLDS``.

    Parameters
    ----------
    cell : pd.Series
        A single row from the master GeoDataFrame.
    city_stats : dict
        Output of :func:`compute_city_stats`.
    gdf : gpd.GeoDataFrame
        Full master dataset (used to compute exact ranks against full series).

    Returns
    -------
    dict
        Keys:
        ``city_rank_<indicator>``  – percentile rank 0–100 (float)
        ``<indicator>_vs_city_avg`` – absolute difference from city mean
        ``<indicator>_pct_diff``   – percentage difference from city mean
        For each indicator present in both *cell* and *city_stats*.
    """
    comparisons: dict[str, Any] = {}

    for col, ascending in _INDICATOR_RANK_CONFIG.items():
        if col not in city_stats:
            # Column missing from dataset; fill with neutral values
            comparisons[f"city_rank_{col.replace('mean_', '')}"] = 50.0
            comparisons[f"{col}_vs_city_avg"] = 0.0
            comparisons[f"{col}_pct_diff"] = 0.0
            continue

        cell_val = cell.get(col)
        stat = city_stats[col]
        city_mean = stat["mean"]

        # Handle missing cell value gracefully
        if cell_val is None or (isinstance(cell_val, float) and np.isnan(cell_val)):
            comparisons[f"city_rank_{col.replace('mean_', '')}"] = 50.0
            comparisons[f"{col}_vs_city_avg"] = 0.0
            comparisons[f"{col}_pct_diff"] = 0.0
            continue

        cell_val = float(cell_val)

        # Percentile rank
        series = gdf[col].dropna()
        rank = _percentile_rank(cell_val, series, ascending)
        rank_key = f"city_rank_{col.replace('mean_', '')}"
        comparisons[rank_key] = round(rank, 1)

        # Absolute deviation
        abs_diff = cell_val - city_mean
        comparisons[f"{col}_vs_city_avg"] = round(abs_diff, 4)

        # Percentage deviation  (avoid division by zero)
        if city_mean != 0.0:
            pct_diff = (abs_diff / abs(city_mean)) * 100.0
        else:
            pct_diff = 0.0
        comparisons[f"{col}_pct_diff"] = round(pct_diff, 1)

    # ── Convenience aliases used by the dashboard and templates ────────────
    # "city_rank_uhi"  comes from "uhi_intensity" key after replace:
    # "uhi_intensity".replace("mean_", "") → "uhi_intensity"
    # We add a short alias "city_rank_uhi" if not already present.
    if "city_rank_uhi_intensity" in comparisons and "city_rank_uhi" not in comparisons:
        comparisons["city_rank_uhi"] = comparisons["city_rank_uhi_intensity"]

    # Short alias for risk
    if "city_rank_risk_score" in comparisons and "city_rank_risk" not in comparisons:
        comparisons["city_rank_risk"] = comparisons["city_rank_risk_score"]

    return comparisons


def get_indicator_rank_config() -> dict[str, bool]:
    """Return the indicator → ascending mapping (read-only copy).

    Useful for callers that need to know the direction convention.
    """
    return dict(_INDICATOR_RANK_CONFIG)
