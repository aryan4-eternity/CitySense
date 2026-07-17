# dashboard/app.py
"""
City Sense – Mumbai Environmental Risk & Sustainability Dashboard
Phase 3: Urban Planning Intelligence & Decision Engine
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import streamlit as st
from folium.plugins import Fullscreen
from streamlit_folium import st_folium

from config_loader import load_config, project_path
from environment.environment_templates import STATUS_COLORS
from planning.planning_summary import get_priority_color

CONFIG = load_config()

# Page configuration
st.set_page_config(page_title="City Sense", layout="wide")
st.title("🌆 City Sense – Mumbai Environmental Dashboard")

# ------------------------------------------------------------------------------
# 1. Data loaders  (all cached)
# ------------------------------------------------------------------------------

@st.cache_data
def load_geodata(path: str) -> gpd.GeoDataFrame:
    """Load GeoJSON master dataset and ensure coordinate reference system."""
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    return gdf


@st.cache_data
def load_explanations(path: str) -> dict:
    """Load cell explanations JSON (SHAP + AI text)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_geographic_metadata(path: str) -> dict:
    """Load geographic metadata JSON; returns {} if file not found."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data
def load_environmental_intelligence(path: str) -> dict:
    """Load environmental intelligence JSON; returns {} if file not found.

    Graceful degradation: if the Phase 2 pipeline stage has not been run
    yet, the dashboard falls back to the legacy raw-metrics display.
    """
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data
def load_planning_profiles(path: str) -> dict:
    """Load planning profiles JSON; returns {} if file not found.

    Graceful degradation: if the Phase 3 pipeline stage has not been run
    yet, the dashboard falls back to the Phase 2 panel only.
    """
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# Load all data
gdf = load_geodata(str(project_path(CONFIG, "master_data")))
explanations = load_explanations(str(project_path(CONFIG, "explanations")))
geo_meta = load_geographic_metadata(str(project_path(CONFIG, "geographic_metadata")))
env_intel = load_environmental_intelligence(str(project_path(CONFIG, "environmental_intelligence")))
planning_profiles = load_planning_profiles(str(project_path(CONFIG, "planning_profiles")))


# Augment GDF with display_name for map tooltips
def _get_display_name(cell_id: str) -> str:
    if geo_meta and cell_id in geo_meta:
        gm = geo_meta[cell_id]
        loc = gm.get("primary_locality", "Unknown")
        gid = gm.get("grid_id", cell_id)
        return f"{loc} ({gid})"
    return cell_id


if "cell_id" in gdf.columns:
    gdf["display_name"] = gdf["cell_id"].apply(_get_display_name)
else:
    gdf["display_name"] = gdf.index.astype(str)

# Merge EHI into GDF for choropleth layer (if intelligence data available)
if env_intel:
    ehi_map = {cid: v.get("environmental_health", np.nan) for cid, v in env_intel.items()}
    if "cell_id" in gdf.columns:
        gdf["environmental_health"] = gdf["cell_id"].map(ehi_map)

# Merge priority_score into GDF for choropleth layer (if planning data available)
if planning_profiles:
    priority_map = {cid: v.get("priority_score", np.nan) for cid, v in planning_profiles.items()}
    if "cell_id" in gdf.columns:
        gdf["planning_priority_score"] = gdf["cell_id"].map(priority_map)

st.sidebar.write(f"✅ Loaded {len(gdf)} grid cells")
if env_intel:
    st.sidebar.write(f"🧠 Environmental intelligence: {len(env_intel)} cells enriched")
else:
    st.sidebar.info("ℹ️ Run the pipeline to generate environmental intelligence data.")
if planning_profiles:
    st.sidebar.write(f"🏗️ Planning profiles: {len(planning_profiles)} cells")
else:
    st.sidebar.info("ℹ️ Run the pipeline to generate planning profiles.")

# ------------------------------------------------------------------------------
# 2. Summary statistics bar
# ------------------------------------------------------------------------------
if not gdf.empty:
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Cells", len(gdf))

    # Use EHI if available, fall back to risk score
    if env_intel and "environmental_health" in gdf.columns:
        avg_ehi = gdf["environmental_health"].mean()
        col2.metric("Avg Environmental Health", f"{avg_ehi:.1f} / 100")
    elif "risk_score" in gdf.columns:
        avg_risk = gdf["risk_score"].mean()
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

    if "cluster" in gdf.columns and "risk_score" in gdf.columns:
        cluster_risk = gdf.groupby("cluster")["risk_score"].mean().idxmax()
        col5.metric("Most At-Risk Cluster", str(cluster_risk))

    # Critical priority cells count (Phase 3)
    if planning_profiles:
        critical_count = sum(
            1 for v in planning_profiles.values()
            if v.get("planning_priority") == "Critical"
        )
        col6.metric("Critical Priority Cells", critical_count)
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
folium.TileLayer("CartoDB Positron", name="Basemap – Light", control=False).add_to(m)
folium.TileLayer("CartoDB dark_matter", name="Basemap – Dark").add_to(m)

# Optional static satellite overlays
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
# 4. Choropleth helper + colour maps
# ------------------------------------------------------------------------------

def add_choropleth(
    base_gdf: gpd.GeoDataFrame,
    column: str,
    name: str,
    color_map: Callable[[float], str],
    tooltip_fields: list[str] | None = None,
    fill_opacity: float = 0.7,
) -> folium.GeoJson | None:
    """Add a GeoJson choropleth layer to the global map *m*."""
    valid_gdf = base_gdf.dropna(subset=[column])
    if len(valid_gdf) == 0:
        return None

    vmin = float(valid_gdf[column].min())
    vmax = float(valid_gdf[column].max())

    def style_function(feature: dict[str, Any]) -> dict[str, Any]:
        value = feature["properties"].get(column)
        if value is None:
            return {"fillColor": "#cccccc", "color": "#999999", "weight": 0.5, "fillOpacity": 0}
        ratio = 0.5 if vmax == vmin else (value - vmin) / (vmax - vmin)
        return {
            "fillColor": color_map(ratio),
            "color": "#555555",
            "weight": 0.5,
            "fillOpacity": fill_opacity,
        }

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
        show=False,
    )
    layer.add_to(m)
    return layer


def risk_color(ratio: float) -> str:
    """Green-to-red for risk (high ratio = high risk = red)."""
    if ratio > 0.5:
        r, g = 255, int(255 * (1 - (ratio - 0.5) * 2))
    else:
        r, g = int(255 * ratio * 2), 255
    return f"#{r:02x}{g:02x}00"


def sustainability_color(ratio: float) -> str:
    """Red-to-green for sustainability (high ratio = high sustainability = green)."""
    if ratio > 0.5:
        g, r = 255, int(255 * (1 - (ratio - 0.5) * 2))
    else:
        g, r = int(255 * ratio * 2), 255
    return f"#{r:02x}{g:02x}00"


def ndvi_color(ratio: float) -> str:
    """Brown-to-green for NDVI."""
    r = int(150 - max(0.0, ratio - 0.5) * 300) if ratio >= 0.5 else 150
    g = 255 if ratio >= 0.5 else int(150 + ratio * 210)
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}00"


def lst_color(ratio: float) -> str:
    """Blue-to-red for surface temperature."""
    return f"#{int(ratio*255):02x}00{int((1-ratio)*255):02x}"


def ndbi_color(ratio: float) -> str:
    """Grey-pink for built-up index."""
    r = int(180 + ratio * 75)
    g = int(130 + ratio * 50)
    return f"#{r:02x}{g:02x}{g:02x}"


def dem_color(ratio: float) -> str:
    """Terrain colour for elevation."""
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
    """Diverging blue-to-red for UHI intensity."""
    if ratio < 0.5:
        r, g, b = int(ratio * 2 * 200), int(ratio * 2 * 100), 255
    else:
        r, g, b = 255, int((1 - (ratio - 0.5) * 2) * 100), int((1 - (ratio - 0.5) * 2) * 200)
    return f"#{r:02x}{g:02x}{b:02x}"


# Environmental Health: high EHI = green (reuse sustainability_color)
ehi_color = sustainability_color

# Add all available choropleth layers
col_layers: dict[str, tuple[str, Callable]] = {
    "planning_priority_score": ("Planning Priority Score", risk_color),
    "environmental_health":  ("Environmental Health (EHI)", ehi_color),
    "risk_score":            ("Risk Score", risk_color),
    "sustainability_score":  ("Sustainability Score", sustainability_color),
    "mean_ndvi":             ("NDVI", ndvi_color),
    "mean_lst":              ("LST (°C)", lst_color),
    "mean_ndbi":             ("NDBI", ndbi_color),
    "mean_dem":              ("DEM (m)", dem_color),
    "uhi_intensity":         ("UHI Intensity", uhi_color),
}
for col, (label, cmap) in col_layers.items():
    if col in gdf.columns:
        add_choropleth(gdf, col, label, cmap)

# Cluster layer (categorical colours)
if "cluster" in gdf.columns:
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors

    clusters = gdf["cluster"].dropna().unique()
    colors = cm.tab10(np.linspace(0, 1, len(clusters)))
    cluster_color_dict = {
        cl: mcolors.rgb2hex(colors[i]) for i, cl in enumerate(sorted(clusters))
    }

    def cluster_style(feature: dict[str, Any]) -> dict[str, Any]:
        """Categorical colour per cluster."""
        cl = feature["properties"].get("cluster")
        return {
            "fillColor": cluster_color_dict.get(cl, "#cccccc"),
            "color": "#333333",
            "weight": 0.5,
            "fillOpacity": 0.7,
        }

    folium.GeoJson(
        gdf,
        name="Clusters",
        style_function=cluster_style,
        tooltip=folium.GeoJsonTooltip(fields=["cluster"], aliases=["Cluster"]),
        show=False,
    ).add_to(m)

# Transparent interactive layer for click detection
folium.GeoJson(
    gdf,
    name="Clickable Grid (transparent)",
    style_function=lambda x: {
        "fillColor": "#000000", "color": "#000000", "weight": 0, "fillOpacity": 0,
    },
    highlight_function=lambda x: {"weight": 3, "color": "#FF0000", "fillOpacity": 0.3},
    tooltip=folium.GeoJsonTooltip(fields=["display_name"], aliases=["Location"]),
    zoom_on_click=True,
).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
Fullscreen().add_to(m)

# ------------------------------------------------------------------------------
# 5. Render map
# ------------------------------------------------------------------------------
st.markdown("### Interactive Map")
map_data = st_folium(m, width=1200, height=650, returned_objects=["last_object_clicked"])

# ------------------------------------------------------------------------------
# 6. Sidebar helpers
# ------------------------------------------------------------------------------

def _render_status_badge(status: str) -> None:
    """Render the environmental status label using an appropriate Streamlit call."""
    color_type = STATUS_COLORS.get(status, "info")
    msg = f"**Environmental Status: {status}**"
    if color_type == "success":
        st.success(msg)
    elif color_type == "warning":
        st.warning(msg)
    else:
        st.error(msg)


def _render_comparison_row(
    label: str,
    value: float,
    unit: str,
    vs_avg: float,
    rank: float,
    pct_diff: float,
) -> None:
    """Render one indicator comparison row using st.metric with delta."""
    c1, c2 = st.columns([3, 2])
    with c1:
        delta_str = f"{vs_avg:+.2f}{unit} vs city avg"
        st.metric(label=label, value=f"{value:.2f}{unit}", delta=delta_str)
    with c2:
        st.caption(f"City rank: **{rank:.0f}th** percentile")
        diff_sign = "above" if pct_diff >= 0 else "below"
        st.caption(f"{abs(pct_diff):.0f}% {diff_sign} city average")


def _render_conditions_tags(conditions: list[str]) -> None:
    """Render detected environmental conditions as labelled pills."""
    if not conditions:
        st.write("No critical environmental conditions detected.")
        return

    # Colour-code by condition type
    _condition_styles = {
        "Urban Heat Island":    "🔥",
        "Low Vegetation":       "🌱",
        "High Built-up Density":"🏢",
        "Flood Susceptibility": "💧",
        "Environmental Stress": "⚠️",
        "Ecological Stability": "✅",
    }
    for cond in conditions:
        icon = _condition_styles.get(cond, "•")
        st.write(f"{icon} {cond}")

def _render_environmental_intelligence_panel(
    cell: pd.Series,
    ei: dict,
) -> None:
    """Render the full Phase 2 Environmental Intelligence panel in the sidebar."""

    ehi    = ei.get("environmental_health", 50.0)
    status = ei.get("environmental_status", "Unknown")

    # ── Environmental Health ──────────────────────────────────────────────
    st.markdown("### 🌿 Environmental Health")
    st.metric(label="Environmental Health Index", value=f"{ehi:.1f} / 100")
    _render_status_badge(status)

    # ── Environmental Issues ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔥 Environmental Issues")
    conditions: list[str] = ei.get("detected_conditions", [])
    primary   = ei.get("primary_issue")
    secondary = ei.get("secondary_issue")
    _render_conditions_tags(conditions)
    if primary:
        st.caption(f"Primary issue: **{primary}**")
    if secondary:
        st.caption(f"Secondary issue: **{secondary}**")

    # ── Comparative Analysis ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📈 Comparative Analysis")

    lst_val  = float(cell.get("mean_lst", 0) or 0)
    ndvi_val = float(cell.get("mean_ndvi", 0) or 0)
    ndbi_val = float(cell.get("mean_ndbi", 0) or 0)
    uhi_val  = float(cell.get("uhi_intensity", 0) or 0)

    comparisons = [
        ("🌡️ Surface Temp",  lst_val,  "°C", ei.get("mean_lst_vs_city_avg", 0),
         ei.get("city_rank_lst", 50),   ei.get("mean_lst_pct_diff", 0)),
        ("🌿 Vegetation",    ndvi_val, "",   ei.get("mean_ndvi_vs_city_avg", 0),
         ei.get("city_rank_ndvi", 50),  ei.get("mean_ndvi_pct_diff", 0)),
        ("🏢 Built-up",      ndbi_val, "",   ei.get("mean_ndbi_vs_city_avg", 0),
         ei.get("city_rank_ndbi", 50),  ei.get("mean_ndbi_pct_diff", 0)),
        ("🔥 UHI Intensity", uhi_val,  "°C", ei.get("uhi_intensity_vs_city_avg", 0),
         ei.get("city_rank_uhi", 50),   ei.get("uhi_intensity_pct_diff", 0)),
    ]
    for label, val, unit, vs_avg, rank, pct_diff in comparisons:
        _render_comparison_row(label, val, unit, vs_avg, rank, pct_diff)

    # ── Environmental Summary ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🧠 Environmental Summary")
    summary = ei.get("environmental_summary", "")
    if summary:
        st.info(summary)
    else:
        st.write("No summary available.")

    # ── Spatial Context ───────────────────────────────────────────────────
    spatial_ctx = ei.get("spatial_context", "")
    if spatial_ctx:
        st.markdown("### 📊 Spatial Context")
        st.write(spatial_ctx)

    # ── Cluster (unchanged) ───────────────────────────────────────────────
    st.markdown("---")
    cluster_val = cell.get("cluster_label") or cell.get("cluster")
    if cluster_val:
        st.markdown(f"**Urban Typology:** {cluster_val}")

def _render_raw_indicators_expander(cell: pd.Series) -> None:
    """Render raw indicator values inside a collapsed expander."""
    with st.expander("📋 Raw Indicators", expanded=False):
        indicators = {
            "mean_ndvi":     "🌿 NDVI",
            "mean_lst":      "🌡️ LST (°C)",
            "mean_ndbi":     "🏢 NDBI",
            "mean_dem":      "⛰️ DEM (m)",
            "uhi_intensity": "🔥 UHI Intensity (°C)",
        }
        for col_name, label in indicators.items():
            val = cell.get(col_name)
            if val is not None:
                try:
                    st.write(f"{label}: **{float(val):.3f}**")
                except (ValueError, TypeError):
                    st.write(f"{label}: {val}")

        if "risk_score" in cell:
            st.metric("Risk Score", f"{cell['risk_score']:.2f}")
        if "sustainability_score" in cell:
            st.metric("Sustainability Score", f"{cell['sustainability_score']:.2f}")


def _render_legacy_environmental_panel(cell: pd.Series) -> None:
    """Fallback: render the original raw metrics panel when Phase 2 data is absent."""
    st.markdown("### 📊 Environmental Analysis")
    st.info("💡 Run 'Generate environmental intelligence' pipeline stage for full analysis.")

    if "risk_score" in cell:
        st.metric("Risk Score", f"{cell['risk_score']:.2f}")
    if "sustainability_score" in cell:
        st.metric("Sustainability Score", f"{cell['sustainability_score']:.2f}")
    cluster_val = cell.get("cluster_label") or cell.get("cluster")
    if cluster_val:
        st.markdown(f"**Cluster:** {cluster_val}")

    indicators = {
        "mean_ndvi":     "🌿 NDVI",
        "mean_lst":      "🌡️ LST (°C)",
        "mean_ndbi":     "🏢 NDBI",
        "mean_dem":      "⛰️ DEM (m)",
        "uhi_intensity": "🔥 UHI Intensity",
    }
    for col_name, label in indicators.items():
        val = cell.get(col_name)
        if val is not None:
            try:
                st.write(f"{label}: **{float(val):.3f}**")
            except (ValueError, TypeError):
                st.write(f"{label}: {val}")


def _render_planning_profile_panel(pp: dict) -> None:
    """Render the Phase 3 Planning Profile panel in the sidebar."""

    priority_label = pp.get("planning_priority", "Medium")
    priority_score = pp.get("priority_score", 0.0)
    color_type     = get_priority_color(priority_label)

    # ── Planning Priority ─────────────────────────────────────────────────
    st.markdown("### 🚨 Planning Priority")
    priority_msg = f"**Priority: {priority_label}**"
    if color_type == "error":
        st.error(priority_msg)
    elif color_type == "warning":
        st.warning(priority_msg)
    else:
        st.success(priority_msg)
    st.metric(label="Priority Score", value=f"{priority_score:.1f} / 100")

    # ── Planning Objective ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🎯 Planning Objective")
    st.write(f"**{pp.get('primary_objective', 'Environmental Management')}**")

    # ── Recommended Intervention ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🏗️ Recommended Intervention")
    st.markdown(f"**{pp.get('recommended_intervention', 'Environmental Monitoring')}**")

    secondary: list[str] = pp.get("secondary_interventions", [])
    if secondary:
        st.caption("Supporting interventions:")
        for s in secondary:
            st.write(f"  • {s}")

    # ── Expected Benefits ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📈 Expected Benefits")
    benefits: list[str] = pp.get("expected_benefits", [])
    for b in benefits:
        st.write(f"  ✓ {b}")

    # ── Implementation Details ────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💰 Implementation Details")
    c1, c2, c3 = st.columns(3)
    c1.metric("Cost",       pp.get("implementation_cost",       "—"))
    c2.metric("Timeline",   pp.get("implementation_timeline",   "—"))
    c3.metric("Complexity", pp.get("implementation_complexity", "—"))

    # ── Why this recommendation? ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🧠 Why this recommendation?")
    evidence = pp.get("evidence", "")
    if evidence:
        st.info(evidence)
    confidence = pp.get("confidence", 0.0)
    st.metric(
        label="Recommendation Confidence",
        value=f"{confidence * 100:.0f}%",
    )

# ------------------------------------------------------------------------------
# 7. Sidebar – cell details
# ------------------------------------------------------------------------------
st.sidebar.header("🔍 Cell Details")
clicked_cell_id: str | None = None

if map_data and map_data.get("last_object_clicked"):
    props = map_data["last_object_clicked"].get("properties", {})
    clicked_cell_id = props.get("cell_id")

if clicked_cell_id is not None:
    cell_row = gdf[gdf["cell_id"] == clicked_cell_id]
    if not cell_row.empty:
        cell = cell_row.iloc[0]

        with st.sidebar:
            # ── Geographic Profile (unchanged) ────────────────────────────
            if geo_meta and clicked_cell_id in geo_meta:
                gm = geo_meta[clicked_cell_id]
                st.markdown("### 📍 Geographic Profile")
                st.markdown(
                    f"**{gm.get('primary_locality', 'Unknown')}** "
                    f"(Grid {gm.get('grid_id', clicked_cell_id)})"
                )
                ward = gm.get("ward", "Unknown Ward")
                zone = gm.get("zone", "Unknown Zone")
                st.markdown(f"📌 {ward} | {zone}")
                st.markdown(f"🏘️ {gm.get('dominant_land_use', 'Unknown')}")

                pop = gm.get("population", 0)
                if pop and pop > 0:
                    st.markdown(f"👥 Population: ~{pop:,}")
                else:
                    st.markdown("👥 Population: Minimal/Uninhabited")

                secondary = gm.get("secondary_localities", [])
                if secondary:
                    st.markdown("**📍 Nearby Areas**")
                    for s in secondary[:3]:
                        st.markdown(f"  • {s}")

                landmarks = gm.get("nearest_landmarks", [])
                if landmarks:
                    st.markdown("**🏛️ Nearby Landmarks**")
                    for lm in landmarks:
                        st.markdown(f"  • {lm['name']} ({lm['distance_km']} km)")

                lat, lon = gm.get("centroid_lat"), gm.get("centroid_lon")
                if lat and lon:
                    st.markdown("**🌐 Coordinates**")
                    st.markdown(f"{lat}°N, {lon}°E")
                    st.markdown(
                        f"[🔗 Google Maps](https://www.google.com/maps/search/?api=1&query={lat},{lon})"
                        f" | "
                        f"[🔗 OpenStreetMap](https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon})"
                    )
            else:
                st.markdown(f"### Cell `{clicked_cell_id}`")
                st.info("💡 Run geographic enrichment to see locality details.")

            st.markdown("---")

            # ── Environmental Intelligence panel OR legacy fallback ────────
            ei = env_intel.get(clicked_cell_id) if env_intel else None
            if ei:
                _render_environmental_intelligence_panel(cell, ei)
                _render_raw_indicators_expander(cell)
            else:
                _render_legacy_environmental_panel(cell)

            # ── AI Explanation (SHAP – unchanged) ─────────────────────────
            if clicked_cell_id in explanations:
                explain = explanations[clicked_cell_id]
                explanation_text = explain.get("explanation_text", "")
                st.markdown("---")
                st.markdown("**🧠 AI Explanation**")
                st.info(explanation_text or "No explanation available.")

                top_pos = explain.get("top_positive_driver")
                top_neg = explain.get("top_negative_driver")
                if top_pos and top_pos.get("feature"):
                    st.write(
                        f"↑ **Positive driver:** {top_pos['feature']} "
                        f"(SHAP {top_pos.get('shap_value', 0):.3f})"
                    )
                if top_neg and top_neg.get("feature"):
                    st.write(
                        f"↓ **Negative driver:** {top_neg['feature']} "
                        f"(SHAP {top_neg.get('shap_value', 0):.3f})"
                    )

            # ── Planning Profile (Phase 3) or legacy recommendation ────────
            st.markdown("---")
            pp = planning_profiles.get(clicked_cell_id) if planning_profiles else None
            if pp:
                _render_planning_profile_panel(pp)
            else:
                st.markdown("**💡 Recommendation**")
                st.info(
                    "💡 Run 'Generate planning profiles' pipeline stage "
                    "for full planning recommendations."
                )
                rec: list[str] = []
                ndvi_val  = cell.get("mean_ndvi") or 0
                lst_val   = cell.get("mean_lst")  or 0
                dem_val   = cell.get("mean_dem")  or 0
                ndbi_val  = cell.get("mean_ndbi") or 0
                thresholds = CONFIG["dashboard"]["thresholds"]
                if ndvi_val < thresholds["low_ndvi"] and lst_val > thresholds["high_lst"]:
                    rec.append("🌳 Increase green cover (low NDVI, high temperature).")
                if dem_val < thresholds["low_dem"]:
                    rec.append("💧 Elevation risk – improve drainage and flood protection.")
                if ndbi_val > thresholds["high_ndbi"]:
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
st.caption("City Sense Dashboard – Phase 3 | Built with Streamlit, Folium, and Geopandas")
