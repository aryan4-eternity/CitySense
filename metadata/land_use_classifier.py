"""
land_use_classifier.py
======================
Classifies dominant land use based on environmental indicators.
"""

import os
import logging
from typing import Dict, Any

from config_loader import load_config

logger = logging.getLogger("CitySense.metadata.land_use_classifier")

class LandUseClassifier:
    def __init__(self):
        cfg = load_config()
        geo_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                    cfg["output_paths"]["geographic_config"])
        with open(geo_cfg_path, 'r') as f:
            import yaml
            self.thresholds = yaml.safe_load(f)["geographic"]["land_use_thresholds"]

    def classify(self, ndvi: float, ndbi: float, dem: float) -> str:
        """
        Classifies land use into broad categories based on indicator heuristics.
        """
        if ndvi is None or ndbi is None or dem is None:
            return "Unknown"
            
        # Handle nan values
        import math
        if math.isnan(ndvi) or math.isnan(ndbi) or math.isnan(dem):
            return "Unknown"

        if dem < self.thresholds.get("water_dem_max", 2.0) and ndvi < 0.0:
            return "Water Body / Coastal"
            
        if ndvi >= self.thresholds.get("green_ndvi_min", 0.4):
            return "Green Space / Forest"
            
        if ndbi >= self.thresholds.get("commercial_ndbi_min", 0.3):
            if ndvi < 0.15:
                return "Dense Commercial / Industrial"
            else:
                return "Mixed Urban"
                
        if ndbi >= self.thresholds.get("residential_ndbi_min", 0.2):
            return "Residential"
            
        if ndvi > 0.2 and ndbi < 0.1:
            return "Sparse Vegetation / Open Land"
            
        return "Mixed Residential"
