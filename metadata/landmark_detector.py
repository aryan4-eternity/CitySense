"""
landmark_detector.py
====================
Detects nearby Points of Interest (POIs) using the Overpass API.
"""

import os
import json
import logging
from typing import Dict, Any, List

from geo_utils import query_overpass, haversine_distance
from config_loader import load_config

logger = logging.getLogger("CitySense.metadata.landmark_detector")

class LandmarkDetector:
    def __init__(self, cache_file: str):
        self.cache_file = cache_file
        self.cache = self._load_cache()
        
        cfg = load_config()
        geo_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                    cfg["output_paths"]["geographic_config"])
        with open(geo_cfg_path, 'r') as f:
            import yaml
            self.geo_cfg = yaml.safe_load(f)["geographic"]
            
        self.radius_km = self.geo_cfg.get("landmark_radius_km", 1.5)
        self.max_landmarks = self.geo_cfg.get("max_landmarks_per_cell", 5)
        self.categories = self.geo_cfg.get("osm_categories", {})

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

    def get_landmarks(self, cell_id: str, lat: float, lon: float) -> List[Dict[str, Any]]:
        """
        Fetch landmarks around a cell centroid.
        Queries Overpass API within the specified radius.
        """
        if cell_id in self.cache:
            return self.cache[cell_id]

        radius_meters = int(self.radius_km * 1000)
        
        # Build Overpass query for multiple categories
        # Example format: node["amenity"="hospital"](around:1500,lat,lon);
        query_parts = []
        for cat_name, tag in self.categories.items():
            key, val = tag.split("=")
            query_parts.append(f'node["{key}"="{val}"](around:{radius_meters},{lat},{lon});')
            query_parts.append(f'way["{key}"="{val}"](around:{radius_meters},{lat},{lon});')
            
        overpass_query = f"[out:json][timeout:25];({ ''.join(query_parts) });out center;"
        
        results = []
        response = query_overpass(overpass_query)
        
        if response and "elements" in response:
            for el in response["elements"]:
                if "tags" in el and "name" in el["tags"]:
                    name = el["tags"]["name"]
                    
                    # Get coordinates (for nodes it's lat/lon, for ways it's center lat/lon)
                    el_lat = el.get("lat") or (el.get("center", {}).get("lat"))
                    el_lon = el.get("lon") or (el.get("center", {}).get("lon"))
                    
                    if el_lat and el_lon:
                        dist = haversine_distance(lat, lon, el_lat, el_lon)
                        
                        # Determine category
                        matched_cat = "poi"
                        for cat_name, tag in self.categories.items():
                            k, v = tag.split("=")
                            if el["tags"].get(k) == v:
                                matched_cat = cat_name
                                break
                                
                        results.append({
                            "name": name,
                            "type": matched_cat,
                            "distance_km": round(dist, 2)
                        })
                        
        # Sort by distance and take top N
        results.sort(key=lambda x: x["distance_km"])
        
        # Deduplicate by name (sometimes nodes and ways return the same POI)
        seen_names = set()
        deduped = []
        for r in results:
            if r["name"] not in seen_names:
                seen_names.add(r["name"])
                deduped.append(r)
                if len(deduped) >= self.max_landmarks:
                    break

        self.cache[cell_id] = deduped
        self._save_cache()
        
        return deduped
