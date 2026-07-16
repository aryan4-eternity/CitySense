import pytest
import geopandas as gpd
import os

@pytest.fixture(scope="module")
def cells_gdf():
    file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'cells_master.geojson')
    if not os.path.exists(file_path):
        pytest.skip(f"Dataset not found at {file_path}")
    return gpd.read_file(file_path)

def test_ndvi_range(cells_gdf):
    """Check that all mean_ndvi values are between -1 and 1."""
    assert 'mean_ndvi' in cells_gdf.columns, "mean_ndvi column is missing"
    
    invalid_ndvi = cells_gdf[(cells_gdf['mean_ndvi'] < -1.0) | (cells_gdf['mean_ndvi'] > 1.0)]
    assert len(invalid_ndvi) == 0, f"Found {len(invalid_ndvi)} cells with NDVI outside [-1, 1]"

def test_lst_range(cells_gdf):
    """Check that mean_lst values are between 10 and 60°C."""
    assert 'mean_lst' in cells_gdf.columns, "mean_lst column is missing"
    
    # We allow a small buffer just in case of extreme data anomalies, but realistically 10-60 is expected
    invalid_lst = cells_gdf[(cells_gdf['mean_lst'] < 10) | (cells_gdf['mean_lst'] > 60)]
    assert len(invalid_lst) == 0, f"Found {len(invalid_lst)} cells with LST outside [10, 60]°C"

def test_dem_range(cells_gdf):
    """Check that mean_dem values are between -10 and 1000m (plausible for Mumbai region)."""
    assert 'mean_dem' in cells_gdf.columns, "mean_dem column is missing"
    
    invalid_dem = cells_gdf[(cells_gdf['mean_dem'] < -10) | (cells_gdf['mean_dem'] > 1000)]
    assert len(invalid_dem) == 0, f"Found {len(invalid_dem)} cells with DEM outside [-10, 1000]m"
