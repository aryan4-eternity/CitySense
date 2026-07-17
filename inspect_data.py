"""Temporary script to inspect the master GeoJSON data."""
import geopandas as gpd
import json

gdf = gpd.read_file('data/cells_master.geojson')
print('Shape:', gdf.shape)
print('Columns:', list(gdf.columns))
print('---')
print(gdf.head(2).drop(columns='geometry').to_string())
print('---')
print('CRS:', gdf.crs)
print('---')
print('Sample cell_id values:', gdf['cell_id'].head(5).tolist())
print('---')
# Centroid of first cell
c = gdf.geometry.centroid.iloc[0]
print(f'First cell centroid: lat={c.y}, lon={c.x}')
print(f'First cell area (deg^2): {gdf.geometry.area.iloc[0]}')
print(f'Bounds of first cell: {gdf.geometry.bounds.iloc[0].to_dict()}')
print('---')
# Check total bounds
print('Total bounds:', gdf.total_bounds)
print('Number of unique cell_ids:', gdf['cell_id'].nunique())

# Also peek at grid.geojson
gdf2 = gpd.read_file('data/grid.geojson')
print('\n--- grid.geojson ---')
print('Shape:', gdf2.shape)
print('Columns:', list(gdf2.columns))
print('Sample:', gdf2.head(1).drop(columns='geometry').to_string())
