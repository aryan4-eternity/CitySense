# dashboard/app.py
"""
City Sense – Mumbai Environmental Risk & Sustainability Dashboard
"""

import streamlit as st
from streamlit_folium import st_folium
import folium
from folium.plugins import Fullscreen
import geopandas as gpd
import pandas as pd
import json
import os
import numpy as np
from collections.abc import Callable
from typing import Any
from config_loader import load_config, project_path

CONFIG = load_config()

# Page configuration
st.set_page_config(page_title="City Sense", layout="wide")
st.title("🌆 City Sense – Mumbai Environmental Dashboard")

# ------------------------------------------------------------------------------
# 1. Load data
# ------------------------------------------------------------------------------
@st.cache_data
def load_geodata(path: str) -> gpd.GeoDataFrame:
    """Load GeoJSON master dataset and ensure coordinate reference system."""
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    return gdf

@st.cache_data
def load_explanations(path: str) -> Any:
    """Load cell explanations JSON."""
    with open(path, "r") as f:
        return json.load(f)

@st.cache_data
def load_geographic_metadata(path: str) -> dict:
    """Load geographic metadata JSON."""
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

gdf = load_geodata(str(project_path(CONFIG, "master_data")))
explanations = load_explanations(str(project_path(CONFIG, "explanations")))
geo_meta = load_geographic_metadata(str(project_path(CONFIG, "geographic_metadata")))

# Augment gdf with display_name for tooltips
def get_display_name(cell_id):
    if geo_meta and cell_id in geo_meta:
        gm = geo_meta[cell_id]
        loc = gm.get("primary_locality", "Unknown")
        gid = gm.get("grid_id", cell_id)
        return f"{loc} ({gid})"
    return cell_id

if "cell_id" in gdf.columns:
    gdf["display_name"] = gdf["cell_id"].apply(get_display_name)
else:
    gdf["display_name"] = gdf.index.astype(str)

# Quick sanity check
st.sidebar.write(f"✅ Loaded {len(gdf)} grid cells")

# ------------------------------------------------------------------------------
# 2. Summary statistics (top of dashboard)
# ------------------------------------------------------------------------------
if not gdf.empty:
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Cells", len(gdf))

    avg_risk = gdf["risk_score"].mean() if "risk_score" in gdf.columns else 0
    col2.metric("Avg Risk Score", f"{avg_risk:.2f}")

    if "mean_lst" in gdf.columns:
        hottest_idx = gdf["mean_lst"].idxmax()
        hottest_val = gdf.loc[hottest_idx, "mean_lst"]
        hottest_name = gdf.loc[hottest_idx, "display_name"]
        col3.metric("Hottest Area", f"{hottest_name} ({hottest_val:.1f}°C)")

    if "mean_ndvi" in gdf.columns:
        greenest_idx = gdf["mean_ndvi"].idxmax()
        greenest_val = gdf.loc[greenest_idx, "mean_ndvi"]
        greenest_name = gdf.loc[greenest_idx, "display_name"]
        col4.metric("Greenest Area", f"{greenest_name} (NDVI {greenest_val:.3f})")

    if "cluster" in gdf.columns:
        # Most at-risk cluster: cluster with highest mean risk score
        cluster_risk = gdf.groupby("cluster")["risk_score"].mean().idxmax()
        col5.metric("Most At-Risk Cluster", str(cluster_risk))
else:
    st.warning("No data loaded. Check your data files.")

# ------------------------------------------------------------------------------
# 3. Build Folium map
# ------------------------------------------------------------------------------
m = folium.Map(
    location=CONFIG["dashboard"]["map_center"],
    zoom_start=CONFIG["dashboard"]["zoom_start"],
    tiles=None,
)
folium.TileLayer(
    "CartoDB Positron",
    name="Basemap – Light",
    control=False  # base tile doesn't need toggle, but we'll add it as default
).add_to(m)

# Add a dark basemap as alternative (will appear in layer control)
folium.TileLayer("CartoDB dark_matter", name="Basemap – Dark").add_to(m)

# Optional static satellite overlays (if files exist)
overlay_dir = str(project_path(CONFIG, "overlays_dir"))
if os.path.exists(overlay_dir):
    rgb_tif = os.path.join(overlay_dir, "mumbai_rgb.tif")
    thermal_tif = os.path.join(overlay_dir, "mumbai_thermal.tif")
    if os.path.exists(rgb_tif):
        folium.raster_layers.ImageOverlay(
            image=rgb_tif,
            bounds=CONFIG["dashboard"]["overlay_bounds"],
            name="Sentinel‑2 RGB",
            opacity=0.7,
        ).add_to(m)
    if os.path.exists(thermal_tif):
        folium.raster_layers.ImageOverlay(
            image=thermal_tif,
            bounds=CONFIG["dashboard"]["overlay_bounds"],
            name="Thermal False‑Color",
            opacity=0.7,
        ).add_to(m)
