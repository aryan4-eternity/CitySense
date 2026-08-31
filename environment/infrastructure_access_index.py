"""
infrastructure_access_index.py
===============================
Computes the Infrastructure Access Index (IAI) per grid cell.

IAI FORMULA
-----------
IAI measures how well-served a cell is by essential urban infrastructure.
Higher IAI = better access. All distance inputs are inverted (closer = better).

    IAI = 0.25 × hospital_access
        + 0.20 × school_access
        + 0.20 × park_access
        + 0.20 × transit_access
        + 0.15 × inv_crowding        (lower density relative to services = better)

Each component is MinMax-normalised to [0,1] from city-wide min/max.
Distance inputs are inverted: norm(max_dist - dist) / (max_dist - min_dist).

LABELING
---------
Status labels describe what is absent from infrastructure, not the residents:
    Excellent (75–100) : Good access to most facility types
    Good      (50–74)  : Adequate access with minor gaps
    Moderate  (25–49)  : Notable access gaps in one or more categories
    Low       (0–24)   : Low infrastructure access across multiple categories

"Low infrastructure access" describes the infrastructure gap — it is a
planning signal for investment priority, not a characterization of residents.

PUBLIC API
----------
compute_iai_city_stats(gdf, infra, geo_meta) → dict
compute_iai(cell_id, cell_data, city_stats)  → float
compute_iai_batch(gdf, city_stats, infra, geo_meta) → pd.Series
get_iai_status(iai)                          → str
generate_iai_narrative(iai, status, dists)   → str
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd
import geopandas as gpd

logger = logging.getLogger("CitySense.environment.infrastructure_access_index")

# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------
IAI_WEIGHTS: dict[str, float] = {
    "hospital_dist_km": 0.25,
    "school_dist_km":   0.20,
    "park_dist_km":     0.20,
    "transit_dist_km":  0.20,
    "population":       0.15,   # inverted crowding
}

# Distance indicators: higher raw value = WORSE access (invert before weighting)
# Population: higher density WITH poor access = worse; included as crowding proxy
_INVERT: set[str] = {"hospital_dist_km", "school_dist_km",
                      "park_dist_km", "transit_dist_km"}
# Population is kept as-is in normalisation direction (handled specially below)

_DEFAULT_DIST = 6.0   # km — used when feature not found within query radius

# ---------------------------------------------------------------------------
# Status thresholds (higher IAI = better access)
# ---------------------------------------------------------------------------
IAI_STATUS_THRESHOLDS: list[tuple[float, float, str]] = [
    (75.0, 100.0, "Excellent"),
    (50.0,  74.9, "Good"),
    (25.0,  49.9, "Moderate"),
    (0.0,   24.9, "Low"),
]


def _nan(v: object) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _norm(val: float, vmin: float, vmax: float) -> float:
    if vmax == vmin:
        return 0.5
    return float(np.clip((val - vmin) / (vmax - vmin), 0.0, 1.0))


# ---------------------------------------------------------------------------
# City-wide stats
# ---------------------------------------------------------------------------

def compute_iai_city_stats(
    gdf: gpd.GeoDataFrame,
    infra: dict[str, dict],
    geo_meta: dict[str, dict],
) -> dict[str, dict[str, float]]:
    """Compute city-wide min/max/mean for all IAI indicators."""
    stats: dict[str, dict[str, float]] = {}

    for key in ("hospital_dist_km", "school_dist_km",
                "park_dist_km", "transit_dist_km"):
        vals = [v[key] for v in infra.values()
                if isinstance(v, dict) and not _nan(v.get(key))]
        if vals:
            stats[key] = {
                "min":  float(min(vals)),
                "max":  float(max(vals)),
                "mean": float(sum(vals) / len(vals)),
            }

    # Population from geo_meta
    pop_vals = [
        v.get("population", 0) or 0
        for v in geo_meta.values()
        if isinstance(v, dict)
    ]
    pop_vals = [p for p in pop_vals if p > 0]
    if pop_vals:
        stats["population"] = {
            "min":  float(min(pop_vals)),
            "max":  float(max(pop_vals)),
            "mean": float(sum(pop_vals) / len(pop_vals)),
        }

    return stats


# ---------------------------------------------------------------------------
# Single-cell IAI
# ---------------------------------------------------------------------------

def compute_iai(
    cell_id: str,
    infra_row: dict,
    geo_meta_row: dict,
    city_stats: dict[str, dict[str, float]],
) -> float:
    """
    Compute IAI for a single cell. Returns 0–100 (higher = better access).
    """
    weighted_sum     = 0.0
    effective_weight = 0.0

    for indicator, base_weight in IAI_WEIGHTS.items():
        if indicator == "population":
            raw = float((geo_meta_row or {}).get("population") or 0)
        else:
            raw = infra_row.get(indicator)
            if raw is None or _nan(raw):
                continue
            raw = float(raw)

        stat = city_stats.get(indicator)
        if stat is None:
            continue

        norm = _norm(raw, stat["min"], stat["max"])

        # Distance indicators: invert so closer = higher score
        # Population: also invert (lower density relative to services = better access)
        norm = 1.0 - norm

        weighted_sum     += base_weight * norm
        effective_weight += base_weight

    if effective_weight == 0.0:
        logger.warning("No valid IAI indicators for cell '%s'; returning IAI=50.", cell_id)
        return 50.0

    return float(np.clip((weighted_sum / effective_weight) * 100.0, 0.0, 100.0))


def get_iai_status(iai: float) -> str:
    for low, high, label in IAI_STATUS_THRESHOLDS:
        if low <= iai <= high:
            return label
    return "Low"


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------

def compute_iai_batch(
    gdf: gpd.GeoDataFrame,
    city_stats: dict[str, dict[str, float]],
    infra: dict[str, dict],
    geo_meta: dict[str, dict],
) -> pd.Series:
    results: list[float] = []
    for _, row in gdf.iterrows():
        cid = row.get("cell_id", str(row.name))
        iai = compute_iai(
            cid,
            infra.get(cid, {}),
            geo_meta.get(cid, {}),
            city_stats,
        )
        results.append(iai)
    s = pd.Series(results, index=gdf.index)
    logger.debug("Batch IAI: min=%.1f  max=%.1f  mean=%.1f",
                 s.min(), s.max(), s.mean())
    return s


# ---------------------------------------------------------------------------
# Narrative
# ---------------------------------------------------------------------------

def generate_iai_narrative(
    iai: float,
    status: str,
    hospital_dist: float | None,
    school_dist:   float | None,
    park_dist:     float | None,
    transit_dist:  float | None,
) -> str:
    """
    Generate a plain-language description of the cell's infrastructure access.
    Uses objective distance language — avoids value judgments about residents.
    """
    parts: list[str] = []
    threshold = 2.5   # km — "limited" if beyond this

    if hospital_dist is not None and hospital_dist >= threshold:
        parts.append(f"nearest healthcare facility is {hospital_dist:.1f} km away")
    if transit_dist is not None and transit_dist >= threshold:
        parts.append(f"nearest transit station is {transit_dist:.1f} km away")
    if park_dist is not None and park_dist >= threshold:
        parts.append(f"nearest park or green space is {park_dist:.1f} km away")
    if school_dist is not None and school_dist >= threshold:
        parts.append(f"nearest school is {school_dist:.1f} km away")

    if parts:
        gaps = "; ".join(parts)
        s1 = (
            f"This grid has {status} infrastructure access (IAI: {iai:.0f}/100). "
            f"Access gaps include: {gaps}."
        )
    else:
        s1 = (
            f"This grid has {status} infrastructure access (IAI: {iai:.0f}/100). "
            f"Key facilities are within {threshold:.0f} km."
        )

    s2 = (
        "IAI measures proximity to hospitals, schools, parks, and transit — "
        "an objective indicator of infrastructure availability, not a judgment "
        "about the community."
    )
    return f"{s1} {s2}"
