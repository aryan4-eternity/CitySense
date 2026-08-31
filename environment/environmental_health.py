"""
environmental_health.py
=======================
Computes the Environmental Health Index (EHI) and Environmental Status
for each grid cell using benchmark-anchored or min-max normalization.

EHI Formula
-----------
1. Normalise each of the 5 indicators to [0, 1] using benchmark anchors (good G, worst W):
   - LST / UHI / NDBI (higher = worse): risk_norm = clip((value - G) / (W - G), 0.0, 1.0)
   - NDVI / DEM (higher = better):      risk_norm = clip((G - value) / (G - W), 0.0, 1.0)
   When anchors are not provided, falls back to city_stats min/max with inversion for NDVI/DEM.
2. Apply EHI_WEIGHTS to produce a weighted risk composite in [0, 1].
3. EHI = (1 - weighted_composite) * 100  -> higher EHI = healthier.
4. Clamp to [0, 100].

NaN handling: if a cell is missing one or more indicator values the
missing indicator's weight is redistributed proportionally across the
remaining present indicators, preserving the relative weighting structure.

Public API
----------
compute_ehi(cell, city_stats=None, anchors=None)       -> float     (single cell)
get_environmental_status(ehi)                          -> str
compute_ehi_batch(gdf, city_stats=None, anchors=None)  -> pd.Series (whole dataset)
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

def _calculate_indicator_risk_norm(
    value: float,
    indicator: str,
    anchor_dict: dict[str, float] | None = None,
    stat_dict: dict[str, float] | None = None,
) -> float:
    """Calculate normalized risk in [0, 1] for an indicator.

    Uses benchmark anchors (good G, worst W) if available; otherwise falls back
    to city_stats min/max with direction inversion.
    """
    if anchor_dict is not None and "good" in anchor_dict and "worst" in anchor_dict:
        g = float(anchor_dict["good"])
        w = float(anchor_dict["worst"])
        if g == w:
            return 0.5
        if indicator in HIGH_IS_BAD:
            return float(np.clip((value - g) / (w - g), 0.0, 1.0))
        else:
            return float(np.clip((g - value) / (g - w), 0.0, 1.0))

    if stat_dict is not None:
        vmin = float(stat_dict.get("min", 0.0))
        vmax = float(stat_dict.get("max", 1.0))
        if vmax == vmin:
            return 0.5
        norm = float(np.clip((value - vmin) / (vmax - vmin), 0.0, 1.0))
        if indicator in HIGH_IS_GOOD:
            return 1.0 - norm
        return norm

    return 0.5


# ---------------------------------------------------------------------------
# Single-cell EHI
# ---------------------------------------------------------------------------

def compute_ehi(
    cell: pd.Series,
    city_stats: dict[str, dict[str, float]] | None = None,
    anchors: dict[str, dict[str, float]] | None = None,
) -> float:
    """Compute the Environmental Health Index (0–100) for a single cell.

    Parameters
    ----------
    cell : pd.Series
        One row from the master GeoDataFrame.
    city_stats : dict, optional
        Output of :func:`~environment.comparative_analysis.compute_city_stats`.
    anchors : dict, optional
        Output of :func:`~environment.benchmarks.compute_benchmarks`.

    Returns
    -------
    float
        EHI score clamped to [0, 100]. Higher = healthier environment.
    """
    ref_dict = anchors if anchors is not None else (city_stats or {})

    weighted_sum = 0.0
    effective_weight_total = 0.0

    for indicator, base_weight in EHI_WEIGHTS.items():
        if indicator not in ref_dict:
            # Indicator not in reference stats/anchors — skip
            continue

        raw_value = cell.get(indicator)

        # Handle missing or NaN cell value
        if raw_value is None or (isinstance(raw_value, float) and np.isnan(raw_value)):
            continue  # exclude this indicator; weight redistributed below

        anchor_entry = anchors.get(indicator) if anchors else None
        stat_entry = city_stats.get(indicator) if city_stats else None

        risk_norm = _calculate_indicator_risk_norm(
            float(raw_value),
            indicator,
            anchor_dict=anchor_entry,
            stat_dict=stat_entry,
        )

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
    city_stats: dict[str, dict[str, float]] | None = None,
    anchors: dict[str, dict[str, float]] | None = None,
) -> pd.Series:
    """Compute EHI for every row in *gdf* efficiently.

    Uses vectorised pandas operations. Supports benchmark anchors or city_stats min/max.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Master dataset.
    city_stats : dict, optional
        Output of :func:`~environment.comparative_analysis.compute_city_stats`.
    anchors : dict, optional
        Output of :func:`~environment.benchmarks.compute_benchmarks`.

    Returns
    -------
    pd.Series
        EHI values (float, 0–100), indexed to match *gdf*.
    """
    ref_dict = anchors if anchors is not None else (city_stats or {})

    present_indicators = [
        ind for ind in EHI_WEIGHTS if ind in ref_dict and ind in gdf.columns
    ]

    if not present_indicators:
        logger.error("No EHI indicators found in GeoDataFrame. Returning neutral EHI=50 for all cells.")
        return pd.Series(50.0, index=gdf.index)

    norm_df = pd.DataFrame(index=gdf.index)

    for indicator in present_indicators:
        col = gdf[indicator].astype(float)

        if anchors is not None and indicator in anchors:
            g = float(anchors[indicator]["good"])
            w = float(anchors[indicator]["worst"])
            if g == w:
                norm_col = pd.Series(0.5, index=gdf.index)
            elif indicator in HIGH_IS_BAD:
                norm_col = ((col - g) / (w - g)).clip(0.0, 1.0)
            else:
                norm_col = ((g - col) / (g - w)).clip(0.0, 1.0)
        elif city_stats is not None and indicator in city_stats:
            stat = city_stats[indicator]
            vmin, vmax = stat["min"], stat["max"]
            if vmax == vmin:
                norm_col = pd.Series(0.5, index=gdf.index)
            else:
                norm_col = ((col - vmin) / (vmax - vmin)).clip(0.0, 1.0)
            if indicator in HIGH_IS_GOOD:
                norm_col = 1.0 - norm_col
        else:
            norm_col = pd.Series(0.5, index=gdf.index)

        norm_df[indicator] = norm_col

    # Weighted sum, handling NaN via per-row weight redistribution
    weights = pd.Series({ind: EHI_WEIGHTS[ind] for ind in present_indicators})

    # Mask NaN positions
    valid_mask = norm_df.notna()
    # Effective weight per row (sum of weights for non-NaN indicators)
    effective_weights = valid_mask.multiply(weights).sum(axis=1)
    # Weighted sum (NaN treated as 0 via fillna)
    weighted_sum = norm_df.fillna(0.0).multiply(weights).sum(axis=1)

    # Avoid division by zero; rows with no valid indicators -> composite = 0.5
    composite = weighted_sum.where(effective_weights > 0, 0.5)
    composite = composite.where(effective_weights == 0, weighted_sum / effective_weights)

    ehi_series = ((1.0 - composite) * 100.0).clip(0.0, 100.0)

    logger.debug(
        "Batch EHI computed: min=%.1f  max=%.1f  mean=%.1f",
        ehi_series.min(), ehi_series.max(), ehi_series.mean(),
    )
    return ehi_series
