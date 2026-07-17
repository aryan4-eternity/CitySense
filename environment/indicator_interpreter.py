"""
indicator_interpreter.py
========================
Detects named environmental conditions for a grid cell and generates
a spatial context sentence.

All functions are pure (no side effects, no file I/O).

Public API
----------
detect_conditions(cell_comparisons, ehi)
    → list[str]  — ordered list of detected condition names

get_primary_and_secondary_issues(conditions, ehi)
    → tuple[str | None, str | None]

generate_spatial_context(cell_comparisons, cell)
    → str  — human-readable spatial context sentence
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from environment.environment_templates import (
    CONDITION_THRESHOLDS,
    SPATIAL_LST_TEMPLATES,
    SPATIAL_NDVI_TEMPLATES,
)

logger = logging.getLogger("CitySense.environment.indicator_interpreter")

# ---------------------------------------------------------------------------
# Condition priority order
# (used to pick primary / secondary when multiple conditions fire)
# ---------------------------------------------------------------------------
_CONDITION_PRIORITY: list[str] = [
    "Urban Heat Island",
    "Low Vegetation",
    "High Built-up Density",
    "Flood Susceptibility",
    "Environmental Stress",
    "Ecological Stability",
]


# ---------------------------------------------------------------------------
# Condition detection
# ---------------------------------------------------------------------------

def _evaluate_rule(
    key: str,
    operator: str,
    threshold: float,
    cell_comparisons: dict[str, Any],
    ehi: float,
) -> bool:
    """Evaluate a single condition rule against cell data.

    Special key ``_ehi`` is evaluated against the *ehi* argument directly.
    All other keys are looked up in *cell_comparisons*.
    """
    if key == "_ehi":
        value = ehi
    else:
        value = cell_comparisons.get(key)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return False
        value = float(value)

    if operator == ">=":
        return value >= threshold
    if operator == "<=":
        return value <= threshold
    if operator == ">":
        return value > threshold
    if operator == "<":
        return value < threshold
    if operator == "==":
        return value == threshold

    logger.warning("Unknown operator '%s' in condition rule — skipping.", operator)
    return False


def detect_conditions(
    cell_comparisons: dict[str, Any],
    ehi: float,
) -> list[str]:
    """Detect all applicable environmental conditions for a cell.

    Each condition in ``CONDITION_THRESHOLDS`` fires only when *all* of
    its rules are satisfied (AND logic).

    Parameters
    ----------
    cell_comparisons : dict
        Output of
        :func:`~environment.comparative_analysis.compute_cell_comparisons`.
    ehi : float
        The cell's Environmental Health Index (0–100).

    Returns
    -------
    list[str]
        Detected condition names, ordered by ``_CONDITION_PRIORITY``.
        Empty list if no conditions are detected.
    """
    detected: list[str] = []

    for condition_name, rules in CONDITION_THRESHOLDS.items():
        all_rules_pass = all(
            _evaluate_rule(key, op, threshold, cell_comparisons, ehi)
            for key, (op, threshold) in rules.items()
        )
        if all_rules_pass:
            detected.append(condition_name)

    # Return in priority order
    ordered = [c for c in _CONDITION_PRIORITY if c in detected]
    # Append any conditions not in the priority list (future-proofing)
    ordered += [c for c in detected if c not in _CONDITION_PRIORITY]
    return ordered


# ---------------------------------------------------------------------------
# Primary / secondary issue selection
# ---------------------------------------------------------------------------

def get_primary_and_secondary_issues(
    conditions: list[str],
    ehi: float,  # noqa: ARG001  — kept for API consistency / future use
) -> tuple[str | None, str | None]:
    """Return the top two environmental issues from a detected condition list.

    "Ecological Stability" is treated as a positive condition, not an issue,
    so it is excluded from the issue selection unless it is the *only*
    condition detected.

    Parameters
    ----------
    conditions : list[str]
        Output of :func:`detect_conditions`.
    ehi : float
        EHI score (reserved for future weighted selection logic).

    Returns
    -------
    tuple[str | None, str | None]
        ``(primary_issue, secondary_issue)``.  Either may be ``None`` if
        fewer than 1 or 2 conditions are available.
    """
    # Separate issues from positive conditions
    issues = [c for c in conditions if c != "Ecological Stability"]
    positive = [c for c in conditions if c == "Ecological Stability"]

    if not issues and not positive:
        return None, None

    if not issues:
        # Only positive condition detected — surface it as the primary
        return positive[0], None

    primary = issues[0]
    secondary = issues[1] if len(issues) > 1 else None
    return primary, secondary


# ---------------------------------------------------------------------------
# Spatial context sentence
# ---------------------------------------------------------------------------

def generate_spatial_context(
    cell_comparisons: dict[str, Any],
    cell: pd.Series,
) -> str:
    """Generate a concise spatial context sentence for a grid cell.

    Describes the cell's most notable characteristics relative to the rest
    of the city.  Uses only spatial rank comparisons — no planning advice.

    Parameters
    ----------
    cell_comparisons : dict
        Output of
        :func:`~environment.comparative_analysis.compute_cell_comparisons`.
    cell : pd.Series
        One row from the master GeoDataFrame (used for raw indicator values).

    Returns
    -------
    str
        A 1–2 sentence spatial context description.  Never empty.
    """
    lst_rank = cell_comparisons.get("city_rank_lst", 50.0)
    ndvi_rank = cell_comparisons.get("city_rank_ndvi", 50.0)
    lst_val = float(cell.get("mean_lst", 0.0) or 0.0)
    ndvi_val = float(cell.get("mean_ndvi", 0.0) or 0.0)

    # ── LST context ─────────────────────────────────────────────────────────
    placeholders = {
        "lst_rank": lst_rank,
        "lst_val": lst_val,
        "ndvi_rank": ndvi_rank,
        "ndvi_val": ndvi_val,
        # Convenience: "top X%" phrasing for vegetation
        "ndvi_pct": 100.0 - ndvi_rank,
    }

    if lst_rank >= 85:
        lst_template = SPATIAL_LST_TEMPLATES["very_high"]
    elif lst_rank >= 65:
        lst_template = SPATIAL_LST_TEMPLATES["high"]
    elif lst_rank <= 35:
        lst_template = SPATIAL_LST_TEMPLATES["low"]
    else:
        lst_template = SPATIAL_LST_TEMPLATES["average"]

    # ── NDVI context ────────────────────────────────────────────────────────
    # city_rank_ndvi: 100 = most vegetated; so LOW rank = low vegetation
    if ndvi_rank <= 15:
        ndvi_template = SPATIAL_NDVI_TEMPLATES["very_low"]
    elif ndvi_rank <= 40:
        ndvi_template = SPATIAL_NDVI_TEMPLATES["low"]
    elif ndvi_rank >= 70:
        ndvi_template = SPATIAL_NDVI_TEMPLATES["high"]
    else:
        ndvi_template = SPATIAL_NDVI_TEMPLATES["average"]

    try:
        lst_sentence = lst_template.format_map(placeholders)
        ndvi_sentence = ndvi_template.format_map(placeholders)
        context = f"This grid is {lst_sentence}. {ndvi_sentence}."
    except (KeyError, ValueError) as exc:
        logger.warning("Spatial context template fill failed: %s", exc)
        context = (
            f"Surface temperature is {lst_val:.1f}°C "
            f"and vegetation cover (NDVI) is {ndvi_val:.3f}."
        )

    return context
