"""
population_estimator.py
=======================
Estimates population and population density for a grid cell.
"""

import os
import logging
from typing import Tuple

from config_loader import load_config

logger = logging.getLogger("CitySense.metadata.population_estimator")

class PopulationEstimator:
    def __init__(self):
        cfg = load_config()
        geo_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                    cfg["output_paths"]["geographic_config"])
        with open(geo_cfg_path, 'r') as f:
            import yaml
            self.ward_populations = yaml.safe_load(f)["geographic"]["ward_population"]
            
        # Approximate area of Mumbai wards in sq km (for density baseline)
        # Using a flat average for simplicity if specific ward areas aren't available
        self.avg_ward_area_km2 = 25.0

    def estimate(self, ward_name: str, ndbi: float, area_km2: float) -> Tuple[int, int]:
        """
        Estimate population based on the ward baseline and cell's built-up index (NDBI).
        Returns (population, density_per_km2).
        """
        # Clean ward name to match config (e.g. "S Ward")
        clean_ward = ward_name.replace(" Ward", "") + " Ward" if "Ward" in ward_name else ward_name
        
        base_ward_pop = self.ward_populations.get(clean_ward, 300000)
        base_density = base_ward_pop / self.avg_ward_area_km2
        
        # Adjust density based on NDBI (built up area proxy)
        # Assuming higher NDBI means higher population density
        ndbi_val = 0.0 if (ndbi is None or str(ndbi).lower() == 'nan') else float(ndbi)
        
        # Heuristic multiplier: NDBI ranges roughly -0.5 to 0.5. 
        # We'll map NDBI > 0 to higher density, NDBI < 0 to lower.
        multiplier = 1.0 + (ndbi_val * 2.0)
        multiplier = max(0.1, min(multiplier, 3.0)) # Clamp between 0.1x and 3x
        
        adjusted_density = int(base_density * multiplier)
        estimated_pop = int(adjusted_density * area_km2)
        
        # If it's mostly water (density will be low due to NDBI, but let's be safe)
        if estimated_pop < 100:
            estimated_pop = 0
            adjusted_density = 0
            
        return estimated_pop, adjusted_density
