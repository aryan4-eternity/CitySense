"""
environmental_summary.py
========================
Composes the final human-readable Environmental Summary paragraph for a
grid cell using deterministic templates.  No LLM is used.

Template selection logic
------------------------
1. Try exact match on ``(primary_condition, status_tier)``.
2. Try match on ``(primary_condition, next-worse status_tier)``.
3. Fall back to ``SUMMARY_FALLBACK_TEMPLATE``.

All generated strings are validated to contain no unfilled ``{placeholder}``
tokens before being returned.

Public API
----------
generate_summary(cell, ehi, status, conditions, cell_comparisons)
    → str
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

from environment.environment_templates import (
    SUMMARY_FALLBACK_TEMPLATE,
    SUMMARY_TEMPLATES,
)

logger = logging.getLogger("CitySense.environment.environmental_summary")

# Status tiers ordered from best to worst (used for fallback tier search)
_STATUS_TIERS: list[str] = ["Excellent", "Good", "Moderate", "Poor", "Critical"]

# Regex that detects any remaining unfilled placeholder token
_PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")


def _build_placeholder_dict(
    cell: pd.Series,
    ehi: float,
    status: str,
    conditions: list[str],
    cell_comparisons: dict[str, Any],
) -> dict[str, Any]:
    """Collect all values that may appear in summary templates.

    Returns a flat dict with every placeholder key defined in
    ``environment_templates.SUMMARY_TEMPLATES`` docstring, using safe
    defaults (0.0 / "Unknown") when a value is missing.
    """
    def _safe_float(val: Any, default: float = 0.0) -> float:
        try:
            f = float(val)
            return f if f == f else default   # NaN check
        except (TypeError, ValueError):
            return default

    return {
        # Core scores
        "ehi":       ehi,
        "status":    status,
        # Raw indicator values
        "lst_val":   _safe_float(cell.get("mean_lst"),       30.0),
        "ndvi_val":  _safe_float(cell.get("mean_ndvi"),       0.2),
        "ndbi_val":  _safe_float(cell.get("mean_ndbi"),       0.2),
        "uhi_val":   _safe_float(cell.get("uhi_intensity"),   0.0),
        "dem_val":   _safe_float(cell.get("mean_dem"),        5.0),
        # City rank values  (percentile 0–100)
        "lst_rank":  _safe_float(cell_comparisons.get("city_rank_lst"),  50.0),
        "ndvi_rank": _safe_float(cell_comparisons.get("city_rank_ndvi"), 50.0),
        "ndbi_rank": _safe_float(cell_comparisons.get("city_rank_ndbi"), 50.0),
        "uhi_rank":  _safe_float(cell_comparisons.get("city_rank_uhi",
                                  cell_comparisons.get("city_rank_uhi_intensity", 50.0))),
        "dem_rank":  _safe_float(cell_comparisons.get("city_rank_dem"),  50.0),
        "risk_rank": _safe_float(cell_comparisons.get("city_rank_risk",
                                  cell_comparisons.get("city_rank_risk_score", 50.0))),
        # Locality (used in a few templates)
        "locality":  str(cell.get("primary_locality", "this area")),
        # Conditions list (for generic fallback)
        "primary_issue":   conditions[0] if conditions else "General Stress",
    }


def _fill_template(template: str, placeholders: dict[str, Any]) -> str | None:
    """Fill *template* with *placeholders* using str.format_map.

    Returns the filled string if all placeholders were resolved, or
    ``None`` if any placeholder remained unfilled.
    """
    try:
        filled = template.format_map(placeholders)
    except (KeyError, ValueError):
        return None

    # Verify no raw {placeholder} tokens remain
    if _PLACEHOLDER_RE.search(filled):
        return None

    return filled


def generate_summary(
    cell: pd.Series,
    ehi: float,
    status: str,
    conditions: list[str],
    cell_comparisons: dict[str, Any],
) -> str:
    """Generate a 2–3 sentence environmental summary paragraph.

    Template selection precedence
    ------------------------------
    1. Exact ``(primary_condition, status)`` match in SUMMARY_TEMPLATES.
    2. Same condition with the next-worse status tier.
    3. ``("Environmental Stress", status)`` if EHI < 50.
    4. ``SUMMARY_FALLBACK_TEMPLATE``.

    Parameters
    ----------
    cell : pd.Series
        One row from the master GeoDataFrame.
    ehi : float
        Environmental Health Index (0–100).
    status : str
        Environmental status label (e.g. "Moderate").
    conditions : list[str]
        Output of
        :func:`~environment.indicator_interpreter.detect_conditions`.
    cell_comparisons : dict
        Output of
        :func:`~environment.comparative_analysis.compute_cell_comparisons`.

    Returns
    -------
    str
        A complete, grammatically correct summary paragraph.  Never
        contains unfilled ``{placeholder}`` tokens.
    """
    placeholders = _build_placeholder_dict(
        cell, ehi, status, conditions, cell_comparisons
    )

    primary = conditions[0] if conditions else None

    # ── 1. Exact match ───────────────────────────────────────────────────────
    if primary is not None:
        template = SUMMARY_TEMPLATES.get((primary, status))
        if template:
            result = _fill_template(template, placeholders)
            if result:
                return result

    # ── 2. Fallback to next-worse status tier ────────────────────────────────
    if primary is not None:
        current_tier_idx = _STATUS_TIERS.index(status) if status in _STATUS_TIERS else -1
        for worse_tier in _STATUS_TIERS[current_tier_idx + 1:]:
            template = SUMMARY_TEMPLATES.get((primary, worse_tier))
            if template:
                result = _fill_template(template, placeholders)
                if result:
                    logger.debug(
                        "Used fallback tier '%s' for condition '%s' (cell status: %s).",
                        worse_tier, primary, status,
                    )
                    return result

    # ── 3. Environmental Stress catch-all for low-EHI cells ─────────────────
    if ehi < 50.0:
        stress_status = "Poor" if ehi < 40.0 else "Moderate"
        template = SUMMARY_TEMPLATES.get(("Environmental Stress", stress_status))
        if template:
            result = _fill_template(template, placeholders)
            if result:
                return result

    # ── 4. Universal fallback ────────────────────────────────────────────────
    result = _fill_template(SUMMARY_FALLBACK_TEMPLATE, placeholders)
    if result:
        logger.debug("Used fallback summary template for cell '%s'.", cell.get("cell_id", "?"))
        return result

    # Last-resort: plain text (should never be reached)
    logger.warning(
        "All summary templates failed for cell '%s'; using plain text.",
        cell.get("cell_id", "?"),
    )
    return (
        f"This grid has {status} environmental health (EHI: {ehi:.0f}/100). "
        f"Surface temperature is {placeholders['lst_val']:.1f}\u00b0C "
        f"and vegetation cover (NDVI) is {placeholders['ndvi_val']:.3f}."
    )
