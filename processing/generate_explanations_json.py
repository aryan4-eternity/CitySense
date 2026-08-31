"""
generate_explanations_json.py
=============================
Extracts indicator attribution columns (top contributors, SHAP values,
attribution text) from data/cells_master.geojson and saves them into a
lightweight JSON file (data/cell_explanations.json).

WHAT THIS FILE CONTAINS
-----------------------
For each grid cell, the JSON records which raw indicator most strongly
*drives* the cell's composite risk index score upward (top_positive_driver)
and which most strongly *suppresses* it (top_negative_driver), along with
the SHAP magnitude and a human-readable attribution sentence.

These are index-decomposition values — they describe how the PCA composite
is constituted for each cell, not independent causal drivers of real-world
urban risk. See processing/train_explainability.py for the full scope note.

This JSON is loaded by the React dashboard (via the FastAPI /api/cell/:id
endpoint) to display per-cell indicator attribution without loading the
full GeoJSON into memory.

Format:
{
    "r0_c14": {
        "explanation_text": "High composite risk index — dominated by high LST (+11.10)",
        "top_positive_driver": {"feature": "mean_lst", "shap_value": 11.10},
        "top_negative_driver": {"feature": "mean_ndbi", "shap_value": -0.11}
    },
    ...
}
"""

import os
import json
import logging
import geopandas as gpd
from config_loader import load_config

logger = logging.getLogger("CitySense.processing.generate_explanations_json")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))


def main() -> None:
    """Extract per-cell indicator attribution data and write cell_explanations.json."""
    logger.info("=== City Sense -- Generate Indicator Attribution JSON ===")

    cfg = load_config()
    master_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["master_data"])
    json_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["explanations"])

    # 1. Load the master dataset
    logger.info("Loading master dataset from %s", master_path)
    gdf = gpd.read_file(master_path)

    # 2. Extract attribution data for each cell
    # top_positive_driver: indicator most strongly raising the composite index score
    # top_negative_driver: indicator most strongly suppressing the composite index score
    # explanation_text:    human-readable index-decomposition sentence (not causal claim)
    logger.info("Extracting indicator attribution data …")
    explanations = {}

    for _, row in gdf.iterrows():
        cell_id = row["cell_id"]

        cell_data = {
            "explanation_text": row.get("explanation_text", "")
        }

        # Top upward contributor
        pos_driver = row.get("top_positive_driver")
        if pos_driver is not None and str(pos_driver).lower() not in ("nan", "none"):
            cell_data["top_positive_driver"] = {
                "feature":    pos_driver,
                "shap_value": float(row.get("top_positive_shap", 0.0)),
            }

        # Top downward contributor
        neg_driver = row.get("top_negative_driver")
        if neg_driver is not None and str(neg_driver).lower() not in ("nan", "none"):
            cell_data["top_negative_driver"] = {
                "feature":    neg_driver,
                "shap_value": float(row.get("top_negative_shap", 0.0)),
            }

        explanations[cell_id] = cell_data

    # 3. Save to JSON
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(explanations, f, indent=2, ensure_ascii=False)

    logger.info("Saved attribution data for %d cells → %s", len(explanations), json_path)
    logger.info("=== Indicator attribution JSON complete! ===")


if __name__ == "__main__":
    main()