else:
    st.sidebar.info("ℹ️ Satellite overlays not found. Place .tif files in data/overlays/ to enable.")

# ------------------------------------------------------------------------------
# 4. Function: add choropleth layer
# ------------------------------------------------------------------------------
def add_choropleth(
    gdf: gpd.GeoDataFrame,
    column: str,
    name: str,
    color_map: Callable[[float], str],
    tooltip_fields: list[str] | None = None,
    fill_opacity: float = 0.7,
) -> folium.GeoJson | None:
    """
    Adds a GeoJson choropleth layer to the map m.
    Returns the folium.GeoJson layer so we can use it for click interactions if needed.
    """
    # Drop missing values for the column to avoid style errors
    valid_gdf = gdf.dropna(subset=[column])
    if len(valid_gdf) == 0:
        return None

    # Build a style function based on a colormap
    def style_function(feature: dict[str, Any]) -> dict[str, Any]:
        """Style one GeoJSON feature from the selected numeric column."""
        value = feature["properties"].get(column)
        if value is None:
            return {"fillColor": "#cccccc", "color": "#999999", "weight": 0.5, "fillOpacity": 0}
        # Map value to color (linearly scaled within valid range)
        vmin = valid_gdf[column].min()
        vmax = valid_gdf[column].max()
        if vmax == vmin:
            ratio = 0.5
        else:
            ratio = (value - vmin) / (vmax - vmin)
        color = color_map(ratio)
        return {
            "fillColor": color,
            "color": "#555555",
            "weight": 0.5,
            "fillOpacity": fill_opacity,
        }

    # Tooltip
    tooltip = folium.GeoJsonTooltip(
        fields=tooltip_fields if tooltip_fields else ["display_name", column],
        aliases=["Location", column.replace("_", " ").title()],
        localize=True,
    ) if tooltip_fields else None

    layer = folium.GeoJson(
        valid_gdf,
        name=name,
        style_function=style_function,
        tooltip=tooltip,
        highlight_function=lambda x: {"weight": 2, "color": "black"},
        show=False,  # start hidden, user can toggle
    )
    layer.add_to(m)
    return layer

# Color maps as simple functions
def risk_color(ratio: float) -> str:
    """Return a green-to-red color representing normalized risk."""
    # diverging: high risk red, low risk green
    if ratio > 0.5:
        r = 255
        g = int(255 * (1 - (ratio - 0.5) * 2))
    else:
        r = int(255 * (ratio * 2))
        g = 255
    return f"#{r:02x}{g:02x}00"

def sustainability_color(ratio: float) -> str:
    """Return a red-to-green color representing normalized sustainability."""
    # high sustainability is green, low is red
    if ratio > 0.5:
        g = 255
        r = int(255 * (1 - (ratio - 0.5) * 2))
    else:
        g = int(255 * (ratio * 2))
        r = 255
    return f"#{r:02x}{g:02x}00"

def ndvi_color(ratio: float) -> str:
    """Return a brown-to-green color representing normalized NDVI."""
    if ratio < 0.5:
        r = 150
        g = int(150 + ratio * 210)  # yellow-green
    else:
        r = int(150 - (ratio - 0.5) * 300)
        g = 255
    b = 0
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{b:02x}"

def lst_color(ratio: float) -> str:
    """Return a blue-to-red color representing normalized temperature."""
    r = int(ratio * 255)
    b = int((1 - ratio) * 255)
    return f"#{r:02x}00{b:02x}"

def ndbi_color(ratio: float) -> str:
    """Return a grey-pink color representing normalized built-up index."""
    r = int(180 + ratio * 75)
    g = int(130 + ratio * 50)
    b = int(130 + ratio * 50)
    return f"#{r:02x}{g:02x}{b:02x}"

def dem_color(ratio: float) -> str:
    """Return a terrain-like color representing normalized elevation."""
    if ratio < 0.5:
        r = int(139 + ratio * 200)
        g = int(69 + ratio * 200)
        b = int(19 + ratio * 50)
    else:
        r = int(34 - (ratio - 0.5) * 68)
        g = int(139 - (ratio - 0.5) * 50)
        b = int(34 + (ratio - 0.5) * 200)
    return f"#{r:02x}{g:02x}{b:02x}"

