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

import time as _time

_last_overpass_call = 0.0
_OVERPASS_MIN_INTERVAL = 1.0  # seconds between calls
_consecutive_failures = 0
_CIRCUIT_BREAKER_THRESHOLD = 5  # skip all calls after this many consecutive failures
_circuit_open = False

def query_overpass(query_string: str, max_retries: int = 1) -> Optional[Dict[str, Any]]:
    """
    Send a query to the Overpass API and return the JSON response.
    Includes rate limiting, retry logic, and a circuit breaker that
    skips calls after too many consecutive failures.
    Returns None if the circuit is open or all retries are exhausted.
    """
    global _last_overpass_call, _consecutive_failures, _circuit_open
    
    # Circuit breaker: if too many consecutive failures, skip immediately
    if _circuit_open:
        return None
    
    overpass_url = "http://overpass-api.de/api/interpreter"

    for attempt in range(max_retries):
        # Rate limiting: ensure minimum interval between calls
        elapsed = _time.time() - _last_overpass_call
        if elapsed < _OVERPASS_MIN_INTERVAL:
            _time.sleep(_OVERPASS_MIN_INTERVAL - elapsed)

        try:
            _last_overpass_call = _time.time()
            response = requests.get(overpass_url, params={'data': query_string}, timeout=5)
            response.raise_for_status()
            _consecutive_failures = 0  # Reset on success
            return response.json()
        except requests.exceptions.RequestException as e:
            _consecutive_failures += 1
            if _consecutive_failures >= _CIRCUIT_BREAKER_THRESHOLD:
                _circuit_open = True
                logger.warning(
                    f"Circuit breaker OPEN after {_consecutive_failures} consecutive failures. "
                    "Skipping remaining Overpass API calls."
                )
                return None
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 2
                logger.warning(f"Overpass API attempt {attempt+1}/{max_retries} failed: {e}. Retrying in {wait}s...")
                _time.sleep(wait)
            else:
                logger.error(f"Overpass API request failed after {max_retries} attempts: {e}")
                return None

