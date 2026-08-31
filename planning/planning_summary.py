"""
planning_summary.py
===================
Assembles the final Planning Profile dict for a single grid cell by
combining all computed Phase 3 components into a consistent, typed
output record.

Public API
----------
build_planning_profile(...)   → dict   (11-key Planning Profile)
get_priority_color(label)     → str    (Streamlit widget type)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("CitySense.planning.planning_summary")

# ---------------------------------------------------------------------------
# Priority → Streamlit colour mapping
# ---------------------------------------------------------------------------
_PRIORITY_COLORS: dict[str, str] = {
    "Critical": "error",    # st.error   → red
    "High":     "error",
    "Medium":   "warning",  # st.warning → amber
    "Low":      "success",  # st.success → green
    "Very Low": "success",
}

# All 11 required keys in the Planning Profile output record
_REQUIRED_KEYS: tuple[str, ...] = (
    "planning_priority",
    "priority_score",
    "primary_objective",
    "recommended_intervention",
    "secondary_interventions",
    "expected_benefits",
    "implementation_cost",
    "implementation_timeline",
    "implementation_complexity",
    "confidence",
    "evidence",
)


def build_planning_profile(
    cell_id: str,
    ehi: float,
    risk_score: float,
    priority_score: float,
    priority_label: str,
    intervention: dict[str, Any],
    confidence: float,
    evidence_text: str,
) -> dict[str, Any]:
    """Assemble the complete Planning Profile for a single grid cell.

    Parameters
    ----------
    cell_id : str
        Grid cell identifier (used only for logging).
    ehi : float
        Environmental Health Index (0–100) — stored for downstream use.
    risk_score : float
        PCA risk score (0–100) — stored for downstream use.
    priority_score : float
        Planning Priority Score (0–100).
    priority_label : str
        Priority label (e.g. ``"Critical"``).
    intervention : dict
        Catalog entry returned by
        :func:`~planning.intervention_engine.select_intervention`.
    confidence : float
        Recommendation confidence score (0.0–1.0).
    evidence_text : str
        "Why this recommendation?" explanation paragraph.

    Returns
    -------
    dict
        Planning Profile with exactly the 11 standard keys plus two
        supplementary fields (``environmental_health``, ``risk_score``)
        for Phase 4 consumers.
    """
    # Primary objective is the first item in the objectives list
    objectives: list[str] = intervention.get("objectives", [])
    primary_objective = objectives[0] if objectives else "Environmental Management"

    profile: dict[str, Any] = {
        # Core planning fields (11 required keys)
        "planning_priority":          priority_label,
        "priority_score":             round(float(priority_score), 1),
        "primary_objective":          primary_objective,
        "recommended_intervention":   str(intervention.get("primary", "Environmental Monitoring")),
        "secondary_interventions":    list(intervention.get("secondary", [])),
        "expected_benefits":          list(intervention.get("benefits", [])),
        "implementation_cost":        str(intervention.get("cost", "Unknown")),
        "implementation_timeline":    str(intervention.get("timeline", "Unknown")),
        "implementation_complexity":  str(intervention.get("complexity", "Unknown")),
        "confidence":                 round(float(confidence), 3),
        "evidence":                   str(evidence_text),
        # Supplementary fields for Phase 4 consumers
        "environmental_health":       round(float(ehi), 2),
        "risk_score":                 round(float(risk_score), 2),
    }

    # Defensive check — log a warning if any required key is accidentally missing
    missing = [k for k in _REQUIRED_KEYS if k not in profile]
    if missing:
        logger.warning(
            "Planning profile for cell '%s' is missing keys: %s", cell_id, missing
        )

    return profile


def get_priority_color(priority_label: str) -> str:
    """Return the Streamlit widget type for a planning priority label.

    Parameters
    ----------
    priority_label : str
        One of: ``"Critical"``, ``"High"``, ``"Medium"``, ``"Low"``,
        ``"Very Low"``.

    Returns
    -------
    str
        One of: ``"error"``, ``"warning"``, ``"success"``.
        Defaults to ``"warning"`` for unknown labels.
    """
    return _PRIORITY_COLORS.get(priority_label, "warning")


def get_required_keys() -> tuple[str, ...]:
    """Return the tuple of required Planning Profile keys (read-only).

    Useful for tests and validation.
    """
    return _REQUIRED_KEYS
