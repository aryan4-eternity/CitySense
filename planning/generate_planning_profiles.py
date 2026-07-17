"""
generate_planning_profiles.py
==============================
Pipeline stage: orchestrates the Phase 3 Planning Decision Engine and
writes ``data/planning_profiles.json``.

This stage is READ-ONLY with respect to ``cells_master.geojson`` and all
Phase 2 JSON files.

Dependencies (must exist before this stage runs)
-------------------------------------------------
    data/cells_master.geojson          – master dataset with SHAP columns
    data/environmental_intelligence.json – Phase 2 output

Optional inputs (gracefully absent)
------------------------------------
    data/geo/geographic_metadata.json  – population & land-use enrichment
    data/cell_explanations.json        – SHAP explanation text

Output
------
    data/planning_profiles.json

Usage
-----
    python -m planning.generate_planning_profiles   (from project root)
    python planning/generate_planning_profiles.py
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import Counter
from pathlib import Path

import geopandas as gpd

from config_loader import load_config, project_path
from planning.decision_engine import run as decision_engine_run

logger = logging.getLogger("CitySense.planning.generate_planning_profiles")

_REQUIRED_FILES = ["master_data", "environmental_intelligence"]


def _load_json(path: Path, label: str) -> dict:
    """Load a JSON file; return {} if path does not exist."""
    if not path.exists():
        logger.warning("%s not found at '%s' — proceeding without it.", label, path)
        return {}
    with open(str(path), "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    """Compute planning profiles for all cells and write JSON output."""
    logger.info("=== City Sense – Phase 3: Generate Planning Profiles ===")
    t_start = time.time()

    # ── 1. Load config and resolve paths ─────────────────────────────────
    cfg = load_config()

    master_path   = project_path(cfg, "master_data")
    ei_path       = project_path(cfg, "environmental_intelligence")
    geo_meta_path = project_path(cfg, "geographic_metadata")
    explain_path  = project_path(cfg, "explanations")
    output_path   = project_path(cfg, "planning_profiles")

    logger.info("Master dataset            : %s", master_path)
    logger.info("Environmental intelligence: %s", ei_path)
    logger.info("Output path               : %s", output_path)

    # ── 2. Validate required inputs ───────────────────────────────────────
    for key in _REQUIRED_FILES:
        p = project_path(cfg, key)
        if not p.exists():
            logger.error(
                "Required input '%s' not found at '%s'. "
                "Run all upstream pipeline stages first.",
                key, p,
            )
            return

    # ── 3. Load all inputs ────────────────────────────────────────────────
    logger.info("Loading master dataset …")
    gdf = gpd.read_file(str(master_path))
    logger.info("Loaded %d cells.", len(gdf))

    env_intel  = _load_json(ei_path,       "Environmental intelligence")
    geo_meta   = _load_json(geo_meta_path, "Geographic metadata")
    explanations = _load_json(explain_path, "Cell explanations")

    logger.info(
        "Inputs: env_intel=%d  geo_meta=%d  explanations=%d",
        len(env_intel), len(geo_meta), len(explanations),
    )

    # ── 4. Run decision engine ────────────────────────────────────────────
    profiles = decision_engine_run(
        gdf=gdf,
        env_intel=env_intel,
        geo_meta=geo_meta,
        explanations=explanations,
    )

    # ── 5. Write output JSON ──────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(output_path), "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - t_start
    logger.info(
        "Wrote planning profiles for %d cells → %s (%.2fs)",
        len(profiles), output_path, elapsed,
    )

    # ── 6. Summary statistics ─────────────────────────────────────────────
    priority_counter: Counter = Counter()
    intervention_counter: Counter = Counter()

    for profile in profiles.values():
        priority_counter[profile.get("planning_priority", "Unknown")] += 1
        intervention_counter[profile.get("recommended_intervention", "Unknown")] += 1

    logger.info("Planning Priority distribution:")
    for label in ["Critical", "High", "Medium", "Low", "Very Low"]:
        count = priority_counter.get(label, 0)
        pct = count / len(profiles) * 100 if profiles else 0
        logger.info("  %-10s : %4d cells  (%.1f%%)", label, count, pct)

    logger.info("Top 5 recommended interventions:")
    for intervention, count in intervention_counter.most_common(5):
        logger.info("  %-45s : %d cells", intervention, count)

    logger.info("=== Planning Profiles generation complete! ===")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from utils import setup_logging
    setup_logging()
    main()
