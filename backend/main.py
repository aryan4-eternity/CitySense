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
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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

# Pre-build fast lookup: cell_id → GeoJSON feature properties
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
    """Full GeoJSON FeatureCollection for Deck.gl map layer.

    Returns the complete cells_master.geojson so the frontend can render
    the choropleth without any additional requests.
    """
    return _cells_geojson


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


@app.get("/health")
def health() -> dict:
    """Simple health check for the frontend to verify the API is reachable."""
    return {"status": "ok", "cells": len(_cell_props)}
