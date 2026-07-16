"""
generate_explanations_json.py
=============================
Extracts the explainability columns (top drivers, SHAP values, explanation text)
from data/cells_master.geojson and saves them into a lightweight JSON file
(data/explanations.json).

This JSON file is loaded by the Streamlit dashboard to display AI-driven
explanations when a user clicks on a grid cell, without needing to load the
entire GeoJSON structure into memory just for text lookups.

Format:
{
    "cell_id_1": {
        "top_positive_driver": {"feature": "mean_lst", "shap_value": 4.2},
        "top_negative_driver": {"feature": "mean_ndvi", "shap_value": -1.5},
        "explanation_text": "High risk driven by high LST and low NDVI"
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
    """Generate the explanations.json file for the dashboard."""
    logger.info("=== City Sense -- Generate Explanations JSON ===")

    cfg = load_config()
    master_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["master_data"])
    json_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["explanations"])

    # 1. Load the master dataset
    logger.info("Loading master dataset from %s", master_path)
    gdf = gpd.read_file(master_path)

    # 2. Extract explanation data
    logger.info("Extracting explanation data...")
    explanations = {}

    for _, row in gdf.iterrows():
        cell_id = row["cell_id"]
        
        # Build the dictionary for this cell
        cell_data = {
            "explanation_text": row.get("explanation_text", "")
        }

        # Add top positive driver if it exists and is not null
        pos_driver = row.get("top_positive_driver")
        if pos_driver is not None and str(pos_driver).lower() != "nan" and str(pos_driver).lower() != "none":
            cell_data["top_positive_driver"] = {
                "feature": pos_driver,
                "shap_value": float(row.get("top_positive_shap", 0.0))
            }

        # Add top negative driver if it exists and is not null
        neg_driver = row.get("top_negative_driver")
        if neg_driver is not None and str(neg_driver).lower() != "nan" and str(neg_driver).lower() != "none":
            cell_data["top_negative_driver"] = {
                "feature": neg_driver,
                "shap_value": float(row.get("top_negative_shap", 0.0))
            }

        explanations[cell_id] = cell_data

    # 3. Save to JSON
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w") as f:
        json.dump(explanations, f, indent=2)

    logger.info("Saved explanations for %d cells to %s", len(explanations), json_path)
    logger.info("=== Generation complete! ===")


if __name__ == "__main__":
    main()
