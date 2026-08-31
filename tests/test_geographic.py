import os
import sys
import geopandas as gpd
from shapely.geometry import Polygon

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from metadata.locality_detector import LocalityDetector
from metadata.landmark_detector import LandmarkDetector
from metadata.ward_detector import get_ward_and_zone
from metadata.land_use_classifier import LandUseClassifier
from metadata.population_estimator import PopulationEstimator
from metadata.area_calculator import compute_geometry_stats

def test_ward_detector():
    # Powai coordinates
    lat, lon = 19.123, 72.913
    ward, zone = get_ward_and_zone(lat, lon)
    assert "S Ward" in ward
    assert zone == "Eastern Suburbs"

def test_land_use_classifier():
    classifier = LandUseClassifier()
    # High NDVI -> Green Space
    assert classifier.classify(0.5, 0.0, 10.0) == "Green Space / Forest"
    # High NDBI, low NDVI -> Dense Commercial / Industrial
    assert classifier.classify(0.1, 0.4, 10.0) == "Dense Commercial / Industrial"
    # Low DEM, negative NDVI -> Water Body / Coastal
    assert classifier.classify(-0.1, -0.1, 1.0) == "Water Body / Coastal"

def test_population_estimator():
    estimator = PopulationEstimator()
    # Average NDBI
    pop, density = estimator.estimate("S Ward", 0.0, 1.0)
    assert pop > 10000
    
def test_area_calculator():
    # Create a dummy 1km x 1km square approximately at Mumbai's latitude
    # 0.01 deg is roughly 1km
    poly = Polygon([
        (72.913, 19.123), 
        (72.923, 19.123), 
        (72.923, 19.133), 
        (72.913, 19.133)
    ])
    gdf = gpd.GeoDataFrame({'cell_id': ['test_1']}, geometry=[poly], crs="EPSG:4326")
    
    res_gdf = compute_geometry_stats(gdf)
    
    assert "grid_area_km2" in res_gdf.columns
    assert "perimeter_km" in res_gdf.columns
    assert "centroid_lat" in res_gdf.columns
    
    # Area should be roughly 1.2 sq km for 0.01 degree at this lat
    assert 0.8 < res_gdf.loc[0, "grid_area_km2"] < 1.5

# We will skip API testing (Nominatim/Overpass) in CI tests to avoid flaky tests, 
# but they are manually verified.
