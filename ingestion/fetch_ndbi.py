"""
fetch_ndbi.py
=============
Pulls a cloud-masked Sentinel-2 NDBI (Normalized Difference Built-up Index)
composite for the pre-monsoon window, reduces to mean per grid cell, and
saves data/ndbi_grid.geojson.

NDBI = (B11 - B8) / (B11 + B8)
    B11 = SWIR1 (1610 nm, 20m resolution)
    B8  = NIR   (842 nm,  10m resolution)

Positive NDBI => built-up / impervious surfaces
Negative NDBI => vegetation / water

Usage:
    python ingestion/fetch_ndbi.py           (from project root)
"""

import os
import sys
import time
import yaml
import ee
import geopandas as gpd

# ---------------------------------------------------------------------------
# 0. Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


# =====================================================================
# Configuration
# =====================================================================
def get_settings(cfg: dict) -> dict:
    aoi = cfg["aoi"]
    return {
        "west":  aoi["west"],
        "south": aoi["south"],
        "east":  aoi["east"],
        "north": aoi["north"],
        "start_date": cfg["time_window"]["start"],
        "end_date":   cfg["time_window"]["end"],
        "project": cfg["gee"].get("project", None),
        "s2_collection": cfg["gee"]["sentinel2_collection"],
        "grid_path": os.path.join(PROJECT_ROOT, cfg["output_paths"]["grid"]),
        "ndbi_output": os.path.join(
            PROJECT_ROOT,
            cfg["output_paths"].get("ndbi_grid", "data/ndbi_grid.geojson"),
        ),
    }


# =====================================================================
# Earth Engine init
# =====================================================================
def init_ee(project: str = None):
    try:
        ee.Initialize(project=project)
    except Exception:
        try:
            ee.Initialize(
                project=project,
                opt_url="https://earthengine-highvolume.googleapis.com",
            )
        except Exception as exc:
            print("ERROR: Could not initialize Earth Engine.")
            print('       Run  python -c "import ee; ee.Authenticate()"  first.')
            raise SystemExit(1) from exc
    print(f"[OK] Earth Engine initialized (project={project})")


def make_aoi(west, south, east, north):
    return ee.Geometry.Rectangle([west, south, east, north])


# =====================================================================
# Cloud masking (same as Week 2 -- Sentinel-2 QA60)
# =====================================================================
def mask_s2_clouds(image: ee.Image) -> ee.Image:
    """Mask opaque clouds (bit 10) and cirrus (bit 11) using QA60."""
    qa = image.select("QA60")
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = (
        qa.bitwiseAnd(cloud_bit_mask).eq(0)
        .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    )
    return image.updateMask(mask)


# =====================================================================
# NDBI composite
# =====================================================================
def get_s2_ndbi_composite(aoi, start_date, end_date, collection_id, max_cloud_pct=20):
    """
    Build a cloud-masked Sentinel-2 NDBI median composite.
    NDBI = (B11 - B8) / (B11 + B8)
    """
    s2 = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date, end_date)
        .filterBounds(aoi)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_pct))
    )
    scene_count = s2.size()

    # Cloud mask
    s2_masked = s2.map(mask_s2_clouds)

    # Compute NDBI for each image
    def add_ndbi(image):
        ndbi = image.normalizedDifference(["B11", "B8"]).rename("ndbi")
        return image.addBands(ndbi)

    s2_ndbi = s2_masked.map(add_ndbi)

    # Median composite, keep only NDBI band
    composite = s2_ndbi.select("ndbi").median().clip(aoi)

    return composite, scene_count


# =====================================================================
# Load grid as ee.FeatureCollection
# =====================================================================
def load_grid_as_ee_fc(grid_path: str):
    gdf = gpd.read_file(grid_path)
    print(f"[OK] Loaded grid: {len(gdf)} cells")

    features = []
    for _, row in gdf.iterrows():
        geom = ee.Geometry(row.geometry.__geo_interface__)
        feat = ee.Feature(geom, {"cell_id": row["cell_id"]})
        features.append(feat)

    return ee.FeatureCollection(features), gdf


# =====================================================================
# Reduce + Export
# =====================================================================
def reduce_and_export(image, grid_fc, local_gdf, output_path, band_name, scale=10):
    """Reduce image to grid cell means and export as GeoJSON."""
    reduced = image.reduceRegions(
        collection=grid_fc,
        reducer=ee.Reducer.mean(),
        scale=scale,
    )

    print("  Fetching results from Earth Engine...")
    t0 = time.time()
    fc_dict = reduced.getInfo()
    elapsed = time.time() - t0
    print(f"  [OK] Received {len(fc_dict['features'])} features in {elapsed:.1f}s")

    # Build lookup
    lookup = {}
    for feat in fc_dict["features"]:
        props = feat["properties"]
        lookup[props.get("cell_id")] = props.get("mean")

    # Merge into local GeoDataFrame
    local_gdf = local_gdf.copy()
    local_gdf[band_name] = local_gdf["cell_id"].map(lookup)

    valid = local_gdf[band_name].notna().sum()
    print(f"  Cells with valid {band_name}: {valid}/{len(local_gdf)}")
    if valid > 0:
        print(f"  Range: {local_gdf[band_name].min():.4f} to {local_gdf[band_name].max():.4f}")
        print(f"  Mean:  {local_gdf[band_name].mean():.4f}")

    result = local_gdf[["cell_id", band_name, "geometry"]].copy()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    result.to_file(output_path, driver="GeoJSON")
    print(f"[OK] Saved to: {output_path}")
    return result


# =====================================================================
# MAIN
# =====================================================================
def main():
    print("=" * 60)
    print("  City Sense -- Week 4: Fetch NDBI")
    print("=" * 60)

    cfg = load_config()
    s = get_settings(cfg)
    print(f"\nAOI        : W={s['west']}, S={s['south']}, E={s['east']}, N={s['north']}")
    print(f"Time window: {s['start_date']} -> {s['end_date']}")
    print(f"Collection : {s['s2_collection']}")
    print()

    init_ee(project=s["project"])
    aoi_geom = make_aoi(s["west"], s["south"], s["east"], s["north"])

    # Build NDBI composite
    print("> Building cloud-masked NDBI composite...")
    ndbi_composite, scene_count = get_s2_ndbi_composite(
        aoi_geom, s["start_date"], s["end_date"], s["s2_collection"]
    )
    n_scenes = scene_count.getInfo()
    print(f"  Sentinel-2 scenes matched: {n_scenes}")
    if n_scenes == 0:
        print("  [WARNING] No scenes found!")
        sys.exit(1)

    # Load grid and reduce
    print("\n> Loading grid and reducing NDBI to cell means (scale=10 m)...")
    grid_fc, local_gdf = load_grid_as_ee_fc(s["grid_path"])

    print("\n> Exporting results...")
    reduce_and_export(
        ndbi_composite, grid_fc, local_gdf,
        s["ndbi_output"], "mean_ndbi", scale=10
    )

    print("\n" + "=" * 60)
    print("  [OK] NDBI layer complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
