"""
priority_engine.py
==================
Computes the Planning Priority Score (0–100) and Priority Label for each
grid cell.

Priority Score formula (domain-justified weights)
--------------------------------------------------
    priority_score =
        0.35 * (100 - ehi)          # lower EHI  → higher urgency
      + 0.30 * risk_score           # PCA risk score (0–100)
      + 0.20 * population_score     # normalised city population (0–100)
      + 0.15 * strategic_weight     # land-use strategic importance (0–100)

All components are in [0, 100] before weighting; result clamped to [0, 100].

Priority Labels
---------------
    80–100  Critical
    60–79   High
    40–59   Medium
    20–39   Low
     0–19   Very Low

Public API
----------
compute_population_score(population, max_population)  → float
compute_priority_score(ehi, risk_score, population,
                        dominant_land_use, max_population) → float
get_priority_label(priority_score)                    → str
compute_priority_batch(gdf, env_intel, geo_meta)      → pd.DataFrame
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd
import geopandas as gpd

from planning.knowledge_base import get_strategic_weight

logger = logging.getLogger("CitySense.planning.priority_engine")

# ---------------------------------------------------------------------------
# Formula weights — must sum to 1.0
# ---------------------------------------------------------------------------
_W_EHI        = 0.35   # urgency from environmental health deficit
_W_RISK       = 0.30   # PCA risk score
_W_POPULATION = 0.20   # exposed population
_W_STRATEGIC  = 0.15   # land-use strategic importance

# ---------------------------------------------------------------------------
# Priority label thresholds (lower bound inclusive)
# ---------------------------------------------------------------------------
_PRIORITY_THRESHOLDS: list[tuple[float, str]] = [
    (80.0, "Critical"),
    (60.0, "High"),
    (40.0, "Medium"),
    (20.0, "Low"),
    (0.0,  "Very Low"),
]


# ---------------------------------------------------------------------------
# Single-value helpers
# ---------------------------------------------------------------------------

def compute_population_score(population: int | float, max_population: int | float) -> float:
    """Normalise *population* to [0, 100] using the city-wide maximum.

    Parameters
    ----------
    population : int or float
        Cell-level estimated population.
    max_population : int or float
        City-wide maximum population (used as the normalisation ceiling).

    Returns
    -------
    float
        Normalised score in [0, 100].  Returns 0 if max_population ≤ 0
        or population is NaN/None.
    """
    if max_population <= 0:
        return 0.0
    if population is None or (isinstance(population, float) and math.isnan(population)):
        return 0.0
    return float(np.clip((population / max_population) * 100.0, 0.0, 100.0))


def compute_priority_score(
    ehi: float,
    risk_score: float,
    population: int | float,
    dominant_land_use: str | None,
    max_population: int | float,
) -> float:
    """Compute the Planning Priority Score for a single grid cell.

    Parameters
    ----------
    ehi : float
        Environmental Health Index (0–100).  Lower = more urgent.
    risk_score : float
        PCA-derived risk score (0–100).  Higher = more urgent.
    population : int or float
        Estimated cell population.
    dominant_land_use : str or None
        Land use classification from geographic metadata.
    max_population : int or float
        City-wide maximum cell population for normalisation.

    Returns
    -------
    float
        Priority Score clamped to [0, 100].
    """
    # Sanitise inputs
    ehi        = float(ehi)        if not _is_nan(ehi)        else 50.0
    risk_score = float(risk_score) if not _is_nan(risk_score) else 50.0

    ehi_urgency    = 100.0 - np.clip(ehi, 0.0, 100.0)
    risk_component = np.clip(risk_score, 0.0, 100.0)
    pop_score      = compute_population_score(population, max_population)
    strategic      = get_strategic_weight(dominant_land_use)

    score = (
        _W_EHI        * ehi_urgency
        + _W_RISK       * risk_component
        + _W_POPULATION * pop_score
        + _W_STRATEGIC  * strategic
    )
    return float(np.clip(score, 0.0, 100.0))


def get_priority_label(priority_score: float) -> str:
    """Map a Priority Score to a human-readable label.

    Parameters
    ----------
    priority_score : float
        Score in [0, 100].

    Returns
    -------
    str
        One of: ``"Critical"``, ``"High"``, ``"Medium"``, ``"Low"``,
        ``"Very Low"``.
    """
    for lower_bound, label in _PRIORITY_THRESHOLDS:
        if priority_score >= lower_bound:
            return label
    return "Very Low"


# ---------------------------------------------------------------------------
# Batch computation
# ---------------------------------------------------------------------------

def compute_priority_batch(
    gdf: gpd.GeoDataFrame,
    env_intel: dict[str, dict],
    geo_meta: dict[str, dict],
) -> pd.DataFrame:
    """Compute Priority Score and Label for every cell in *gdf*.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Master dataset containing at least ``cell_id`` and ``risk_score``.
    env_intel : dict
        Output of ``generate_environmental_intelligence`` keyed by ``cell_id``.
    geo_meta : dict
        Geographic metadata keyed by ``cell_id`` (may be empty ``{}``).

    Returns
    -------
    pd.DataFrame
        Columns: ``cell_id``, ``priority_score``, ``planning_priority``.
        Row order matches *gdf*.
    """
    # Pre-compute city-wide max population from geo_meta
    populations = [
        v.get("population", 0) or 0
        for v in geo_meta.values()
        if isinstance(v, dict)
    ]
    max_population: float = max(populations) if populations else 1.0
    if max_population <= 0:
        max_population = 1.0

    logger.debug(
        "Priority batch: %d cells | max_population=%.0f",
        len(gdf), max_population,
    )

    records: list[dict] = []

    for _, row in gdf.iterrows():
        cell_id = row.get("cell_id", str(row.name))

        # EHI from Phase 2 intelligence; fall back to (100 - risk_score)
        ei = env_intel.get(cell_id, {})
        ehi = ei.get("environmental_health")
        if ehi is None or _is_nan(ehi):
            risk_val = row.get("risk_score") or 50.0
            ehi = float(np.clip(100.0 - float(risk_val), 0.0, 100.0))

        risk_score = row.get("risk_score") or 50.0

        # Population and land use from geographic metadata
        gm = geo_meta.get(cell_id, {})
        population    = gm.get("population", 0) or 0
        land_use      = gm.get("dominant_land_use") or "Unknown"

        score = compute_priority_score(
            ehi=ehi,
            risk_score=float(risk_score),
            population=population,
            dominant_land_use=land_use,
            max_population=max_population,
        )
        label = get_priority_label(score)

        records.append({
            "cell_id":          cell_id,
            "priority_score":   round(score, 2),
            "planning_priority": label,
        })

    result = pd.DataFrame(records)
    logger.debug(
        "Priority distribution: %s",
        result["planning_priority"].value_counts().to_dict(),
    )
    return result


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _is_nan(value: object) -> bool:
    """Return True if *value* is None or a float NaN."""
    if value is None:
        return True
    try:
        return math.isnan(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
