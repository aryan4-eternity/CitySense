"""
knowledge_base.py
=================
Loads the intervention catalog YAML and exposes a clean API for resolving
the best intervention for a given set of detected environmental conditions.

All functions are pure (no side effects, no file I/O after initial load).
The catalog is loaded once per process and cached at module level.

Public API
----------
load_catalog()                    → dict  (full parsed YAML)
get_intervention(conditions)      → dict  (best matching catalog entry)
get_strategic_weight(land_use)    → float (0–100 strategic importance)
list_all_interventions()          → list[str]
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("CitySense.planning.knowledge_base")

# ---------------------------------------------------------------------------
# Catalog path (relative to this file)
# ---------------------------------------------------------------------------
_CATALOG_PATH = Path(__file__).resolve().parent / "intervention_catalog.yaml"

# Module-level cache — loaded once per process
_catalog_cache: dict[str, Any] | None = None

# ---------------------------------------------------------------------------
# Strategic importance weights by dominant land use
# ---------------------------------------------------------------------------
# Values 0–100; higher = more important to intervene.
_STRATEGIC_WEIGHTS: dict[str, float] = {
    "Dense Commercial / Industrial": 90.0,
    "Residential":                   80.0,
    "Mixed Urban":                   70.0,
    "Mixed Residential":             60.0,
    "Sparse Vegetation / Open Land": 40.0,
    "Green Space / Forest":          30.0,
    "Water Body / Coastal":          10.0,
    "Unknown":                       50.0,
}

# Required keys that every catalog entry must contain
_REQUIRED_ENTRY_KEYS: frozenset[str] = frozenset({
    "primary", "secondary", "objectives",
    "benefits", "cost", "timeline", "complexity",
})


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------

def load_catalog(path: Path = _CATALOG_PATH) -> dict[str, Any]:
    """Load and return the intervention catalog.

    The result is cached after the first call so subsequent calls are free.

    Parameters
    ----------
    path : Path
        Path to ``intervention_catalog.yaml``.  Defaults to the bundled file
        inside the ``planning/`` package directory.

    Returns
    -------
    dict
        Parsed YAML document.  Top-level keys are ``interventions`` and
        ``multi_condition_overrides``.
    """
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache

    if not path.exists():
        raise FileNotFoundError(
            f"Intervention catalog not found at '{path}'. "
            "Ensure planning/intervention_catalog.yaml is present."
        )

    with path.open("r", encoding="utf-8") as f:
        catalog = yaml.safe_load(f)

    if not isinstance(catalog, dict):
        raise ValueError("intervention_catalog.yaml must contain a YAML mapping.")

    _catalog_cache = catalog
    logger.debug("Intervention catalog loaded from %s", path)
    return _catalog_cache


def _clear_cache() -> None:
    """Clear the module-level cache.  Used in tests that supply custom paths."""
    global _catalog_cache
    _catalog_cache = None


# ---------------------------------------------------------------------------
# Intervention resolution
# ---------------------------------------------------------------------------

def get_intervention(
    conditions: list[str],
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the best matching intervention entry for the given conditions.

    Resolution order
    ----------------
    1. **Multi-condition overrides** — find the override whose ``conditions``
       set is the largest subset of *conditions* (most-specific match wins).
       Overrides are ordered in the YAML from most- to least-specific so the
       first full-subset match is returned.
    2. **Single-condition lookup** — use the first detected condition that has
       a direct entry under ``interventions:``.
    3. **Default entry** — ``interventions.default``.

    Parameters
    ----------
    conditions : list[str]
        Ordered list of detected environmental conditions from Phase 2
        (e.g. ``["Urban Heat Island", "Low Vegetation"]``).
    catalog : dict, optional
        Pre-loaded catalog dict.  If omitted, the cached catalog is used.

    Returns
    -------
    dict
        A catalog entry dict with keys: ``primary``, ``secondary``,
        ``objectives``, ``benefits``, ``cost``, ``timeline``, ``complexity``.
        Never returns ``None``.
    """
    if catalog is None:
        catalog = load_catalog()

    interventions: dict = catalog.get("interventions", {})
    overrides: list[dict] = catalog.get("multi_condition_overrides", [])
    conditions_set = set(conditions)

    # ── 1. Multi-condition overrides ────────────────────────────────────────
    best_override: dict | None = None
    best_match_size: int = 0

    for override in overrides:
        override_conditions = set(override.get("conditions", []))
        if len(override_conditions) < 2:
            continue  # safety: skip malformed entries
        if override_conditions.issubset(conditions_set):
            match_size = len(override_conditions)
            if match_size > best_match_size:
                best_match_size = match_size
                best_override = override

    if best_override is not None:
        logger.debug(
            "Multi-condition override matched (%d conditions): %s",
            best_match_size,
            best_override.get("primary"),
        )
        return _clean_entry(best_override)

    # ── 2. Single-condition lookup ───────────────────────────────────────────
    for condition in conditions:
        if condition in interventions and condition != "default":
            logger.debug("Single-condition match: '%s'", condition)
            return _clean_entry(interventions[condition])

    # ── 3. Default ──────────────────────────────────────────────────────────
    logger.debug("No condition match; using default intervention.")
    return _clean_entry(interventions.get("default", _fallback_default()))


def _clean_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *entry* with only the standard fields, safe defaults added."""
    fallback = _fallback_default()
    return {
        "primary":    entry.get("primary",    fallback["primary"]),
        "secondary":  list(entry.get("secondary",  fallback["secondary"])),
        "objectives": list(entry.get("objectives", fallback["objectives"])),
        "benefits":   list(entry.get("benefits",   fallback["benefits"])),
        "cost":       entry.get("cost",       fallback["cost"]),
        "timeline":   entry.get("timeline",   fallback["timeline"]),
        "complexity": entry.get("complexity", fallback["complexity"]),
    }


def _fallback_default() -> dict[str, Any]:
    """Hardcoded default used only if catalog is entirely missing."""
    return {
        "primary":    "Environmental Monitoring",
        "secondary":  ["Baseline Assessment", "Indicator Tracking"],
        "objectives": ["Baseline Environmental Management"],
        "benefits":   ["Improved Data Quality", "Early Warning Capability"],
        "cost":       "Low",
        "timeline":   "Ongoing",
        "complexity": "Easy",
    }


# ---------------------------------------------------------------------------
# Strategic weight
# ---------------------------------------------------------------------------

def get_strategic_weight(dominant_land_use: str | None) -> float:
    """Return the strategic importance weight (0–100) for a land use type.

    Parameters
    ----------
    dominant_land_use : str or None
        Value from ``geographic_metadata.json`` ``dominant_land_use`` field.

    Returns
    -------
    float
        Weight in [0, 100].  Unknown or None land uses return 50.0.
    """
    if not dominant_land_use:
        return _STRATEGIC_WEIGHTS["Unknown"]
    return _STRATEGIC_WEIGHTS.get(dominant_land_use, _STRATEGIC_WEIGHTS["Unknown"])


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def list_all_interventions(catalog: dict[str, Any] | None = None) -> list[str]:
    """Return all primary intervention names from the catalog.

    Includes both single-condition entries and multi-condition overrides.
    Excludes the ``default`` entry.
    """
    if catalog is None:
        catalog = load_catalog()

    names: list[str] = []
    for key, entry in catalog.get("interventions", {}).items():
        if key != "default" and isinstance(entry, dict):
            names.append(entry.get("primary", key))

    for override in catalog.get("multi_condition_overrides", []):
        if isinstance(override, dict):
            primary = override.get("primary")
            if primary and primary not in names:
                names.append(primary)

    return names
