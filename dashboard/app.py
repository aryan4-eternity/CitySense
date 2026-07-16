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

# Page configuration
st.set_page_config(page_title="City Sense", layout="wide")
st.title("🌆 City Sense – Mumbai Environmental Dashboard")

# ------------------------------------------------------------------------------
# 1. Load data
# ------------------------------------------------------------------------------
@st.cache_data
def load_geodata(path):
    """Load GeoJSON master dataset and ensure coordinate reference system."""
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    return gdf

@st.cache_data
def load_explanations(path):
    """Load cell explanations JSON."""
    with open(path, "r") as f:
        return json.load(f)

gdf = load_geodata("data/cells_master.geojson")
explanations = load_explanations("data/cell_explanations.json")

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
        hottest_id = gdf.loc[hottest_idx, "cell_id"] if "cell_id" in gdf.columns else hottest_idx
        col3.metric("Hottest Cell", f"{hottest_id} ({hottest_val:.1f}°C)")

    if "mean_ndvi" in gdf.columns:
        greenest_idx = gdf["mean_ndvi"].idxmax()
        greenest_val = gdf.loc[greenest_idx, "mean_ndvi"]
        greenest_id = gdf.loc[greenest_idx, "cell_id"] if "cell_id" in gdf.columns else greenest_idx
        col4.metric("Greenest Cell", f"{greenest_id} (NDVI {greenest_val:.3f})")

    if "cluster" in gdf.columns:
        # Most at-risk cluster: cluster with highest mean risk score
        cluster_risk = gdf.groupby("cluster")["risk_score"].mean().idxmax()
        col5.metric("Most At-Risk Cluster", str(cluster_risk))
else:
    st.warning("No data loaded. Check your data files.")

# ------------------------------------------------------------------------------
# 3. Build Folium map
# ------------------------------------------------------------------------------
m = folium.Map(location=[19.076, 72.877], zoom_start=11, tiles=None)
folium.TileLayer(
    "CartoDB Positron",
    name="Basemap – Light",
    control=False  # base tile doesn't need toggle, but we'll add it as default
).add_to(m)

# Add a dark basemap as alternative (will appear in layer control)
folium.TileLayer("CartoDB dark_matter", name="Basemap – Dark").add_to(m)

# Optional static satellite overlays (if files exist)
overlay_dir = "data/overlays"
if os.path.exists(overlay_dir):
    rgb_tif = os.path.join(overlay_dir, "mumbai_rgb.tif")
    thermal_tif = os.path.join(overlay_dir, "mumbai_thermal.tif")
    if os.path.exists(rgb_tif):
        folium.raster_layers.ImageOverlay(
            image=rgb_tif,
            bounds=[[18.89, 72.77], [19.27, 72.98]],  # rough Mumbai bounds
            name="Sentinel‑2 RGB",
            opacity=0.7,
        ).add_to(m)
    if os.path.exists(thermal_tif):
        folium.raster_layers.ImageOverlay(
            image=thermal_tif,
            bounds=[[18.89, 72.77], [19.27, 72.98]],
            name="Thermal False‑Color",
            opacity=0.7,
        ).add_to(m)
else:
    st.sidebar.info("ℹ️ Satellite overlays not found. Place .tif files in data/overlays/ to enable.")

# ------------------------------------------------------------------------------
# 4. Function: add choropleth layer
# ------------------------------------------------------------------------------
def add_choropleth(gdf, column, name, color_map, tooltip_fields=None, fill_opacity=0.7):
    """
    Adds a GeoJson choropleth layer to the map m.
    Returns the folium.GeoJson layer so we can use it for click interactions if needed.
    """
    # Drop missing values for the column to avoid style errors
    valid_gdf = gdf.dropna(subset=[column])
    if len(valid_gdf) == 0:
        return None

    # Build a style function based on a colormap
    def style_function(feature):
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
        fields=tooltip_fields if tooltip_fields else ["cell_id", column],
        aliases=["Cell ID", column.replace("_", " ").title()],
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
def risk_color(ratio):  # red (high) -> yellow -> green (low)
    # diverging: high risk red, low risk green
    if ratio > 0.5:
        r = 255
        g = int(255 * (1 - (ratio - 0.5) * 2))
    else:
        r = int(255 * (ratio * 2))
        g = 255
    return f"#{r:02x}{g:02x}00"

