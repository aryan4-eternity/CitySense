"""
area_calculator.py
==================
Calculates geometric properties (area, perimeter, centroid) for grid cells.
"""

import geopandas as gpd
import pandas as pd
from typing import Tuple

def compute_geometry_stats(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Given a GeoDataFrame in EPSG:4326, computes area and perimeter in km2,
    and extracts centroid lat/lon.
    Modifies the GeoDataFrame in place and returns it.
    """
    # Create a copy with projected CRS (UTM Zone 43N for Mumbai) to get accurate metric areas
    projected = gdf.to_crs(epsg=32643)
    
    # Area in sq km
    gdf["grid_area_km2"] = projected.geometry.area / 1_000_000
    
    # Perimeter in km
    gdf["perimeter_km"] = projected.geometry.length / 1000
    
    # Centroid (in original EPSG:4326 for geocoding)
    centroids = gdf.geometry.centroid
    gdf["centroid_lon"] = centroids.x
    gdf["centroid_lat"] = centroids.y
    
    return gdf
