"""
locality_detector.py
====================
Handles reverse geocoding of grid centroids to find their locality names
(suburb, neighbourhood, etc.) using OpenStreetMap Nominatim.
"""

import os
import json
import time
import logging
from typing import Dict, Any, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from config_loader import load_config, project_path

logger = logging.getLogger("CitySense.metadata.locality_detector")

class LocalityDetector:
    def __init__(self, cache_file: str):
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.geolocator = Nominatim(user_agent="citysense_mumbai_research")
        
        cfg = load_config()
        geo_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                    cfg["output_paths"]["geographic_config"])
        with open(geo_cfg_path, 'r') as f:
            import yaml
            self.geo_cfg = yaml.safe_load(f)["geographic"]
            
        self.rate_limit = self.geo_cfg.get("nominatim_rate_limit_sec", 1.1)

    def _load_cache(self) -> Dict[str, Any]:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_cache(self):
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, "w") as f:
            json.dump(self.cache, f, indent=2)

    def get_locality(self, cell_id: str, lat: float, lon: float) -> Tuple[str, list]:
        """
        Reverse geocode the lat/lon to get primary and secondary localities.
        Uses a local cache to avoid redundant API calls.
        """
        if cell_id in self.cache:
            data = self.cache[cell_id]
            return data["primary"], data["secondary"]

        primary = "Unknown"
        secondary = []

        try:
            time.sleep(self.rate_limit) # Respect Nominatim usage policy
            location = self.geolocator.reverse((lat, lon), exactly_one=True, timeout=10)
            
            if location and location.raw.get("address"):
                addr = location.raw["address"]
                # Try to find the most meaningful locality names
                possible_primaries = ["suburb", "city_district", "neighbourhood", "residential", "village", "town"]
                
                for key in possible_primaries:
                    if key in addr:
                        primary = addr[key]
                        break
                
                # Gather secondary localities (other geographical tags present)
                for key in ["neighbourhood", "residential", "suburb", "industrial", "commercial"]:
                    if key in addr and addr[key] != primary:
                        secondary.append(addr[key])
                
                # If we hit water
                if "water" in addr or "sea" in addr or "bay" in addr:
                    primary = "Water Body / Coast"
                    
            elif location and not location.raw.get("address"):
                primary = "Arabian Sea" # Fallback for offshore points in Mumbai bbox

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.warning(f"Geocoding failed for cell {cell_id} ({lat}, {lon}): {e}")
            primary = "Error Fetching Locality"

        # Save to cache
        self.cache[cell_id] = {
            "primary": primary,
            "secondary": list(set(secondary)) # unique values
        }
        self._save_cache()
        
        return self.cache[cell_id]["primary"], self.cache[cell_id]["secondary"]
