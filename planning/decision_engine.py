"""
decision_engine.py
==================
Top-level orchestrator for Phase 3.

Runs all planning modules over the full dataset and returns a dict of
Planning Profiles keyed by cell_id.  This is the single entry point
called by the pipeline stage.

Public API
----------
run(gdf, env_intel, geo_meta, explanations)  → dict[str, dict]
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd
import geopandas as gpd

from planning.priority_engine import compute_priority_batch, get_priority_label
from planning.intervention_engine import (
    select_intervention,
    compute_confidence,
    build_evidence_text,
)
from planning.planning_summary import build_planning_profile

logger = logging.getLogger("CitySense.planning.decision_engine")

# The 5 core indicators used to assess data completeness for confidence scoring
_CORE_INDICATORS: tuple[str, ...] = (
    "mean_lst", "mean_ndvi", "mean_ndbi", "mean_dem", "uhi_intensity",
)


def run(
    gdf: gpd.GeoDataFrame,
    env_intel: dict[str, dict[str, Any]],
    geo_meta: dict[str, dict[str, Any]],
    explanations: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Compute Planning Profiles for every cell in *gdf*.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Master dataset (must contain at least ``cell_id``, ``risk_score``,
        ``top_positive_driver``, ``top_positive_shap``).
    env_intel : dict
        Phase 2 environmental intelligence keyed by ``cell_id``.
    geo_meta : dict
        Geographic metadata keyed by ``cell_id`` (may be ``{}``).
    explanations : dict
        SHAP explanation records keyed by ``cell_id`` (may be ``{}``).

    Returns
    -------
    dict[str, dict]
        Planning Profiles keyed by ``cell_id``.
    """
    logger.info("Decision engine: processing %d cells …", len(gdf))

    # ── 1. City-wide SHAP max (for confidence normalisation) ──────────────
    city_max_shap = _compute_city_max_shap(gdf)
    logger.debug("City-wide max |SHAP| = %.4f", city_max_shap)

    # ── 2. Batch priority scores ──────────────────────────────────────────
    priority_df = compute_priority_batch(gdf, env_intel, geo_meta)
    priority_lookup: dict[str, tuple[float, str]] = {
        row["cell_id"]: (row["priority_score"], row["planning_priority"])
        for _, row in priority_df.iterrows()
    }

    # ── 3. Per-cell loop ──────────────────────────────────────────────────
    profiles: dict[str, dict[str, Any]] = {}

    for _, row in gdf.iterrows():
        cell_id = str(row.get("cell_id", row.name))

        # Environmental intelligence (Phase 2)
        ei = env_intel.get(cell_id, {})
        ehi        = float(ei.get("environmental_health", 50.0) or 50.0)
        risk_score = float(row.get("risk_score", 50.0) or 50.0)
        conditions: list[str] = ei.get("detected_conditions", [])
        primary_issue: str | None = ei.get("primary_issue")
        cell_comparisons: dict[str, Any] = {
            k: ei.get(k) for k in ei if k.startswith("city_rank_")
        }

        # Priority (from batch)
        priority_score, priority_label = priority_lookup.get(
            cell_id, (50.0, "Medium")
        )

        # SHAP data
        top_driver = _safe_str(row.get("top_positive_driver"))
        top_shap   = _safe_float(row.get("top_positive_shap"), 0.0)

        # Data completeness
        n_present = sum(
            1 for ind in _CORE_INDICATORS
            if _is_present(row.get(ind))
        )

        # Intervention selection
        intervention = select_intervention(conditions, primary_issue)

        # Confidence
        confidence = compute_confidence(
            top_positive_shap=top_shap,
            city_max_shap=city_max_shap,
            n_conditions=len(conditions),
            n_indicators_present=n_present,
        )

        # Evidence text
        evidence = build_evidence_text(
            primary_issue=primary_issue,
            cell_comparisons=cell_comparisons,
            top_positive_driver=top_driver,
            top_positive_shap=top_shap,
            intervention_name=intervention["primary"],
        )

        # Assemble profile
        profile = build_planning_profile(
            cell_id=cell_id,
            ehi=ehi,
            risk_score=risk_score,
            priority_score=priority_score,
            priority_label=priority_label,
            intervention=intervention,
            confidence=confidence,
            evidence_text=evidence,
        )
        profiles[cell_id] = profile

    logger.info("Decision engine complete: %d profiles generated.", len(profiles))
    return profiles


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_city_max_shap(gdf: gpd.GeoDataFrame) -> float:
    """Return the city-wide maximum absolute SHAP value.

    Falls back to 1.0 so confidence calculations remain well-defined even
    if the column is absent or all-zero.
    """
    if "top_positive_shap" not in gdf.columns:
        return 1.0
    series = gdf["top_positive_shap"].dropna().abs()
    if series.empty or series.max() == 0.0:
        return 1.0
    return float(series.max())


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce *value* to float; return *default* on failure or NaN."""
    if value is None:
        return default
    try:
        f = float(value)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any) -> str | None:
    """Return str(*value*) or None if value is None/NaN/empty."""
    if value is None:
        return None
    s = str(value).strip()
    if s.lower() in ("nan", "none", ""):
        return None
    return s


def _is_present(value: Any) -> bool:
    """Return True if *value* is a non-None, non-NaN number."""
    if value is None:
        return False
    try:
        return not math.isnan(float(value))
    except (TypeError, ValueError):
        return False
