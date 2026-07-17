"""
ward_detector.py
================
Determines which administrative ward a grid cell belongs to.
Uses a hardcoded list of approximate ward centroids for robust mapping,
which avoids complex spatial joins with potentially incomplete OSM ward boundaries.
"""

import logging
from typing import Tuple
from geo_utils import haversine_distance

logger = logging.getLogger("CitySense.metadata.ward_detector")

# Approximate centroids for Mumbai's 24 municipal wards
# and their corresponding zones
MUMBAI_WARDS = {
    "A Ward": {"lat": 18.932, "lon": 72.829, "zone": "City"},
    "B Ward": {"lat": 18.956, "lon": 72.836, "zone": "City"},
    "C Ward": {"lat": 18.951, "lon": 72.825, "zone": "City"},
    "D Ward": {"lat": 18.966, "lon": 72.814, "zone": "City"},
    "E Ward": {"lat": 18.975, "lon": 72.835, "zone": "City"},
    "F/North": {"lat": 19.029, "lon": 72.859, "zone": "City"},
    "F/South": {"lat": 19.001, "lon": 72.840, "zone": "City"},
    "G/North": {"lat": 19.025, "lon": 72.842, "zone": "City"},
    "G/South": {"lat": 19.001, "lon": 72.820, "zone": "City"},
    "H/East": {"lat": 19.079, "lon": 72.847, "zone": "Western Suburbs"},
    "H/West": {"lat": 19.062, "lon": 72.831, "zone": "Western Suburbs"},
    "K/East": {"lat": 19.117, "lon": 72.863, "zone": "Western Suburbs"},
    "K/West": {"lat": 19.115, "lon": 72.834, "zone": "Western Suburbs"},
    "P/North": {"lat": 19.197, "lon": 72.842, "zone": "Western Suburbs"},
    "P/South": {"lat": 19.162, "lon": 72.845, "zone": "Western Suburbs"},
    "R/Central": {"lat": 19.227, "lon": 72.856, "zone": "Western Suburbs"},
    "R/North": {"lat": 19.255, "lon": 72.866, "zone": "Western Suburbs"},
    "R/South": {"lat": 19.206, "lon": 72.851, "zone": "Western Suburbs"},
    "L Ward": {"lat": 19.071, "lon": 72.882, "zone": "Eastern Suburbs"},
    "M/East": {"lat": 19.053, "lon": 72.919, "zone": "Eastern Suburbs"},
    "M/West": {"lat": 19.055, "lon": 72.898, "zone": "Eastern Suburbs"},
    "N Ward": {"lat": 19.088, "lon": 72.906, "zone": "Eastern Suburbs"},
    "S Ward": {"lat": 19.141, "lon": 72.928, "zone": "Eastern Suburbs"},
    "T Ward": {"lat": 19.176, "lon": 72.951, "zone": "Eastern Suburbs"},
}

def get_ward_and_zone(lat: float, lon: float) -> Tuple[str, str]:
    """
    Finds the closest ward to the given lat/lon by comparing distance to known ward centroids.
    """
    closest_ward = "Unknown Ward"
    closest_zone = "Unknown Zone"
    min_dist = float('inf')
    
    for ward_name, data in MUMBAI_WARDS.items():
        dist = haversine_distance(lat, lon, data["lat"], data["lon"])
        if dist < min_dist:
            min_dist = dist
            closest_ward = ward_name
            closest_zone = data["zone"]
            
    # If it's too far from any ward (e.g. > 15km), it might be outside Mumbai proper
    if min_dist > 15.0:
        return "Outside Municipal Limits", "N/A"
        
    return f"{closest_ward} Ward" if not closest_ward.endswith("Ward") else closest_ward, closest_zone
