"""
environment_templates.py
========================
Single source of truth for all constants, thresholds, and template strings
used by the Phase 2 Environmental Intelligence modules.

Nothing in this module performs computation — it is imported by the other
modules in the ``environment`` package.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Environmental Health Index weights
# ---------------------------------------------------------------------------
# Rationale (Mumbai domain context):
#   Heat stress (LST + UHI) is the dominant urban environmental risk → 50 %
#   Vegetation loss is the primary ecological driver            → 25 %
#   Built-up density amplifies heat and reduces permeability   → 15 %
#   Elevation is a secondary flood-risk proxy                  → 10 %
# All weights sum to 1.0.
EHI_WEIGHTS: dict[str, float] = {
    "mean_lst":      0.30,
    "mean_ndvi":     0.25,
    "uhi_intensity": 0.20,
    "mean_ndbi":     0.15,
    "mean_dem":      0.10,
}

# Indicators where a HIGHER value means WORSE environmental health.
# Used to invert NDVI and DEM before the weighted sum so that
# "higher normalised value = higher risk" for all indicators.
HIGH_IS_BAD: set[str] = {"mean_lst", "uhi_intensity", "mean_ndbi"}
HIGH_IS_GOOD: set[str] = {"mean_ndvi", "mean_dem"}

# ---------------------------------------------------------------------------
# Environmental Status thresholds  (EHI → label)
# ---------------------------------------------------------------------------
# Covers the full [0, 100] range without gaps.
# Each tuple is (lower_bound_inclusive, upper_bound_inclusive, label).
STATUS_THRESHOLDS: list[tuple[float, float, str]] = [
    (80.0, 100.0, "Excellent"),
    (60.0,  79.9, "Good"),
    (40.0,  59.9, "Moderate"),
    (20.0,  39.9, "Poor"),
    (0.0,   19.9, "Critical"),
]

# Convenience mapping used by the dashboard for colour coding
STATUS_COLORS: dict[str, str] = {
    "Excellent": "success",   # st.success  → green
    "Good":      "success",
    "Moderate":  "warning",   # st.warning  → amber
    "Poor":      "error",     # st.error    → red
    "Critical":  "error",
}

# ---------------------------------------------------------------------------
# Condition detection thresholds  (percentile rank, 0–100)
# ---------------------------------------------------------------------------
# city_rank_* conventions used throughout:
#   city_rank_lst   – 100 = hottest cell in the city
#   city_rank_uhi   – 100 = highest UHI intensity
#   city_rank_ndbi  – 100 = most built-up
#   city_rank_ndvi  – 100 = most vegetated   ← NOTE: low rank = low vegetation
#   city_rank_dem   – 100 = highest elevation ← NOTE: low rank = flood risk
#   city_rank_risk  – 100 = highest risk score
CONDITION_THRESHOLDS: dict[str, dict] = {
    "Urban Heat Island": {
        "city_rank_uhi": (">=", 75),
        "city_rank_lst": (">=", 70),
    },
    "Low Vegetation": {
        "city_rank_ndvi": ("<=", 25),
    },
    "High Built-up Density": {
        "city_rank_ndbi": (">=", 75),
    },
    "Flood Susceptibility": {
        "city_rank_dem": ("<=", 20),
    },
    "Environmental Stress": {
        # Evaluated against EHI directly, not a city_rank column.
        # Handled specially in indicator_interpreter.py.
        "_ehi": ("<", 40),
    },
    "Ecological Stability": {
        "_ehi":           (">=", 70),
        "city_rank_ndvi": (">=", 60),
    },
}

# ---------------------------------------------------------------------------
# Summary paragraph templates
# ---------------------------------------------------------------------------
# Keys map to (primary_condition, status_tier) tuples.
# Use Python str.format_map() with a dict of placeholder values.
# Required placeholders for each template are documented inline.
#
# Available placeholders (all optional — use only what fits):
#   {locality}       primary locality name (str)
#   {status}         environmental status label (str)
#   {ehi:.0f}        EHI score (float)
#   {lst_val:.1f}    mean LST in °C (float)
#   {ndvi_val:.3f}   mean NDVI (float)
#   {ndbi_val:.3f}   mean NDBI (float)
#   {uhi_val:.1f}    UHI intensity in °C (float)
#   {dem_val:.0f}    mean DEM in metres (float)
#   {lst_rank:.0f}   city percentile rank for LST (float, 0–100)
#   {ndvi_rank:.0f}  city percentile rank for NDVI (float, 0–100)
#   {ndbi_rank:.0f}  city percentile rank for NDBI (float, 0–100)
#   {uhi_rank:.0f}   city percentile rank for UHI (float, 0–100)
#   {dem_rank:.0f}   city percentile rank for DEM (float, 0–100)
#   {risk_rank:.0f}  city percentile rank for risk score (float, 0–100)

SUMMARY_TEMPLATES: dict[tuple[str, str], str] = {

    # ── Urban Heat Island dominant ──────────────────────────────────────────
    ("Urban Heat Island", "Critical"): (
        "This grid is experiencing a severe Urban Heat Island effect, "
        "with surface temperatures of {lst_val:.1f}°C — hotter than {lst_rank:.0f}% "
        "of all Mumbai grids. Vegetation cover is critically insufficient to provide "
        "meaningful cooling, and dense urban development further amplifies heat "
        "retention. The overall environmental health is critical (EHI: {ehi:.0f}/100)."
    ),
    ("Urban Heat Island", "Poor"): (
        "Elevated surface temperatures ({lst_val:.1f}°C) and a pronounced Urban Heat "
        "Island effect characterise this grid. Built-up density suppresses natural "
        "cooling, and vegetation cover remains well below the city average "
        "(NDVI: {ndvi_val:.3f}). Environmental health is poor (EHI: {ehi:.0f}/100)."
    ),
    ("Urban Heat Island", "Moderate"): (
        "This grid shows moderate Urban Heat Island conditions, with a surface "
        "temperature of {lst_val:.1f}°C. Vegetation is limited, reducing the "
        "natural cooling capacity of the area. These factors combine to produce "
        "moderate environmental health (EHI: {ehi:.0f}/100)."
    ),

    # ── Low Vegetation dominant ─────────────────────────────────────────────
    ("Low Vegetation", "Critical"): (
        "This grid has critically low vegetation cover (NDVI: {ndvi_val:.3f}), "
        "placing it among the least green {ndvi_rank:.0f}% of city grids. "
        "The absence of green infrastructure leaves the area highly vulnerable "
        "to heat stress and ecological degradation. "
        "Environmental health is critical (EHI: {ehi:.0f}/100)."
    ),
    ("Low Vegetation", "Poor"): (
        "Vegetation cover is substantially below the city average (NDVI: {ndvi_val:.3f}), "
        "limiting ecological resilience and natural cooling. Combined with elevated "
        "surface temperatures, this grid shows poor environmental health "
        "(EHI: {ehi:.0f}/100)."
    ),
    ("Low Vegetation", "Moderate"): (
        "Vegetation cover in this grid is below the city median (NDVI: {ndvi_val:.3f}). "
        "While conditions are not critical, the limited green cover reduces "
        "cooling capacity and ecological connectivity. "
        "Environmental health is moderate (EHI: {ehi:.0f}/100)."
    ),

    # ── High Built-up Density dominant ──────────────────────────────────────
    ("High Built-up Density", "Poor"): (
        "This grid is characterised by dense urban development "
        "(NDBI: {ndbi_val:.3f}), which reduces surface permeability and "
        "increases heat retention. Limited green cover compounds these effects, "
        "resulting in poor environmental health (EHI: {ehi:.0f}/100)."
    ),
    ("High Built-up Density", "Moderate"): (
        "Built-up density is notably high in this grid (NDBI: {ndbi_val:.3f}), "
        "reducing permeability and contributing to localised heat buildup. "
        "Environmental health is moderate (EHI: {ehi:.0f}/100)."
    ),

    # ── Flood Susceptibility dominant ───────────────────────────────────────
    ("Flood Susceptibility", "Poor"): (
        "This grid sits at low elevation ({dem_val:.0f} m), placing it among the "
        "bottom {dem_rank:.0f}% of city grids by terrain height. "
        "This increases susceptibility to waterlogging and flooding during "
        "monsoon events. Environmental health is poor (EHI: {ehi:.0f}/100)."
    ),
    ("Flood Susceptibility", "Moderate"): (
        "Relatively low elevation ({dem_val:.0f} m) creates moderate flood "
        "susceptibility in this grid. Combined with dense surface coverage, "
        "drainage may be limited during heavy rainfall. "
        "Environmental health is moderate (EHI: {ehi:.0f}/100)."
    ),

    # ── Healthy / Stable ────────────────────────────────────────────────────
    ("Ecological Stability", "Excellent"): (
        "This grid demonstrates excellent ecological health, with strong "
        "vegetation cover (NDVI: {ndvi_val:.3f}) and moderate surface "
        "temperatures ({lst_val:.1f}°C). Natural cooling is effective and "
        "ecological resilience is high (EHI: {ehi:.0f}/100)."
    ),
    ("Ecological Stability", "Good"): (
        "Environmental conditions in this grid are good. Vegetation cover "
        "is above the city average (NDVI: {ndvi_val:.3f}), contributing to "
        "natural cooling and ecological stability. "
        "Environmental health is good (EHI: {ehi:.0f}/100)."
    ),

    # ── Environmental Stress (catch-all for low-EHI without a specific driver) ─
    ("Environmental Stress", "Poor"): (
        "Multiple environmental stressors are present in this grid, including "
        "elevated temperatures ({lst_val:.1f}°C) and limited vegetation "
        "(NDVI: {ndvi_val:.3f}). These combined pressures result in poor "
        "environmental health (EHI: {ehi:.0f}/100)."
    ),
    ("Environmental Stress", "Critical"): (
        "This grid is under severe environmental stress. Elevated heat, "
        "limited vegetation, and dense urban development combine to produce "
        "critical environmental health conditions (EHI: {ehi:.0f}/100). "
        "Immediate attention is warranted."
    ),
}

# Fallback template when no specific template matches.
SUMMARY_FALLBACK_TEMPLATE: str = (
    "This grid has {status} environmental health (EHI: {ehi:.0f}/100). "
    "Surface temperature is {lst_val:.1f}°C and vegetation cover (NDVI) is {ndvi_val:.3f}."
)

# Spatial context template
# Filled by indicator_interpreter.generate_spatial_context()
SPATIAL_CONTEXT_TEMPLATE: str = (
    "This grid is {lst_context}. {ndvi_context}."
)

# Sub-templates for each component of the spatial context sentence
SPATIAL_LST_TEMPLATES: dict[str, str] = {
    "very_high": "hotter than {lst_rank:.0f}% of all Mumbai grids ({lst_val:.1f}°C)",
    "high":      "above average in temperature ({lst_val:.1f}°C, hotter than {lst_rank:.0f}% of grids)",
    "average":   "near the city average in temperature ({lst_val:.1f}°C)",
    "low":       "cooler than {lst_rank:.0f}% of Mumbai grids ({lst_val:.1f}°C)",
}

SPATIAL_NDVI_TEMPLATES: dict[str, str] = {
    "very_low":  "Vegetation is considerably lower than {ndvi_rank:.0f}% of surrounding grids (NDVI: {ndvi_val:.3f})",
    "low":       "Vegetation cover is below average (NDVI: {ndvi_val:.3f})",
    "average":   "Vegetation is near the city average (NDVI: {ndvi_val:.3f})",
    "high":      "Vegetation cover is above average (NDVI: {ndvi_val:.3f}), placing it in the top {ndvi_pct:.0f}% of the city",
}