def sustainability_color(ratio):  # green (high) -> red (low)
    # high sustainability is green, low is red
    if ratio > 0.5:
        g = 255
        r = int(255 * (1 - (ratio - 0.5) * 2))
    else:
        g = int(255 * (ratio * 2))
        r = 255
    return f"#{r:02x}{g:02x}00"

def ndvi_color(ratio):  # brown -> yellow -> dark green
    if ratio < 0.5:
        r = 150
        g = int(150 + ratio * 210)  # yellow-green
    else:
        r = int(150 - (ratio - 0.5) * 300)
        g = 255
    b = 0
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{b:02x}"

def lst_color(ratio):  # cool (blue) to hot (red)
    r = int(ratio * 255)
    b = int((1 - ratio) * 255)
    return f"#{r:02x}00{b:02x}"

def ndbi_color(ratio):  # grey-pink for built-up
    r = int(180 + ratio * 75)
    g = int(130 + ratio * 50)
    b = int(130 + ratio * 50)
    return f"#{r:02x}{g:02x}{b:02x}"

def dem_color(ratio):  # brown (low) to blue (high) via green
    if ratio < 0.5:
        r = int(139 + ratio * 200)
        g = int(69 + ratio * 200)
        b = int(19 + ratio * 50)
    else:
        r = int(34 - (ratio - 0.5) * 68)
        g = int(139 - (ratio - 0.5) * 50)
        b = int(34 + (ratio - 0.5) * 200)
    return f"#{r:02x}{g:02x}{b:02x}"

def uhi_color(ratio):  # diverging: RdBu (red high, blue low)
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
    def cluster_style(feature):
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
    tooltip=folium.GeoJsonTooltip(fields=["cell_id"], aliases=["Cell ID"]),
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
        # Display info in sidebar and main area
        with st.sidebar:
            st.markdown(f"### Cell `{clicked_cell_id}`")
            # Risk & Sustainability
            if "risk_score" in cell:
                st.metric("Risk Score", f"{cell['risk_score']:.2f}")
            if "sustainability_score" in cell:
                st.metric("Sustainability Score", f"{cell['sustainability_score']:.2f}")
            if "cluster" in cell:
                st.markdown(f"**Cluster:** {cell['cluster']}")

            st.markdown("---")
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
                st.markdown("**🧠 AI Explanation**")
                st.info(explanation_text if explanation_text else "No explanation available.")

                # SHAP values if present
                top_pos = explain.get("top_positive_driver")
                top_neg = explain.get("top_negative_driver")
                if top_pos:
                    st.write(f"↑ **Positive driver:** {top_pos.get('feature', '?')} (SHAP {top_pos.get('shap_value', 0):.3f})")
                if top_neg:
                    st.write(f"↓ **Negative driver:** {top_neg.get('feature', '?')} (SHAP {top_neg.get('shap_value', 0):.3f})")
            else:
                st.markdown("_No explanation found for this cell._")

            # Rule-based recommendation
            st.markdown("---")
            st.markdown("**💡 Recommendation**")
            rec = []
            ndvi_val = cell.get("mean_ndvi", 0)
            lst_val = cell.get("mean_lst", 0)
            dem_val = cell.get("mean_dem", 0)
            ndbi_val = cell.get("mean_ndbi", 0)
            if ndvi_val is not None and lst_val is not None:
                if ndvi_val < 0.2 and lst_val > 35:
                    rec.append("🌳 Increase green cover (low NDVI, high temperature).")
            if dem_val is not None and dem_val < 5:
                rec.append("💧 Elevation risk – improve drainage and flood protection.")
            if ndbi_val is not None and ndbi_val > 0.2:
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