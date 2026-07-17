"""
intervention_engine.py
======================
Selects the optimal intervention for a cell and computes a confidence score
based on SHAP magnitude and data completeness.

Confidence Score formula
------------------------
    shap_score       = min(abs(top_positive_shap) / city_max_shap, 1.0)
    data_completeness = n_indicators_present / 5
    condition_boost  = min(n_conditions * 0.05, 0.15)

    confidence = 0.50 * shap_score
               + 0.35 * data_completeness
               + 0.15 * condition_boost

    Clamped to [0.0, 1.0].

Public API
----------
select_intervention(conditions, primary_issue, catalog)  → dict
compute_confidence(top_positive_shap, city_max_shap,
                   n_conditions, n_indicators_present)   → float
build_evidence_text(primary_issue, cell_comparisons,
                    top_positive_driver, top_positive_shap,
                    intervention_name)                   → str
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from planning.knowledge_base import get_intervention

logger = logging.getLogger("CitySense.planning.intervention_engine")

# ---------------------------------------------------------------------------
# Indicator metadata used when building evidence sentences
# ---------------------------------------------------------------------------
_INDICATOR_LABELS: dict[str, str] = {
    "mean_lst":      "surface temperature",
    "mean_ndvi":     "vegetation cover (NDVI)",
    "mean_ndbi":     "built-up density (NDBI)",
    "mean_dem":      "terrain elevation",
    "uhi_intensity": "Urban Heat Island intensity",
    "risk_score":    "overall risk score",
}

# Maps city_rank_* key → human phrase when the rank is extreme
_RANK_PHRASES: dict[str, tuple[str, str]] = {
    # key: (high-rank phrase, low-rank phrase)
    "city_rank_lst":  (
        "Surface temperature ranks in the hottest {rank:.0f}% of the city",
        "Surface temperature is among the coolest in the city",
    ),
    "city_rank_ndvi": (
        "Vegetation cover is above the city median (top {inv_rank:.0f}%)",
        "Vegetation is in the lowest {rank:.0f}% of the city",
    ),
    "city_rank_ndbi": (
        "Built-up density is among the highest {rank:.0f}% of the city",
        "Built-up density is below average",
    ),
    "city_rank_uhi":  (
        "UHI intensity ranks in the top {rank:.0f}% of the city",
        "UHI intensity is below average",
    ),
    "city_rank_dem":  (
        "Elevation is in the top {inv_rank:.0f}% of the city",
        "Terrain is among the lowest {rank:.0f}% of the city (flood risk)",
    ),
}

# SHAP feature → human-readable label
_SHAP_DRIVER_LABELS: dict[str, str] = {
    "mean_ndvi": "vegetation loss",
    "mean_lst":  "surface temperature",
    "mean_ndbi": "built-up density",
    "mean_dem":  "low terrain elevation",
}


# ---------------------------------------------------------------------------
# Intervention selection
# ---------------------------------------------------------------------------

def select_intervention(
    conditions: list[str],
    primary_issue: str | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the best matching intervention catalog entry.

    Delegates to :func:`~planning.knowledge_base.get_intervention`.  The
    *primary_issue* parameter is accepted for API consistency but the
    full *conditions* list is always passed to the knowledge base so that
    multi-condition overrides can fire correctly.

    Parameters
    ----------
    conditions : list[str]
        All detected environmental conditions for the cell.
    primary_issue : str or None
        The primary issue label (not used directly; present for callers
        that already have it).
    catalog : dict, optional
        Pre-loaded catalog dict; defaults to the cached catalog.

    Returns
    -------
    dict
        Catalog entry with keys: ``primary``, ``secondary``, ``objectives``,
        ``benefits``, ``cost``, ``timeline``, ``complexity``.
    """
    return get_intervention(conditions, catalog)


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def compute_confidence(
    top_positive_shap: float | None,
    city_max_shap: float,
    n_conditions: int,
    n_indicators_present: int,
) -> float:
    """Compute a recommendation confidence score in [0.0, 1.0].

    Parameters
    ----------
    top_positive_shap : float or None
        Absolute value of the top positive SHAP driver for this cell.
        ``None`` or ``NaN`` is treated as 0.
    city_max_shap : float
        City-wide maximum absolute SHAP value (used for normalisation).
        Must be > 0; if ≤ 0 the shap component defaults to 0.
    n_conditions : int
        Number of environmental conditions detected for this cell (≥ 0).
    n_indicators_present : int
        Number of the 5 core indicators (LST, NDVI, NDBI, DEM, UHI) that
        have non-null values for this cell.

    Returns
    -------
    float
        Confidence in [0.0, 1.0].
    """
    # SHAP magnitude component
    shap_val = 0.0
    if top_positive_shap is not None and not _is_nan(top_positive_shap):
        shap_val = abs(float(top_positive_shap))

    if city_max_shap > 0:
        shap_score = min(shap_val / city_max_shap, 1.0)
    else:
        shap_score = 0.0

    # Data completeness (5 total indicators)
    n_present = max(0, min(n_indicators_present, 5))
    data_completeness = n_present / 5.0

    # Condition boost: more detected conditions = stronger multi-indicator evidence
    condition_boost = min(n_conditions * 0.05, 0.15)

    confidence = (
        0.50 * shap_score
        + 0.35 * data_completeness
        + 0.15 * condition_boost
    )
    return float(np.clip(confidence, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Evidence text
# ---------------------------------------------------------------------------

def build_evidence_text(
    primary_issue: str | None,
    cell_comparisons: dict[str, Any],
    top_positive_driver: str | None,
    top_positive_shap: float,
    intervention_name: str,
) -> str:
    """Build the "Why this recommendation?" evidence paragraph.

    The text links the recommendation back to the two most extreme
    percentile ranks and the SHAP top driver.

    Parameters
    ----------
    primary_issue : str or None
        Primary detected environmental condition.
    cell_comparisons : dict
        Output of ``comparative_analysis.compute_cell_comparisons`` —
        contains ``city_rank_*`` and ``*_pct_diff`` fields.
    top_positive_driver : str or None
        Feature name of the top SHAP driver (e.g. ``"mean_lst"``).
    top_positive_shap : float
        Absolute magnitude of the top SHAP value.
    intervention_name : str
        Name of the recommended primary intervention.

    Returns
    -------
    str
        A complete evidence paragraph.  Never empty; never contains
        ``{placeholder}`` tokens.
    """
    sentences: list[str] = []

    # ── 1. Condition sentence ────────────────────────────────────────────────
    if primary_issue:
        sentences.append(f"This area has been identified as having {primary_issue}.")

    # ── 2. Top 2 most extreme rank-based evidence sentences ─────────────────
    rank_evidence = _extract_rank_evidence(cell_comparisons)
    sentences.extend(rank_evidence[:2])

    # ── 3. SHAP driver sentence ──────────────────────────────────────────────
    if top_positive_driver and not _is_nan(top_positive_shap):
        driver_label = _SHAP_DRIVER_LABELS.get(
            top_positive_driver,
            top_positive_driver.replace("mean_", "").replace("_", " "),
        )
        sentences.append(
            f"SHAP analysis identifies {driver_label} as the strongest "
            f"contributor to risk (SHAP value: +{abs(top_positive_shap):.2f})."
        )

    # ── 4. Conclusion ────────────────────────────────────────────────────────
    sentences.append(
        f"Therefore, {intervention_name} provides the highest expected "
        "environmental benefit for this grid."
    )

    result = " ".join(sentences)

    # Safety: ensure no raw {placeholder} tokens remain
    if "{" in result:
        result = (
            f"Recommendation based on detected conditions: {primary_issue or 'General Stress'}. "
            f"Intervention: {intervention_name}."
        )

    return result


def _extract_rank_evidence(cell_comparisons: dict[str, Any]) -> list[str]:
    """Return up to 2 evidence sentences from the most extreme percentile ranks."""
    candidates: list[tuple[float, str]] = []

    for rank_key, (high_tmpl, low_tmpl) in _RANK_PHRASES.items():
        rank = cell_comparisons.get(rank_key)
        if rank is None or _is_nan(rank):
            continue
        rank = float(rank)
        inv_rank = 100.0 - rank

        # Only generate evidence for clearly extreme values (top/bottom 30%)
        if rank >= 70.0:
            try:
                sentence = high_tmpl.format(rank=rank, inv_rank=inv_rank)
                candidates.append((rank, sentence + "."))
            except (KeyError, ValueError):
                pass
        elif rank <= 30.0:
            try:
                sentence = low_tmpl.format(rank=rank, inv_rank=inv_rank)
                candidates.append((100.0 - rank, sentence + "."))
            except (KeyError, ValueError):
                pass

    # Sort by extremity (highest first) and return top 2
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in candidates[:2]]


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
