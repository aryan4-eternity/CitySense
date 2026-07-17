"""
geo_utils.py
============
Shared geographic utilities for coordinate transformations, distance
calculations, and external API requests (Nominatim, Overpass).
"""

import math
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("CitySense.geo_utils")

# Constant for WGS84 Earth radius in km
EARTH_RADIUS_KM = 6371.0

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees) in kilometers.
    """
    # convert decimal degrees to radians 
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = EARTH_RADIUS_KM
    return c * r

def query_overpass(query_string: str) -> Optional[Dict[str, Any]]:
    """
    Send a query to the Overpass API and return the JSON response.
    Returns None if the request fails.
    """
    overpass_url = "http://overpass-api.de/api/interpreter"
    try:
        response = requests.get(overpass_url, params={'data': query_string}, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Overpass API request failed: {e}")
        return None
