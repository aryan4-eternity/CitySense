"""
geo_enrichment.py
=================
Orchestrates the Geographic Intelligence Layer enrichment.
Processes cells_master.geojson, adds geographic context, and outputs geographic_metadata.json.
"""

import os
import json
import logging
import time
import geopandas as gpd
from tqdm import tqdm

from config_loader import load_config, project_path
from .locality_detector import LocalityDetector
from .ward_detector import get_ward_and_zone
from .landmark_detector import LandmarkDetector
from .land_use_classifier import LandUseClassifier
from .population_estimator import PopulationEstimator
from .area_calculator import compute_geometry_stats

logger = logging.getLogger("CitySense.metadata.geo_enrichment")

def main() -> None:
    """Main orchestrator for geographic enrichment."""
    logger.info("=== City Sense -- Phase 1: Geographic Enrichment ===")
    
    cfg = load_config()
    master_path = str(project_path(cfg, "master_data"))
    output_json_path = str(project_path(cfg, "geographic_metadata"))
    cache_dir = os.path.dirname(output_json_path)
    os.makedirs(cache_dir, exist_ok=True)
    
    logger.info(f"Loading master dataset from {master_path}")
    gdf = gpd.read_file(master_path)
    
    logger.info("Computing area and centroid statistics...")
    gdf = compute_geometry_stats(gdf)
    
    # Initialize sub-modules
    loc_detector = LocalityDetector(os.path.join(cache_dir, "nominatim_cache.json"))
    lm_detector = LandmarkDetector(os.path.join(cache_dir, "overpass_cache.json"))
    lu_classifier = LandUseClassifier()
    pop_estimator = PopulationEstimator()
    
    metadata = {}
    
    # Process cells
    logger.info(f"Enriching {len(gdf)} grid cells. This may take a while due to API rate limits...")
    
    start_time = time.time()
    for idx, row in tqdm(gdf.iterrows(), total=len(gdf), desc="Enriching grids"):
        cell_id = row["cell_id"]
        # Generate new grid_id (MUM-001 format)
        grid_id = f"MUM-{idx+1:03d}"
        
        lat = row["centroid_lat"]
        lon = row["centroid_lon"]
        area_km2 = row["grid_area_km2"]
        ndbi = row.get("mean_ndbi")
        ndvi = row.get("mean_ndvi")
        dem = row.get("mean_dem")
        
        # 1. Locality
        primary, secondary = loc_detector.get_locality(cell_id, lat, lon)
        
        # 2. Ward & Zone
        ward, zone = get_ward_and_zone(lat, lon)
        
        # 3. Landmarks
        landmarks = lm_detector.get_landmarks(cell_id, lat, lon)
        
        # 4. Land Use
        land_use = lu_classifier.classify(ndvi, ndbi, dem)
        
        # 5. Population
        pop, density = pop_estimator.estimate(ward, ndbi, area_km2)
        
        metadata[cell_id] = {
            "grid_id": grid_id,
            "primary_locality": primary,
            "secondary_localities": secondary,
            "ward": ward,
            "zone": zone,
            "nearest_landmarks": landmarks,
            "dominant_land_use": land_use,
            "population": pop,
            "population_density": density,
            "grid_area_km2": round(area_km2, 3),
            "perimeter_km": round(row["perimeter_km"], 3),
            "centroid_lat": round(lat, 5),
            "centroid_lon": round(lon, 5)
        }
    
    # Save output
    with open(output_json_path, "w") as f:
        json.dump(metadata, f, indent=2)
        
    elapsed = time.time() - start_time
    logger.info(f"Successfully generated geographic metadata for {len(metadata)} cells in {elapsed:.1f} seconds.")
    logger.info(f"Saved to {output_json_path}")
    logger.info("=== Enrichment Complete ===")

if __name__ == "__main__":
    main()
