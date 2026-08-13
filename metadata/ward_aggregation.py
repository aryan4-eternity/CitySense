"""
ward_aggregation.py
===================
Aggregates cell-level planning profiles and environmental intelligence
to ward-level summaries and writes data/ward_profiles.json.

WHY WARD LEVEL
--------------
The 1 km² grid is appropriate for city-wide risk identification and
comparative ranking. For planning recommendations to be actionable by
BMC ward officers, they must be expressed at the ward level — the
administrative unit at which budgets are allocated, projects sanctioned,
and staff assigned. This module rolls up cell-level outputs to 24 wards
without replacing the cell-level data.

AGGREGATION LOGIC
-----------------
For each ward (derived from geographic_metadata.json ward field):

  priority_score_mean    Arithmetic mean of all cells' priority_score.
  priority_score_max     Maximum priority_score among cells in the ward.
  dominant_intervention  Most frequent recommended_intervention across
                         cells, excluding "Environmental Monitoring"
                         (the default/no-condition intervention) when
                         at least one specific intervention is present.
  intervention_counts    Full frequency table of all interventions.
  dominant_issue         Most frequent primary_issue across cells.
  avg_ehi                Mean environmental_health across cells.
  avg_risk_score         Mean risk_score across cells.
  total_cells            Count of cells assigned to this ward.
  high_priority_cells    Count of cells with planning_priority in
                         {Critical, High}.
  priority_distribution  Counts per priority label.
  zone                   Administrative zone (City / Western Suburbs /
                         Eastern Suburbs) from geographic_metadata.
  ward_population        Estimated ward population from
                         geographic_config.yaml baselines.
  planning_summary       One-sentence human-readable summary of the
                         ward's dominant planning need.

Output: data/ward_profiles.json keyed by ward name.

Usage
-----
    python -m metadata.ward_aggregation    (from project root)
    python metadata/ward_aggregation.py
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent

sys.path.insert(0, str(_PROJECT_ROOT))
from config_loader import load_config, project_path

logger = logging.getLogger("CitySense.metadata.ward_aggregation")

# Priority labels ordered worst → best (for dominant label selection)
_PRIORITY_ORDER = ["Critical", "High", "Medium", "Low", "Very Low"]

# Intervention to skip as "dominant" when specific ones exist
_DEFAULT_INTERVENTION = "Environmental Monitoring"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path, label: str) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found at '{path}'")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _dominant_label(labels: list[str], order: list[str]) -> str:
    """Return the most severe priority label present in *labels*."""
    for label in order:
        if label in labels:
            return label
    return labels[0] if labels else "Unknown"


def _dominant_intervention(interventions: list[str]) -> str:
    """Most frequent non-default intervention; falls back to default."""
    specific = [i for i in interventions if i != _DEFAULT_INTERVENTION]
    if specific:
        return Counter(specific).most_common(1)[0][0]
    return _DEFAULT_INTERVENTION


def _build_planning_summary(
    ward: str,
    dominant_intervention: str,
    dominant_issue: str | None,
    avg_priority: float,
    high_cells: int,
    total_cells: int,
) -> str:
    """One-sentence planning summary for a ward."""
    issue_clause = f" driven by {dominant_issue}" if dominant_issue else ""
    urgency = (
        "requires urgent attention" if avg_priority >= 60
        else "warrants attention" if avg_priority >= 40
        else "has low planning urgency"
    )
    return (
        f"{ward} {urgency} (avg priority score {avg_priority:.0f}/100"
        f"{', ' + str(high_cells) + ' high-priority cells' if high_cells > 0 else ''}"
        f"): primary recommended intervention is {dominant_intervention}"
        f"{issue_clause}."
    )


# ---------------------------------------------------------------------------
# Core aggregation
# ---------------------------------------------------------------------------

def aggregate_to_wards(
    geo_meta: dict[str, dict],
    planning: dict[str, dict],
    env_intel: dict[str, dict],
    ward_populations: dict[str, int],
) -> dict[str, dict[str, Any]]:
    """Aggregate cell-level data to ward-level summaries.

    Parameters
    ----------
    geo_meta   : cell_id → {ward, zone, ...}
    planning   : cell_id → {priority_score, recommended_intervention, ...}
    env_intel  : cell_id → {environmental_health, primary_issue, ...}
    ward_populations : ward_name → estimated population

    Returns
    -------
    dict keyed by ward name, each value containing aggregated fields.
    """
    # Group cells by ward
    ward_cells: dict[str, list[str]] = {}
    for cell_id, meta in geo_meta.items():
        ward = meta.get("ward", "Unknown Ward")
        if ward not in ward_cells:
            ward_cells[ward] = []
        ward_cells[ward].append(cell_id)

    logger.info("Aggregating %d cells across %d wards …", len(geo_meta), len(ward_cells))

    ward_profiles: dict[str, dict[str, Any]] = {}

    for ward, cell_ids in sorted(ward_cells.items()):
        priority_scores:    list[float] = []
        interventions:      list[str]   = []
        issues:             list[str]   = []
        ehi_vals:           list[float] = []
        risk_vals:          list[float] = []
        priority_labels:    list[str]   = []
        zones:              list[str]   = []

        for cid in cell_ids:
            plan = planning.get(cid, {})
            ei   = env_intel.get(cid, {})
            meta = geo_meta.get(cid, {})

            ps = plan.get("priority_score")
            if ps is not None:
                priority_scores.append(float(ps))

            iv = plan.get("recommended_intervention")
            if iv:
                interventions.append(iv)

            pl = plan.get("planning_priority")
            if pl:
                priority_labels.append(pl)

            issue = ei.get("primary_issue")
            if issue:
                issues.append(issue)

            ehi = ei.get("environmental_health") or plan.get("environmental_health")
            if ehi is not None:
                ehi_vals.append(float(ehi))

            rs = plan.get("risk_score")
            if rs is not None:
                risk_vals.append(float(rs))

            zone = meta.get("zone")
            if zone:
                zones.append(zone)

        # Compute aggregates
        avg_priority = round(sum(priority_scores) / len(priority_scores), 1) if priority_scores else 0.0
        max_priority = round(max(priority_scores), 1) if priority_scores else 0.0
        avg_ehi      = round(sum(ehi_vals)      / len(ehi_vals),      1) if ehi_vals      else 0.0
        avg_risk     = round(sum(risk_vals)      / len(risk_vals),     1) if risk_vals      else 0.0

        intervention_counts = dict(Counter(interventions).most_common())
        issue_counts        = dict(Counter(issues).most_common())

        dom_intervention = _dominant_intervention(interventions)
        dom_issue        = Counter(issues).most_common(1)[0][0] if issues else None
        dom_priority     = _dominant_label(priority_labels, _PRIORITY_ORDER) if priority_labels else "Unknown"
        zone             = Counter(zones).most_common(1)[0][0] if zones else "Unknown"

        high_cells = sum(
            1 for lbl in priority_labels if lbl in ("Critical", "High")
        )

        priority_dist = {
            lbl: priority_labels.count(lbl) for lbl in _PRIORITY_ORDER
            if lbl in priority_labels
        }

        # Ward population from config baseline
        pop_key = ward if ward in ward_populations else ward.replace(" Ward", "") + " Ward"
        population = ward_populations.get(pop_key, ward_populations.get(ward, 0))

        summary = _build_planning_summary(
            ward, dom_intervention, dom_issue, avg_priority, high_cells, len(cell_ids)
        )

        ward_profiles[ward] = {
            "ward":                    ward,
            "zone":                    zone,
            "ward_population":         population,
            "total_cells":             len(cell_ids),
            "high_priority_cells":     high_cells,
            "dominant_priority":       dom_priority,
            "priority_score_mean":     avg_priority,
            "priority_score_max":      max_priority,
            "priority_distribution":   priority_dist,
            "dominant_intervention":   dom_intervention,
            "intervention_counts":     intervention_counts,
            "dominant_issue":          dom_issue,
            "issue_counts":            issue_counts,
            "avg_ehi":                 avg_ehi,
            "avg_risk_score":          avg_risk,
            "planning_summary":        summary,
        }

        logger.debug(
            "  %-22s  cells=%3d  avg_priority=%5.1f  dominant=%s",
            ward, len(cell_ids), avg_priority, dom_intervention,
        )

    return ward_profiles


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Aggregate cell-level planning data to wards and write JSON output."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("=== CitySense — Ward-Level Planning Aggregation ===")

    cfg = load_config()

    geo_meta_path = project_path(cfg, "geographic_metadata")
    planning_path = project_path(cfg, "planning_profiles")
    ei_path       = project_path(cfg, "environmental_intelligence")
    geo_cfg_path  = _PROJECT_ROOT / cfg["output_paths"]["geographic_config"]
    output_path   = _PROJECT_ROOT / "data" / "ward_profiles.json"

    # Load inputs
    geo_meta = _load_json(geo_meta_path, "Geographic metadata")
    planning = _load_json(planning_path, "Planning profiles")
    env_intel = _load_json(ei_path, "Environmental intelligence") if ei_path.exists() else {}

    # Load ward population baselines from geographic_config.yaml
    with geo_cfg_path.open("r", encoding="utf-8") as f:
        geo_cfg = yaml.safe_load(f)
    ward_populations: dict[str, int] = geo_cfg.get("geographic", {}).get("ward_population", {})
    logger.info("Loaded population baselines for %d wards.", len(ward_populations))

    # Aggregate
    ward_profiles = aggregate_to_wards(geo_meta, planning, env_intel, ward_populations)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(ward_profiles, f, indent=2, ensure_ascii=False)

    logger.info("Wrote ward profiles for %d wards → %s", len(ward_profiles), output_path)

    # Summary log
    logger.info("Ward summary (sorted by avg priority score desc):")
    sorted_wards = sorted(
        ward_profiles.items(),
        key=lambda x: x[1]["priority_score_mean"],
        reverse=True,
    )
    for ward, profile in sorted_wards:
        logger.info(
            "  %-22s  cells=%3d  avg_pri=%5.1f  dominant_iv=%-40s  pop=%s",
            ward,
            profile["total_cells"],
            profile["priority_score_mean"],
            profile["dominant_intervention"],
            f"{profile['ward_population']:,}" if profile["ward_population"] else "—",
        )

    logger.info("=== Ward aggregation complete! ===")


if __name__ == "__main__":
    main()
