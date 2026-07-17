"""
environmental_health.py
=======================
Computes the Environmental Health Index (EHI) and Environmental Status
for each grid cell.

EHI Formula
-----------
1. MinMax-normalise each of the 5 indicators to [0, 1] using city-wide
   min/max from ``compute_city_stats()``.
2. Invert NDVI and DEM so that "higher normalised value = more risk" for
   all indicators.
3. Apply ``EHI_WEIGHTS`` to produce a weighted risk composite in [0, 1].
4. ``EHI = (1 - weighted_composite) * 100``  → higher EHI = healthier.
5. Clamp to [0, 100].

NaN handling: if a cell is missing one or more indicator values the
missing indicator's weight is redistributed proportionally across the
remaining present indicators, preserving the relative weighting structure.

Public API
----------
compute_ehi(cell, city_stats)            → float  (single cell)
get_environmental_status(ehi)            → str
compute_ehi_batch(gdf, city_stats)       → pd.Series  (whole dataset)
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import geopandas as gpd

from environment.environment_templates import (
    EHI_WEIGHTS,
    HIGH_IS_BAD,
    HIGH_IS_GOOD,
    STATUS_THRESHOLDS,
)

logger = logging.getLogger("CitySense.environment.environmental_health")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(value: float, vmin: float, vmax: float) -> float:
    """MinMax-normalise *value* to [0, 1].

    Returns 0.5 (neutral) when min == max to avoid division by zero.
    """
    if vmax == vmin:
        return 0.5
    return float(np.clip((value - vmin) / (vmax - vmin), 0.0, 1.0))


def _invert_if_good(norm_value: float, indicator: str) -> float:
    """Return the risk-aligned normalised value.

    For indicators where high values are *good* (NDVI, DEM), invert so
    that a normalised value of 1.0 always means "highest risk" in the
    weighted sum.
    """
    if indicator in HIGH_IS_GOOD:
        return 1.0 - norm_value
    return norm_value


# ---------------------------------------------------------------------------
# Single-cell EHI
# ---------------------------------------------------------------------------

def compute_ehi(
    cell: pd.Series,
    city_stats: dict[str, dict[str, float]],
) -> float:
    """Compute the Environmental Health Index (0–100) for a single cell.

    Parameters
    ----------
    cell : pd.Series
        One row from the master GeoDataFrame.
    city_stats : dict
        Output of :func:`~environment.comparative_analysis.compute_city_stats`.

    Returns
    -------
    float
        EHI score clamped to [0, 100].  Higher = healthier environment.
    """
    weighted_sum = 0.0
    effective_weight_total = 0.0

    for indicator, base_weight in EHI_WEIGHTS.items():
        if indicator not in city_stats:
            # Indicator not in dataset at all — skip silently
            continue

        raw_value = cell.get(indicator)

        # Handle missing or NaN cell value
        if raw_value is None or (isinstance(raw_value, float) and np.isnan(raw_value)):
            continue  # exclude this indicator; weight redistributed below

        stat = city_stats[indicator]
        norm = _normalise(float(raw_value), stat["min"], stat["max"])
        risk_norm = _invert_if_good(norm, indicator)

        weighted_sum += base_weight * risk_norm
        effective_weight_total += base_weight

    if effective_weight_total == 0.0:
        logger.warning("No valid indicators found for cell '%s'; returning EHI=50.", cell.get("cell_id", "?"))
        return 50.0

    # Renormalise in case some indicators were missing
    weighted_composite = weighted_sum / effective_weight_total

    ehi = (1.0 - weighted_composite) * 100.0
    return float(np.clip(ehi, 0.0, 100.0))


# ---------------------------------------------------------------------------
# Status label
# ---------------------------------------------------------------------------

def get_environmental_status(ehi: float) -> str:
    """Map an EHI score to a human-readable status label.

    Parameters
    ----------
    ehi : float
        Environmental Health Index, expected in [0, 100].

    Returns
    -------
    str
        One of: ``"Excellent"``, ``"Good"``, ``"Moderate"``,
        ``"Poor"``, ``"Critical"``.
    """
    for low, high, label in STATUS_THRESHOLDS:
        if low <= ehi <= high:
            return label
    # Fallback for values marginally outside [0, 100] due to floating point
    return "Critical" if ehi < 20.0 else "Excellent"


# ---------------------------------------------------------------------------
# Batch computation (vectorised for performance on the full dataset)
# ---------------------------------------------------------------------------

def compute_ehi_batch(
    gdf: gpd.GeoDataFrame,
    city_stats: dict[str, dict[str, float]],
) -> pd.Series:
    """Compute EHI for every row in *gdf* efficiently.

    Uses vectorised pandas operations instead of row-by-row iteration.
    Falls back to the single-cell function for any row where vectorisation
    is not possible (e.g. all indicators are NaN).

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Master dataset.
    city_stats : dict
        Output of :func:`~environment.comparative_analysis.compute_city_stats`.

    Returns
    -------
    pd.Series
        EHI values (float, 0–100), indexed to match *gdf*.
    """
    present_indicators = [
        ind for ind in EHI_WEIGHTS if ind in city_stats and ind in gdf.columns
    ]

    if not present_indicators:
        logger.error("No EHI indicators found in GeoDataFrame. Returning neutral EHI=50 for all cells.")
        return pd.Series(50.0, index=gdf.index)

    # Build a DataFrame of normalised, risk-aligned values
    norm_df = pd.DataFrame(index=gdf.index)

    for indicator in present_indicators:
        stat = city_stats[indicator]
        vmin, vmax = stat["min"], stat["max"]
        col = gdf[indicator].astype(float)

        if vmax == vmin:
            norm_col = pd.Series(0.5, index=gdf.index)
        else:
            norm_col = ((col - vmin) / (vmax - vmin)).clip(0.0, 1.0)

        if indicator in HIGH_IS_GOOD:
            norm_col = 1.0 - norm_col

        norm_df[indicator] = norm_col

    # Weighted sum, handling NaN via per-row weight redistribution
    weights = pd.Series({ind: EHI_WEIGHTS[ind] for ind in present_indicators})

    # Mask NaN positions
    valid_mask = norm_df.notna()
    # Effective weight per row (sum of weights for non-NaN indicators)
    effective_weights = valid_mask.multiply(weights).sum(axis=1)
    # Weighted sum (NaN treated as 0 via fillna)
    weighted_sum = norm_df.fillna(0.0).multiply(weights).sum(axis=1)

    # Avoid division by zero; rows with no valid indicators → composite = 0.5
    composite = weighted_sum.where(effective_weights > 0, 0.5)
    composite = composite.where(effective_weights == 0, weighted_sum / effective_weights)

    ehi_series = ((1.0 - composite) * 100.0).clip(0.0, 100.0)

    logger.debug(
        "Batch EHI computed: min=%.1f  max=%.1f  mean=%.1f",
        ehi_series.min(), ehi_series.max(), ehi_series.mean(),
    )
    return ehi_series
