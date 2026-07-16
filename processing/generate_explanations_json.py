"""
generate_explanations_json.py
==============================
Week 6 – Export per-cell explanations to a lightweight JSON file for the
Streamlit dashboard (Week 7).

Reads the enriched data/cells_master.geojson and writes a simplified
data/cell_explanations.json containing only the fields the dashboard
needs for on-click display, avoiding the overhead of parsing a large
GeoJSON with geometry in the browser.

Output schema (list of objects):
    {
        "cell_id": "r3_c12",
        "risk_score": 72.5,
        "sustainability_score": 27.5,
        "top_positive_driver": "mean_lst",
        "top_positive_shap": 3.21,
        "top_negative_driver": "mean_ndvi",
        "top_negative_shap": -2.10,
        "explanation_text": "High risk driven by high LST (+3.21) …",
        "cluster_label": "Urban Heat Core",
        "mean_ndvi": 0.08,
        "mean_lst": 44.3,
        "mean_ndbi": 0.05,
        "mean_dem": 12.0,
        "uhi_intensity": 5.6,
        "centroid_lat": 19.05,
        "centroid_lon": 72.88
    }

Usage:
    python processing/generate_explanations_json.py   (from project root)
"""

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

import geopandas as gpd
from config_loader import load_config

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
# Fields to include in the JSON export
EXPORT_FIELDS = [
    "cell_id",
    "risk_score",
    "sustainability_score",
    "top_positive_driver",
    "top_positive_shap",
    "top_negative_driver",
    "top_negative_shap",
    "explanation_text",
    "cluster_label",
    "cluster",
    "mean_ndvi",
    "mean_lst",
    "mean_ndbi",
    "mean_dem",
    "uhi_intensity",
]


def main() -> None:
    """Export dashboard-ready explanations using configured paths."""
    print("=" * 65)
    print("  City Sense – Week 6: Generate Explanations JSON")
    print("=" * 65)

    cfg = load_config()
    master_path = os.path.join(PROJECT_ROOT,
                               cfg["output_paths"]["master_data"])
    output_path = os.path.join(PROJECT_ROOT, cfg["output_paths"]["explanations"])

    # ------------------------------------------------------------------
    # 1. Load enriched master dataset
    # ------------------------------------------------------------------
    print(f"\n▸ Loading {master_path} …")
    gdf = gpd.read_file(master_path)
    print(f"  {len(gdf)} cells loaded  |  columns: {list(gdf.columns)}")

    # Verify explanation columns exist
    required = ["top_positive_driver", "top_positive_shap",
                "top_negative_driver", "top_negative_shap",
                "explanation_text"]
    missing = [c for c in required if c not in gdf.columns]
    if missing:
        raise RuntimeError(
            f"Missing explanation columns: {missing}. "
            f"Run processing/train_explainability.py first."
        )

    # ------------------------------------------------------------------
    # 2. Compute centroids (for dashboard map tooltips)
    # ------------------------------------------------------------------
    print("▸ Computing cell centroids …")
    centroids = gdf.geometry.centroid
    gdf["centroid_lat"] = centroids.y
    gdf["centroid_lon"] = centroids.x

    # ------------------------------------------------------------------
    # 3. Build export records
    # ------------------------------------------------------------------
    print("▸ Building JSON records …")
    export_fields = EXPORT_FIELDS + ["centroid_lat", "centroid_lon"]
    records = []
    for _, row in gdf.iterrows():
        rec = {}
        for field in export_fields:
            val = row.get(field)
            # Convert numpy types to native Python for JSON serialisation
            if hasattr(val, "item"):
                val = val.item()
            rec[field] = val
        records.append(rec)

    # ------------------------------------------------------------------
    # 4. Write JSON
    # ------------------------------------------------------------------
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False,
                  default=str)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\n  [OK] Exported {len(records)} cells → {output_path}")
    print(f"       File size: {size_kb:.1f} KB")

    # ------------------------------------------------------------------
    # 5. Quick preview
    # ------------------------------------------------------------------
    print("\n▸ Preview (first 3 records):")
    for rec in records[:3]:
        print(f"  {rec['cell_id']:>8s}  risk={rec['risk_score']:5.1f}  "
              f"cluster={rec['cluster_label']}")
        print(f"           ➜ {rec['explanation_text']}")

    print("\n" + "=" * 65)
    print("  ✔  Explanations JSON export complete!")
    print("=" * 65)


if __name__ == "__main__":
    main()
