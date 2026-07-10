"""
merge_indicators.py
===================
Loads the four per-cell GeoJSON files (NDVI, LST, NDBI, DEM) and merges
them on cell_id into a single master GeoDataFrame. Saves the result as
data/cells_master.geojson.

Final columns: cell_id, mean_ndvi, mean_lst, mean_ndbi, mean_dem, geometry

Usage:
    python processing/merge_indicators.py    (from project root)
"""

import os
import yaml
import geopandas as gpd
import pandas as pd

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def main():
    print("=" * 60)
    print("  City Sense -- Week 4: Merge Indicators")
    print("=" * 60)

    cfg = load_config()
    paths = cfg["output_paths"]

    # Define input files and the column each contributes
    sources = {
        "ndvi": {
            "path": os.path.join(PROJECT_ROOT, paths["ndvi_grid"]),
            "column": "mean_ndvi",
        },
        "lst": {
            "path": os.path.join(PROJECT_ROOT, paths["lst_grid"]),
            "column": "mean_lst",
        },
        "ndbi": {
            "path": os.path.join(PROJECT_ROOT, paths["ndbi_grid"]),
            "column": "mean_ndbi",
        },
        "dem": {
            "path": os.path.join(PROJECT_ROOT, paths["dem_grid"]),
            "column": "mean_dem",
        },
    }

    # ---- Load the first source as the base GeoDataFrame --------------------
    print("\n> Loading indicator layers...")
    base_name = "ndvi"
    base_info = sources.pop(base_name)
    master = gpd.read_file(base_info["path"])
    print(f"  [{base_name.upper()}] {len(master)} cells, column: {base_info['column']}")

    # ---- Merge remaining sources on cell_id --------------------------------
    for name, info in sources.items():
        gdf = gpd.read_file(info["path"])
        col = info["column"]
        print(f"  [{name.upper()}] {len(gdf)} cells, column: {col}")

        # Extract only cell_id and the indicator column (drop geometry)
        df = pd.DataFrame(gdf[["cell_id", col]])
        master = master.merge(df, on="cell_id", how="left")

    # ---- Ensure correct column order ---------------------------------------
    desired_cols = ["cell_id", "mean_ndvi", "mean_lst", "mean_ndbi", "mean_dem", "geometry"]
    # Keep only desired columns (some may have extra from previous runs)
    available = [c for c in desired_cols if c in master.columns]
    master = master[available]

    # ---- Print summary -----------------------------------------------------
    print(f"\n> Merged dataset: {len(master)} rows x {len(master.columns)} columns")
    print(f"  Columns: {list(master.columns)}")
    print(f"\n  First 5 rows:")
    # Print without geometry for readability
    print(master.drop(columns="geometry").head().to_string(index=False))

    print(f"\n  Basic statistics:")
    print(master.drop(columns=["geometry", "cell_id"]).describe().to_string())

    # ---- Check for missing values ------------------------------------------
    missing = master.drop(columns="geometry").isnull().sum()
    if missing.sum() > 0:
        print(f"\n  [WARNING] Missing values detected:")
        for col, count in missing.items():
            if count > 0:
                print(f"    {col}: {count} missing")
    else:
        print(f"\n  [OK] No missing values in any column.")

    # ---- Save ---------------------------------------------------------------
    output_path = os.path.join(PROJECT_ROOT, paths["master_data"])
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    master.to_file(output_path, driver="GeoJSON")
    print(f"\n[OK] Saved master dataset to: {output_path}")

    print("\n" + "=" * 60)
    print("  [OK] Merge complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