def uhi_color(ratio: float) -> str:
    """Return a diverging color representing normalized UHI intensity."""
    if ratio < 0.5:
        # blue to white
        r = int(ratio * 2 * 200)
        g = int(ratio * 2 * 100)
        b = 255
    else:
        # white to red
        r = 255
        g = int((1 - (ratio - 0.5) * 2) * 100)
        b = int((1 - (ratio - 0.5) * 2) * 200)
    return f"#{r:02x}{g:02x}{b:02x}"

# Add layers if columns exist
col_layers = {
    "risk_score": ("Risk Score", risk_color),
    "sustainability_score": ("Sustainability Score", sustainability_color),
    "mean_ndvi": ("NDVI", ndvi_color),
    "mean_lst": ("LST (°C)", lst_color),
    "mean_ndbi": ("NDBI", ndbi_color),
    "mean_dem": ("DEM (m)", dem_color),
    "uhi_intensity": ("UHI Intensity", uhi_color),
}
for col, (label, cmap) in col_layers.items():
    if col in gdf.columns:
        add_choropleth(gdf, col, label, cmap)

# Add cluster layer as distinct colors (categorical)
if "cluster" in gdf.columns:
    clusters = gdf["cluster"].dropna().unique()
    # create a discrete color mapping
    import matplotlib.colors as mcolors
    import matplotlib.cm as cm
    colors = cm.tab10(np.linspace(0, 1, len(clusters)))
    cluster_color_dict = {
        cl: mcolors.rgb2hex(colors[i]) for i, cl in enumerate(sorted(clusters))
    }
    def cluster_style(feature: dict[str, Any]) -> dict[str, Any]:
        """Style one GeoJSON feature with its categorical cluster color."""
        cl = feature["properties"].get("cluster")
        color = cluster_color_dict.get(cl, "#cccccc")
        return {"fillColor": color, "color": "#333333", "weight": 0.5, "fillOpacity": 0.7}
    folium.GeoJson(
        gdf,
        name="Clusters",
        style_function=cluster_style,
        tooltip=folium.GeoJsonTooltip(fields=["cluster"], aliases=["Cluster"]),
        show=False,
    ).add_to(m)

# ------------------------------------------------------------------------------
# 5. Interactive layer for click detection (transparent, but with cell_id)
# ------------------------------------------------------------------------------
# We create a dedicated GeoJson layer that sends the clicked feature data back.
interactive_layer = folium.GeoJson(
    gdf,
    name="Clickable Grid (transparent)",
    style_function=lambda x: {"fillColor": "#000000", "color": "#000000", "weight": 0, "fillOpacity": 0},
    highlight_function=lambda x: {"weight": 3, "color": "#FF0000", "fillOpacity": 0.3},
    tooltip=folium.GeoJsonTooltip(fields=["display_name"], aliases=["Location"]),
    zoom_on_click=True,
)
interactive_layer.add_to(m)

# Add layer control
folium.LayerControl(collapsed=False).add_to(m)
Fullscreen().add_to(m)

# ------------------------------------------------------------------------------
# 6. Render map and capture clicks
# ------------------------------------------------------------------------------
st.markdown("### Interactive Map")
map_data = st_folium(m, width=1200, height=650, returned_objects=["last_object_clicked"])

# ------------------------------------------------------------------------------
# 7. Sidebar / expander for cell details
# ------------------------------------------------------------------------------
st.sidebar.header("🔍 Cell Details")
clicked_cell_id = None

if map_data and map_data["last_object_clicked"]:
    props = map_data["last_object_clicked"].get("properties", {})
    clicked_cell_id = props.get("cell_id", None)

