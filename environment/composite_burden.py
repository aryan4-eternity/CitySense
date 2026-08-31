"""
composite_burden.py
====================
Computes the Environmental Burden + Access Gap composite score —
a "double disadvantage" index that identifies cells with BOTH poor
environmental health (high EHI deficit) AND poor infrastructure access
(low IAI).

FORMULA
-------
    burden_score = 0.50 × (100 - ehi)   +   0.50 × (100 - iai)

Where:
    (100 - ehi) = environmental health deficit (higher = worse environment)
    (100 - iai) = infrastructure access deficit (higher = worse access)

Higher burden_score = area faces both environmental degradation AND
limited infrastructure access. These are the cells that should be
highest priority for integrated urban investment.

FRAMING
--------
The composite is presented as "Environmental Burden + Access Gap" —
an objective planning indicator. Status labels describe conditions,
not communities:
    Critical (75–100) : Severe combined burden
    High     (50–74)  : High combined burden
    Moderate (25–49)  : Moderate combined burden
    Low      (0–24)   : Low combined burden

PUBLIC API
----------
compute_burden_batch(ehi_series, iai_series) → pd.Series
get_burden_status(score) → str
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
import sys

import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger("CitySense.environment.composite_burden")

BURDEN_STATUS_THRESHOLDS: list[tuple[float, float, str]] = [
    (75.0, 100.0, "Critical"),
    (50.0,  74.9, "High"),
    (25.0,  49.9, "Moderate"),
    (0.0,   24.9, "Low"),
]


def compute_burden_batch(
    ehi_series: pd.Series,
    iai_series: pd.Series,
) -> pd.Series:
    """Compute combined burden score for all cells. Both series must share the same index."""
    ehi_deficit = 100.0 - ehi_series.fillna(50.0).clip(0, 100)
    iai_deficit = 100.0 - iai_series.fillna(50.0).clip(0, 100)
    burden = (0.50 * ehi_deficit + 0.50 * iai_deficit).clip(0, 100)
    logger.debug("Burden: min=%.1f  max=%.1f  mean=%.1f",
                 burden.min(), burden.max(), burden.mean())
    return burden


def get_burden_status(score: float) -> str:
    for low, high, label in BURDEN_STATUS_THRESHOLDS:
        if low <= score <= high:
            return label
    return "Low"


def main() -> None:
    """Generate composite_burden.json from existing IAI and EHI outputs."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("=== CitySense — Generate Composite Burden Score ===")
    t0 = time.time()

    from config_loader import load_config, project_path

    cfg     = load_config()
    ei_path = _PROJECT_ROOT / "data" / "environmental_intelligence.json"
    iai_path= _PROJECT_ROOT / "data" / "infrastructure_access_index.json"
    out_path= _PROJECT_ROOT / "data" / "composite_burden.json"

    for p, label in [(ei_path, "environmental_intelligence.json"),
                     (iai_path, "infrastructure_access_index.json")]:
        if not p.exists():
            logger.error("%s not found. Run upstream stages first.", label)
            return

    with ei_path.open(encoding="utf-8") as f:
        ei_data = json.load(f)
    with iai_path.open(encoding="utf-8") as f:
        iai_data = json.load(f)

    cell_ids = list(ei_data.keys())
    ehi_vals = pd.Series(
        {cid: ei_data[cid].get("environmental_health", 50.0) for cid in cell_ids}
    )
    iai_vals = pd.Series(
        {cid: iai_data.get(cid, {}).get("iai_score", 50.0) for cid in cell_ids}
    )

    burden = compute_burden_batch(ehi_vals, iai_vals)

    output: dict[str, dict] = {}
    from collections import Counter
    status_counter: Counter = Counter()

    for cid in cell_ids:
        score  = float(burden.get(cid, 50.0))
        status = get_burden_status(score)
        ehi    = float(ei_data[cid].get("environmental_health", 50.0))
        iai    = float(iai_data.get(cid, {}).get("iai_score", 50.0))
        ei_status  = ei_data[cid].get("environmental_status", "Moderate")
        iai_status = iai_data.get(cid, {}).get("iai_status", "Moderate")
        output[cid] = {
            "burden_score":        round(score, 2),
            "burden_status":       status,
            "ehi_component":       round(100.0 - ehi, 2),
            "iai_deficit":         round(100.0 - iai, 2),
            "environmental_status": ei_status,
            "iai_status":          iai_status,
        }
        status_counter[status] += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info("Wrote burden scores for %d cells -> %s (%.2fs)",
                len(output), out_path, time.time() - t0)
    for label in ["Critical", "High", "Moderate", "Low"]:
        count = status_counter.get(label, 0)
        logger.info("  %-10s : %4d cells  (%.1f%%)", label, count,
                    count / len(output) * 100 if output else 0)
    logger.info("=== Composite burden complete! ===")


if __name__ == "__main__":
    main()
