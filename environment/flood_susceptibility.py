"""
flood_susceptibility.py
=======================
Computes the Flood Susceptibility Index (FSI) — a separate sub-model
from the Environmental Health Index (EHI). FSI and EHI are intentionally
kept independent: EHI captures heat/ecology stress, FSI captures
flood/drainage susceptibility. Conflating them would make both harder
to validate and explain.

FSI FORMULA (provisional — domain-weight approach, not fitted to ground truth)
-------------------------------------------------------------------------------
    FSI = 0.30 × inv_dem_score        (low elevation → higher susceptibility)
        + 0.30 × precip_score         (higher monsoon rainfall → higher susceptibility)
        + 0.25 × inv_drain_dist_score  (far from mapped drains → higher susceptibility)
        + 0.15 × ndbi_score           (denser built-up → less infiltration)

Each component is MinMax-normalised to [0,1] using city-wide min/max
(same approach as EHI in environmental_health.py). Indicators where
higher raw value means lower susceptibility are inverted.
Result is scaled to [0, 100], clamped, and bucketed into status labels.

WEIGHTS RATIONALE
-----------------
Weights are domain-expert values consistent with published flood
susceptibility literature (e.g. Costache et al. 2020, Tehrany et al. 2014
for indicator importance in urban flood models). They have NOT been fitted
against the 25 documented flood points in validation/ground_truth_locations.csv
— that dataset is reserved for out-of-sample evaluation in
validation/statistical_validation.py to avoid circularity.

NOT A HYDROLOGICAL MODEL
------------------------
FSI is a proxy susceptibility index built from available public data.
It does NOT model:
  - Actual municipal drainage network capacity or storm-sewer sizing
  - Real-time rainfall-runoff dynamics or hydrodynamic flow routing
  - Historical inundation depth or flood frequency return periods
  - Soil saturation, antecedent moisture conditions, or baseflow

It is appropriate for: first-pass area prioritisation, reconnaissance-scale
screening, and comparative ward-level planning triage.
It is NOT appropriate for: engineering-grade drainage infrastructure sizing
or site-level flood risk certification.

PUBLIC API
----------
compute_fsi(cell, city_stats)                  → float  (single cell)
get_fsi_status(fsi)                            → str
compute_fsi_batch(gdf, city_stats, drain, precip) → pd.Series
generate_fsi_narrative(cell_id, fsi, status, cell_stats) → str
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd
import geopandas as gpd

logger = logging.getLogger("CitySense.environment.flood_susceptibility")

# ---------------------------------------------------------------------------
# FSI weights — must sum to 1.0
# ---------------------------------------------------------------------------
FSI_WEIGHTS: dict[str, float] = {
    "mean_dem":          0.30,   # inverted — low elevation → more susceptible
    "cumul_precip":      0.30,   # higher monsoon rainfall → more susceptible
    "drain_distance_km": 0.25,   # inverted — far from drains → more susceptible
    "mean_ndbi":         0.15,   # higher NDBI → less infiltration
}

# Indicators where HIGHER raw value means LESS susceptible (invert before weighting)
_INVERT: set[str] = {"mean_dem", "drain_distance_km"}

# ---------------------------------------------------------------------------
# FSI status thresholds
# ---------------------------------------------------------------------------
FSI_STATUS_THRESHOLDS: list[tuple[float, float, str]] = [
    (75.0, 100.0, "Severe"),
    (50.0,  74.9, "High"),
    (25.0,  49.9, "Moderate"),
    (0.0,   24.9, "Low"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_nan(value: object) -> bool:
    if value is None:
        return True
    try:
        return math.isnan(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _norm(value: float, vmin: float, vmax: float) -> float:
    """MinMax normalise to [0, 1]. Returns 0.5 if min==max."""
    if vmax == vmin:
        return 0.5
    return float(np.clip((value - vmin) / (vmax - vmin), 0.0, 1.0))


# ---------------------------------------------------------------------------
# City-wide statistics for FSI indicators
# ---------------------------------------------------------------------------

def compute_fsi_city_stats(
    gdf: gpd.GeoDataFrame,
    drain: dict[str, dict],
    precip: dict[str, dict],
) -> dict[str, dict[str, float]]:
    """
    Compute city-wide min/max/mean for all four FSI input indicators.

    Parameters
    ----------
    gdf    : master GeoDataFrame (provides mean_dem, mean_ndbi)
    drain  : drainage_proxy.json dict  {cell_id: {drain_distance_km, ...}}
    precip : precipitation_grid data   {cell_id: {cumul_precip, ...}} or
             loaded from GeoDataFrame if None

    Returns
    -------
    dict keyed by indicator name, each with 'min', 'max', 'mean'.
    """
    stats: dict[str, dict[str, float]] = {}

    # DEM and NDBI from master GDF
    for col in ("mean_dem", "mean_ndbi"):
        if col in gdf.columns:
            series = gdf[col].dropna()
            if not series.empty:
                stats[col] = {
                    "min":  float(series.min()),
                    "max":  float(series.max()),
                    "mean": float(series.mean()),
                }

    # drain_distance_km from drainage proxy dict
    drain_dists = [
        v["drain_distance_km"] for v in drain.values()
        if isinstance(v, dict) and "drain_distance_km" in v
        and not _is_nan(v["drain_distance_km"])
    ]
    if drain_dists:
        stats["drain_distance_km"] = {
            "min":  float(min(drain_dists)),
            "max":  float(max(drain_dists)),
            "mean": float(sum(drain_dists) / len(drain_dists)),
        }

    # cumul_precip from precipitation dict
    precip_vals = [
        v["cumul_precip"] for v in precip.values()
        if isinstance(v, dict) and "cumul_precip" in v
        and not _is_nan(v["cumul_precip"])
    ]
    if precip_vals:
        stats["cumul_precip"] = {
            "min":  float(min(precip_vals)),
            "max":  float(max(precip_vals)),
            "mean": float(sum(precip_vals) / len(precip_vals)),
        }
    else:
        # Precipitation data absent — use a neutral constant so FSI can still run
        logger.warning(
            "No cumul_precip data found. FSI will be computed without rainfall "
            "component (weight redistributed). Run fetch_precipitation.py first."
        )

    return stats


# ---------------------------------------------------------------------------
# Single-cell FSI
# ---------------------------------------------------------------------------

def compute_fsi(
    cell_id: str,
    dem: float | None,
    ndbi: float | None,
    drain_distance_km: float | None,
    cumul_precip: float | None,
    city_stats: dict[str, dict[str, float]],
) -> float:
    """
    Compute the Flood Susceptibility Index for a single grid cell.

    Returns FSI in [0, 100]. Higher = more susceptible to flooding.
    Missing indicators have their weight redistributed proportionally.
    """
    inputs = {
        "mean_dem":          dem,
        "mean_ndbi":         ndbi,
        "drain_distance_km": drain_distance_km,
        "cumul_precip":      cumul_precip,
    }

    weighted_sum        = 0.0
    effective_weight    = 0.0

    for indicator, base_weight in FSI_WEIGHTS.items():
        raw = inputs.get(indicator)

        if raw is None or _is_nan(raw):
            continue  # skip; weight redistributed below

        stat = city_stats.get(indicator)
        if stat is None:
            continue  # indicator has no city stats — skip

        norm = _norm(float(raw), stat["min"], stat["max"])

        # Invert if higher raw value means LOWER susceptibility
        if indicator in _INVERT:
            norm = 1.0 - norm

        weighted_sum     += base_weight * norm
        effective_weight += base_weight

    if effective_weight == 0.0:
        logger.warning("No valid FSI indicators for cell '%s'; returning FSI=50.", cell_id)
        return 50.0

    composite = weighted_sum / effective_weight
    return float(np.clip(composite * 100.0, 0.0, 100.0))


def get_fsi_status(fsi: float) -> str:
    """Map FSI score to status label."""
    for low, high, label in FSI_STATUS_THRESHOLDS:
        if low <= fsi <= high:
            return label
    return "Low" if fsi < 25.0 else "Severe"


# ---------------------------------------------------------------------------
# Batch computation
# ---------------------------------------------------------------------------

def compute_fsi_batch(
    gdf: gpd.GeoDataFrame,
    city_stats: dict[str, dict[str, float]],
    drain: dict[str, dict],
    precip: dict[str, dict],
) -> pd.Series:
    """
    Compute FSI for every row in *gdf* efficiently.

    Parameters
    ----------
    gdf        : master GeoDataFrame
    city_stats : output of compute_fsi_city_stats()
    drain      : drainage_proxy.json dict
    precip     : precipitation dict (cell_id → {cumul_precip, mean_precip})

    Returns
    -------
    pd.Series of FSI values indexed to match gdf.
    """
    results: list[float] = []

    for _, row in gdf.iterrows():
        cell_id = row.get("cell_id", str(row.name))

        dem  = row.get("mean_dem")
        ndbi = row.get("mean_ndbi")

        dp = drain.get(cell_id, {})
        drain_dist = dp.get("drain_distance_km")

        pp = precip.get(cell_id, {})
        cumul = pp.get("cumul_precip")

        fsi = compute_fsi(cell_id, dem, ndbi, drain_dist, cumul, city_stats)
        results.append(fsi)

    series = pd.Series(results, index=gdf.index)
    logger.debug(
        "Batch FSI: min=%.1f  max=%.1f  mean=%.1f",
        series.min(), series.max(), series.mean(),
    )
    return series


# ---------------------------------------------------------------------------
# Narrative generator
# ---------------------------------------------------------------------------

# Contribution phrases for narrative text
_DRIVER_PHRASES: dict[str, dict[str, str]] = {
    "mean_dem": {
        "high": "low terrain elevation (high flood susceptibility topography)",
        "low":  "relatively elevated terrain (lower topographic flood risk)",
    },
    "cumul_precip": {
        "high": "high monsoon rainfall accumulation",
        "low":  "below-average monsoon rainfall",
    },
    "drain_distance_km": {
        "high": "limited mapped drainage infrastructure nearby",
        "low":  "proximity to mapped drainage infrastructure",
    },
    "mean_ndbi": {
        "high": "high impervious surface coverage (reduced infiltration)",
        "low":  "lower impervious surface density",
    },
}


def generate_fsi_narrative(
    cell_id: str,
    fsi: float,
    status: str,
    dem: float | None,
    ndbi: float | None,
    drain_distance_km: float | None,
    cumul_precip: float | None,
    city_stats: dict[str, dict[str, float]],
) -> str:
    """
    Generate a plain-language FSI narrative sentence.

    Returns a 2-sentence description of the cell's flood susceptibility
    based on which indicators are most extreme relative to city averages.
    """
    drivers: list[tuple[float, str]] = []

    def _rank(raw: float | None, indicator: str, invert: bool) -> float:
        """Return how extreme this value is (0=average, 1=maximally extreme)."""
        if raw is None or _is_nan(raw):
            return 0.0
        stat = city_stats.get(indicator)
        if stat is None:
            return 0.0
        norm = _norm(float(raw), stat["min"], stat["max"])
        return (1.0 - norm) if invert else norm

    for indicator, raw, invert in [
        ("mean_dem",          dem,              True),
        ("cumul_precip",      cumul_precip,     False),
        ("drain_distance_km", drain_distance_km, True),
        ("mean_ndbi",         ndbi,             False),
    ]:
        rank = _rank(raw, indicator, invert)
        if rank >= 0.6:   # only call out clearly elevated contributors
            phrase_key = "high"
        elif rank <= 0.4:
            phrase_key = "low"
        else:
            continue
        phrase = _DRIVER_PHRASES[indicator][phrase_key]
        drivers.append((rank, phrase))

    drivers.sort(reverse=True)
    top_drivers = [p for _, p in drivers[:2]]

    if top_drivers:
        driver_str = " and ".join(top_drivers)
        s1 = (
            f"This grid has {status} flood susceptibility (FSI: {fsi:.0f}/100), "
            f"driven primarily by {driver_str}."
        )
    else:
        s1 = (
            f"This grid has {status} flood susceptibility (FSI: {fsi:.0f}/100). "
            f"No single indicator stands out as a dominant driver."
        )

    s2 = (
        "FSI is a proxy index based on elevation, monsoon rainfall, "
        "mapped drainage proximity, and impervious surface coverage — "
        "not a hydrological model of actual drainage capacity."
    )

    return f"{s1} {s2}"
