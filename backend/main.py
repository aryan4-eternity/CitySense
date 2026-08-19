"""
CitySense FastAPI Backend
=========================
Serves the four pipeline output files as REST endpoints.
No database, no computation — pure file serving with CORS.

Run:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Load .env from the backend directory (GEMINI_API_KEY lives here)
load_dotenv(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CitySense API",
    description="Environmental intelligence and planning data for Mumbai",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Data loading — loaded once at startup
# ---------------------------------------------------------------------------

_DATA = Path(__file__).parent.parent / "data"


def _load(filename: str) -> Any:
    path = _DATA / filename
    if not path.exists():
        raise RuntimeError(f"Data file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# Load all files at module level (startup)
_cells_geojson: dict = _load("cells_master.geojson")
_env_intel: dict     = _load("environmental_intelligence.json")
_plans: dict         = _load("planning_profiles.json")

# ward_profiles.json — loaded with graceful fallback if not yet generated
_ward_profiles: dict = {}
_ward_profiles_path  = _DATA / "ward_profiles.json"
if _ward_profiles_path.exists():
    _ward_profiles = json.loads(_ward_profiles_path.read_text(encoding="utf-8"))
    print(f"[CitySense API] Ward profiles: {len(_ward_profiles)} wards loaded")

# flood_susceptibility.json — loaded with graceful fallback
_fsi_data: dict = {}
_fsi_path = _DATA / "flood_susceptibility.json"
if _fsi_path.exists():
    _fsi_data = json.loads(_fsi_path.read_text(encoding="utf-8"))
    print(f"[CitySense API] Flood susceptibility: {len(_fsi_data)} cells loaded")

# infrastructure_access_index.json — loaded with graceful fallback
_iai_data: dict = {}
_iai_path = _DATA / "infrastructure_access_index.json"
if _iai_path.exists():
    _iai_data = json.loads(_iai_path.read_text(encoding="utf-8"))
    print(f"[CitySense API] Infrastructure access index: {len(_iai_data)} cells loaded")

# composite_burden.json — loaded with graceful fallback
_burden_data: dict = {}
_burden_path = _DATA / "composite_burden.json"
if _burden_path.exists():
    _burden_data = json.loads(_burden_path.read_text(encoding="utf-8"))
    print(f"[CitySense API] Composite burden: {len(_burden_data)} cells loaded")

# geographic_metadata.json — locality names, wards, coordinates per cell
_geo_meta: dict = {}
_geo_meta_path = _DATA / "geo" / "geographic_metadata.json"
if _geo_meta_path.exists():
    _geo_meta = json.loads(_geo_meta_path.read_text(encoding="utf-8"))
    print(f"[CitySense API] Geographic metadata: {len(_geo_meta)} cells loaded")

# cell_explanations.json can be a list or dict depending on pipeline version
_explanations_raw = _load("cell_explanations.json")
if isinstance(_explanations_raw, list):
    # Normalise list → dict keyed by cell_id
    _explanations: dict = {
        item["cell_id"]: item
        for item in _explanations_raw
        if isinstance(item, dict) and "cell_id" in item
    }
else:
    _explanations = _explanations_raw


# ---------------------------------------------------------------------------
# Land / water classification — filter sea cells at the data layer
# ---------------------------------------------------------------------------

def _is_land_cell(props: dict) -> bool:
    """Return True if the cell is on land, False if it is water/sea.

    Reads the `is_water` boolean pre-computed at startup rather than
    re-deriving from raw ndvi/dem values, so the threshold is authoritative
    in one place (_WATER_NDVI_MAX / _WATER_DEM_MAX above).
    """
    # Fast path: use the pre-computed flag if available
    if "is_water" in props:
        return not props["is_water"]
    # Fallback for cells that somehow lack the flag (should not occur)
    ndvi = props.get("mean_ndvi")
    dem  = props.get("mean_dem")
    if ndvi is None or dem is None:
        return False
    import math
    if math.isnan(ndvi) or math.isnan(dem):
        return False
    if ndvi < _WATER_NDVI_MAX and dem < _WATER_DEM_MAX:
        return False
    return True


_total_before = len(_cells_geojson["features"])

# Annotate every feature with is_water so the frontend has a single
# authoritative boolean rather than re-deriving from ndvi/dem thresholds.
# Threshold: ndvi < 0.05 AND dem < 3.5 — catches open ocean, turbid coastal
# water, and tidal flats that are meaningless for urban environmental analysis.
# This is the loosened threshold validated during dashboard development
# (original land_use_classifier uses dem < 2.0 and ndvi < 0.0; the broader
# values here reduce false negatives for turbid nearshore pixels).
_WATER_NDVI_MAX = 0.05
_WATER_DEM_MAX  = 3.5

for _feat in _cells_geojson["features"]:
    _p = _feat.get("properties", {})
    _ndvi = _p.get("mean_ndvi")
    _dem  = _p.get("mean_dem")
    import math as _math
    _is_water = (
        _ndvi is None or _dem is None
        or (_math.isnan(float(_ndvi)) if isinstance(_ndvi, float) else False)
        or (_math.isnan(float(_dem))  if isinstance(_dem,  float) else False)
        or (float(_ndvi) < _WATER_NDVI_MAX and float(_dem) < _WATER_DEM_MAX)
    )
    _feat["properties"]["is_water"] = _is_water

    # Merge FSI score so the frontend choropleth can colour by flood susceptibility
    _cid = _p.get("cell_id")
    if _cid and _cid in _fsi_data:
        _feat["properties"]["flood_susceptibility_score"] = (
            _fsi_data[_cid].get("flood_susceptibility_score")
        )
    # Merge IAI and burden scores for their choropleth layers
    if _cid and _cid in _iai_data:
        _feat["properties"]["iai_score"] = _iai_data[_cid].get("iai_score")
    if _cid and _cid in _burden_data:
        _feat["properties"]["burden_score"] = _burden_data[_cid].get("burden_score")

# Build a land-only GeoJSON for the map endpoint
_cells_land_geojson: dict = {
    "type": "FeatureCollection",
    "features": [
        f for f in _cells_geojson["features"]
        if _is_land_cell(f.get("properties", {}))
    ],
}

_total_after = len(_cells_land_geojson["features"])
print(f"[CitySense API] Filtered {_total_before - _total_after} water cells "
      f"({_total_before} -> {_total_after} land cells)")

# Pre-build fast lookup: cell_id → GeoJSON feature properties (all cells)
_cell_props: dict[str, dict] = {
    f["properties"]["cell_id"]: f["properties"]
    for f in _cells_geojson["features"]
    if "cell_id" in f.get("properties", {})
}

print(f"[CitySense API] Loaded {len(_cell_props)} cells")
print(f"[CitySense API] Environmental intelligence: {len(_env_intel)} cells")
print(f"[CitySense API] Planning profiles: {len(_plans)} cells")
print(f"[CitySense API] Explanations: {len(_explanations)} cells")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/cells")
def get_cells() -> dict:
    """Land-only GeoJSON FeatureCollection for Deck.gl map layer.

    Returns cells_master.geojson with water/sea cells removed so the
    frontend renders a clean landmass-only choropleth.
    """
    return _cells_land_geojson


@app.get("/api/cell/{cell_id}")
def get_cell(cell_id: str) -> dict:
    """Complete data bundle for the sidebar detail panel.

    Merges master properties, environmental intelligence, planning profile,
    and SHAP explanation into a single response object.
    """
    if cell_id not in _cell_props:
        raise HTTPException(status_code=404, detail=f"Cell '{cell_id}' not found")

    return {
        "master":      _cell_props[cell_id],
        "environment": _env_intel.get(cell_id, {}),
        "planning":    _plans.get(cell_id, {}),
        "explanation": _explanations.get(cell_id, {}),
        "flood":       _fsi_data.get(cell_id, {}),
        "access":      _iai_data.get(cell_id, {}),
        "burden":      _burden_data.get(cell_id, {}),
    }


@app.get("/api/rankings")
def get_rankings() -> list[dict]:
    """All cells sorted by priority_score descending.

    Used by the StatsPanel top-5 list and any future ranking table.
    Merges planning priority with master indicator values for richer rows.
    """
    rows: list[dict] = []
    for cell_id, plan in _plans.items():
        master = _cell_props.get(cell_id, {})
        ei = _env_intel.get(cell_id, {})
        rows.append({
            "cell_id":           cell_id,
            "planning_priority": plan.get("planning_priority", "Unknown"),
            "priority_score":    plan.get("priority_score", 0.0),
            "recommended_intervention": plan.get("recommended_intervention", ""),
            "environmental_health": plan.get("environmental_health",
                                    ei.get("environmental_health", 50.0)),
            "risk_score":        master.get("risk_score", 0.0),
            "mean_lst":          master.get("mean_lst", 0.0),
            "mean_ndvi":         master.get("mean_ndvi", 0.0),
            "cluster":           master.get("cluster", ""),
            "primary_issue":     ei.get("primary_issue"),
        })

    rows.sort(key=lambda r: r["priority_score"], reverse=True)
    return rows


@app.get("/api/stats")
def get_stats() -> dict:
    """City-wide aggregate statistics for the header and StatsPanel.

    Computes summary numbers from the loaded data without re-reading files.
    """
    # EHI stats
    ehi_vals = [
        v["environmental_health"]
        for v in _env_intel.values()
        if isinstance(v.get("environmental_health"), (int, float))
    ]
    avg_ehi = round(sum(ehi_vals) / len(ehi_vals), 1) if ehi_vals else 0.0
    min_ehi = round(min(ehi_vals), 1) if ehi_vals else 0.0
    max_ehi = round(max(ehi_vals), 1) if ehi_vals else 0.0

    # Priority distribution
    priority_counts: dict[str, int] = {}
    for v in _plans.values():
        p = v.get("planning_priority", "Unknown")
        priority_counts[p] = priority_counts.get(p, 0) + 1

    # Top environmental issues
    issue_counts: dict[str, int] = {}
    for v in _env_intel.values():
        issue = v.get("primary_issue")
        if issue:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:6]

    # Top interventions
    intervention_counts: dict[str, int] = {}
    for v in _plans.values():
        iv = v.get("recommended_intervention", "")
        if iv:
            intervention_counts[iv] = intervention_counts.get(iv, 0) + 1
    top_interventions = sorted(
        intervention_counts.items(), key=lambda x: x[1], reverse=True
    )[:5]

    # Risk score stats
    risk_vals = [
        p.get("risk_score", 0.0)
        for p in _cell_props.values()
        if isinstance(p.get("risk_score"), (int, float))
    ]
    avg_risk = round(sum(risk_vals) / len(risk_vals), 1) if risk_vals else 0.0

    # Environmental status distribution
    status_counts: dict[str, int] = {}
    for v in _env_intel.values():
        s = v.get("environmental_status", "Unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "total_cells":       len(_cell_props),
        "avg_ehi":           avg_ehi,
        "min_ehi":           min_ehi,
        "max_ehi":           max_ehi,
        "avg_risk":          avg_risk,
        "priority_counts":   priority_counts,
        "status_counts":     status_counts,
        "top_issues":        [{"issue": k, "count": v} for k, v in top_issues],
        "top_interventions": [{"intervention": k, "count": v} for k, v in top_interventions],
    }


@app.get("/api/wards")
def get_wards() -> dict:
    """Ward-level aggregated planning summaries.

    Returns a dict keyed by ward name, each containing:
      - dominant_intervention, dominant_issue, dominant_priority
      - priority_score_mean, priority_score_max
      - priority_distribution, intervention_counts, issue_counts
      - avg_ehi, avg_risk_score
      - total_cells, high_priority_cells
      - ward_population, zone, planning_summary

    Sorted by priority_score_mean descending so the highest-priority
    wards appear first.

    Returns 503 if ward_profiles.json has not been generated yet.
    """
    if not _ward_profiles:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail=(
                "Ward profiles not yet generated. "
                "Run: python -m metadata.ward_aggregation"
            ),
        )
    sorted_wards = dict(
        sorted(
            _ward_profiles.items(),
            key=lambda x: x[1].get("priority_score_mean", 0),
            reverse=True,
        )
    )
    return sorted_wards


@app.get("/api/wards/{ward_name}")
def get_ward(ward_name: str) -> dict:
    """Planning summary for a single ward by name (e.g. 'L Ward').

    Ward names are case-sensitive and match the keys in ward_profiles.json.
    """
    if not _ward_profiles:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Ward profiles not yet generated.")
    if ward_name not in _ward_profiles:
        from fastapi import HTTPException
        available = list(_ward_profiles.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Ward '{ward_name}' not found. Available: {available}",
        )
    return _ward_profiles[ward_name]


@app.get("/health")
def health() -> dict:
    """Simple health check for the frontend to verify the API is reachable."""
    return {"status": "ok", "cells": len(_cell_props)}


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------

from backend.chat import ChatRequest, ChatResponse, handle_chat


def _build_app_data() -> dict:
    """Bundle all in-memory data into a single dict for the chat handler."""
    # Build stats inline (same logic as get_stats) so we don't repeat HTTP calls
    ehi_vals = [
        v["environmental_health"]
        for v in _env_intel.values()
        if isinstance(v.get("environmental_health"), (int, float))
    ]
    avg_ehi = round(sum(ehi_vals) / len(ehi_vals), 1) if ehi_vals else 0.0

    priority_counts: dict[str, int] = {}
    for v in _plans.values():
        p = v.get("planning_priority", "Unknown")
        priority_counts[p] = priority_counts.get(p, 0) + 1

    issue_counts: dict[str, int] = {}
    for v in _env_intel.values():
        issue = v.get("primary_issue")
        if issue:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:6]

    intervention_counts: dict[str, int] = {}
    for v in _plans.values():
        iv = v.get("recommended_intervention", "")
        if iv:
            intervention_counts[iv] = intervention_counts.get(iv, 0) + 1
    top_interventions = sorted(
        intervention_counts.items(), key=lambda x: x[1], reverse=True
    )[:5]

    risk_vals = [
        p.get("risk_score", 0.0)
        for p in _cell_props.values()
        if isinstance(p.get("risk_score"), (int, float))
    ]
    avg_risk = round(sum(risk_vals) / len(risk_vals), 1) if risk_vals else 0.0

    stats = {
        "total_cells":       len(_cell_props),
        "avg_ehi":           avg_ehi,
        "avg_risk":          avg_risk,
        "priority_counts":   priority_counts,
        "top_issues":        [{"issue": k, "count": v} for k, v in top_issues],
        "top_interventions": [{"intervention": k, "count": v} for k, v in top_interventions],
    }

    return {
        "cell_props":   _cell_props,
        "env_intel":    _env_intel,
        "plans":        _plans,
        "explanations": _explanations,
        "fsi_data":     _fsi_data,
        "iai_data":     _iai_data,
        "burden_data":  _burden_data,
        "ward_profiles": _ward_profiles,
        "geo_meta":     _geo_meta,
        "stats":        stats,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    LLM-powered chat endpoint for CitySense.

    Accepts a conversation history and returns the assistant's reply.
    Optionally returns a cell_id to highlight on the map when a location
    is resolved from a Google Maps URL or coordinates.

    Requires GEMINI_API_KEY environment variable (or backend/.env file).
    """
    app_data = _build_app_data()
    try:
        return handle_chat(request, app_data)
    except HTTPException:
        raise
    except Exception as exc:
        err_msg = str(exc)
        if "503" in err_msg or "UNAVAILABLE" in err_msg:
            return ChatResponse(
                reply="⚠️ The Gemini API is currently experiencing temporary high demand (503). Please wait a few seconds and try your request again."
            )
        raise HTTPException(status_code=500, detail=f"Chat error: {err_msg}")
