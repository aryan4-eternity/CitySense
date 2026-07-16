import pytest
import geopandas as gpd
import pandas as pd
import os

# Fixture to load the dataset once for all tests
@pytest.fixture(scope="module")
def cells_gdf():
    file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'cells_master.geojson')
    if not os.path.exists(file_path):
        pytest.skip(f"Dataset not found at {file_path}")
    return gpd.read_file(file_path)

def test_risk_score_bounds(cells_gdf):
    """Verify that risk_score and sustainability_score are within [0,100]."""
    assert 'risk_score' in cells_gdf.columns, "risk_score column is missing"
    assert 'sustainability_score' in cells_gdf.columns, "sustainability_score column is missing"
    
    # Check bounds (allowing a tiny float tolerance just in case)
    assert cells_gdf['risk_score'].min() >= -0.01, "Risk score is below 0"
    assert cells_gdf['risk_score'].max() <= 100.01, "Risk score is above 100"
    
    assert cells_gdf['sustainability_score'].min() >= -0.01, "Sustainability score is below 0"
    assert cells_gdf['sustainability_score'].max() <= 100.01, "Sustainability score is above 100"

def test_score_correlation(cells_gdf):
    """Verify that risk_score and sustainability_score are negatively correlated (Pearson r < -0.5)."""
    # Assuming scores are not strictly scaled to 100 yet (in our data they were 0 to 1)
    # The bounds test will pass if they are 0-1 as well.
    # We drop NAs before correlation
    df = cells_gdf[['risk_score', 'sustainability_score']].dropna()
    
    if len(df) > 1:
        corr = df['risk_score'].corr(df['sustainability_score'])
        assert corr < -0.5, f"Expected strong negative correlation, but got r = {corr:.3f}"
    else:
        pytest.skip("Not enough data to compute correlation")

def test_cluster_labels(cells_gdf):
    """Verify that all cells have a non-null cluster label."""
    # Sometimes it's called 'cluster' or 'cluster_label'
    cluster_col = 'cluster' if 'cluster' in cells_gdf.columns else 'cluster_label'
    assert cluster_col in cells_gdf.columns, "Cluster column is missing"
    
    null_count = cells_gdf[cluster_col].isnull().sum()
    assert null_count == 0, f"Found {null_count} cells with null cluster labels"