if clicked_cell_id is not None:
    # Retrieve row from GeoDataFrame
    cell_row = gdf[gdf["cell_id"] == clicked_cell_id]
    if not cell_row.empty:
        cell = cell_row.iloc[0]
        
        with st.sidebar:
            # Check if geographic metadata exists for this cell
            if geo_meta and clicked_cell_id in geo_meta:
                gm = geo_meta[clicked_cell_id]
                st.markdown(f"### 📍 Geographic Profile")
                st.markdown(f"**{gm.get('primary_locality', 'Unknown')}** (Grid {gm.get('grid_id', clicked_cell_id)})")
                
                ward = gm.get('ward', 'Unknown Ward')
                zone = gm.get('zone', 'Unknown Zone')
                st.markdown(f"📌 {ward} | {zone}")
                
                st.markdown(f"🏘️ {gm.get('dominant_land_use', 'Unknown')}")
                
                pop = gm.get('population', 0)
                if pop > 0:
                    st.markdown(f"👥 Population: ~{pop:,}")
                else:
                    st.markdown(f"👥 Population: Minimal/Uninhabited")
                    
                secondary = gm.get('secondary_localities', [])
                if secondary:
                    st.markdown("**📍 Nearby Areas**")
                    for s in secondary[:3]:
                        st.markdown(f"  • {s}")
                        
                landmarks = gm.get('nearest_landmarks', [])
                if landmarks:
                    st.markdown("**🏛️ Nearby Landmarks**")
                    for lm in landmarks:
                        st.markdown(f"  • {lm['name']} ({lm['distance_km']} km)")
                        
                lat, lon = gm.get('centroid_lat'), gm.get('centroid_lon')
                if lat and lon:
                    st.markdown("**🌐 Coordinates**")
                    st.markdown(f"{lat}°N, {lon}°E")
                    st.markdown(f"[🔗 Open in Google Maps](https://www.google.com/maps/search/?api=1&query={lat},{lon})")
                    st.markdown(f"[🔗 Open in OpenStreetMap](https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon})")
            else:
                st.markdown(f"### Cell `{clicked_cell_id}`")
                st.info("💡 Run geographic enrichment pipeline to see locality details.")

            st.markdown("---")
            st.markdown("### 📊 Environmental Analysis")
            
            # Risk & Sustainability
            if "risk_score" in cell:
                st.metric("Risk Score", f"{cell['risk_score']:.2f}")
            if "sustainability_score" in cell:
                st.metric("Sustainability Score", f"{cell['sustainability_score']:.2f}")
            if "cluster_label" in cell:
                st.markdown(f"**Cluster:** {cell['cluster_label']}")
            elif "cluster" in cell:
                st.markdown(f"**Cluster:** {cell['cluster']}")

            # Indicators
            indicators = {
                "mean_ndvi": "🌿 NDVI",
                "mean_lst": "🌡️ LST (°C)",
                "mean_ndbi": "🏢 NDBI",
                "mean_dem": "⛰️ DEM (m)",
                "uhi_intensity": "🔥 UHI Intensity",
            }
            for col, label in indicators.items():
                if col in cell:
                    st.write(f"{label}: **{cell[col]:.3f}**" if not isinstance(cell[col], str) else f"{label}: {cell[col]}")

            # Explanation
            if clicked_cell_id in explanations:
                explain = explanations[clicked_cell_id]
                explanation_text = explain.get("explanation_text", "")
                st.markdown("---")
                st.markdown("**🧠 AI Explanation**")
                st.info(explanation_text if explanation_text else "No explanation available.")

                # SHAP values if present
                top_pos = explain.get("top_positive_driver")
                top_neg = explain.get("top_negative_driver")
                if top_pos and top_pos.get("feature"):
                    st.write(f"↑ **Positive driver:** {top_pos.get('feature')} (SHAP {top_pos.get('shap_value', 0):.3f})")
                if top_neg and top_neg.get("feature"):
                    st.write(f"↓ **Negative driver:** {top_neg.get('feature')} (SHAP {top_neg.get('shap_value', 0):.3f})")

            # Rule-based recommendation
            st.markdown("---")
            st.markdown("**💡 Recommendation**")
            rec = []
            ndvi_val = cell.get("mean_ndvi", 0)
            lst_val = cell.get("mean_lst", 0)
            dem_val = cell.get("mean_dem", 0)
            ndbi_val = cell.get("mean_ndbi", 0)
            if ndvi_val is not None and lst_val is not None:
                if (ndvi_val < CONFIG["dashboard"]["thresholds"]["low_ndvi"]
                        and lst_val > CONFIG["dashboard"]["thresholds"]["high_lst"]):
                    rec.append("🌳 Increase green cover (low NDVI, high temperature).")
            if dem_val is not None and dem_val < CONFIG["dashboard"]["thresholds"]["low_dem"]:
                rec.append("💧 Elevation risk – improve drainage and flood protection.")
            if ndbi_val is not None and ndbi_val > CONFIG["dashboard"]["thresholds"]["high_ndbi"]:
                rec.append("🏗️ High built-up density – consider permeable surfaces and cool roofs.")
            
            if rec:
                for r in rec:
                    st.success(r)
            else:
                st.write("No specific urgent recommendation.")
    else:
        st.sidebar.warning("Cell data not found.")
else:
    st.sidebar.info("👆 Click a grid cell on the map to see its details.")

# ------------------------------------------------------------------------------
# Footer
# ------------------------------------------------------------------------------
st.markdown("---")
st.caption("City Sense Dashboard – Week 7 | Built with Streamlit, Folium, and Geopandas")
