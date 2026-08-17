"""
Tests for CitySense Chat Backend
=================================
Tests tool dispatching, coordinate/Google Maps URL extraction,
and grid cell coordinate mapping.
"""

from backend.chat import (
    extract_coords_from_text,
    coords_to_cell_id,
    dispatch_tool,
    ChatRequest,
    ChatMessage,
)

def test_extract_coords_from_gmaps_url():
    url = "https://www.google.com/maps/@19.05,72.88,15z"
    coords = extract_coords_from_text(url)
    assert coords is not None
    assert abs(coords[0] - 19.05) < 1e-4
    assert abs(coords[1] - 72.88) < 1e-4

def test_extract_bare_coords():
    text = "Check out 19.05, 72.88"
    coords = extract_coords_from_text(text)
    assert coords is not None
    assert abs(coords[0] - 19.05) < 1e-4
    assert abs(coords[1] - 72.88) < 1e-4

def test_coords_to_cell_id():
    cell_id = coords_to_cell_id(19.05, 72.88)
    assert cell_id == "r16_c10"

def test_dispatch_tool_get_city_stats():
    mock_data = {
        "stats": {
            "total_cells": 100,
            "avg_ehi": 55.0,
            "min_ehi": 12.0,
            "max_ehi": 88.0,
            "avg_risk": 45.0,
            "priority_counts": {"Critical": 10},
            "status_counts": {"Healthy": 90},
            "top_issues": [],
            "top_interventions": [],
        }
    }
    result = dispatch_tool("get_city_stats", {}, mock_data)
    assert result["total_cells"] == 100
    assert result["avg_ehi"] == 55.0

def test_dispatch_tool_find_cell_by_coordinates():
    mock_data = {
        "cell_props": {"r16_c10": {"risk_score": 75}},
        "env_intel": {},
        "plans": {},
        "explanations": {},
        "fsi_data": {},
        "iai_data": {},
        "burden_data": {},
    }
    result = dispatch_tool("find_cell_by_coordinates", {"lat": 19.05, "lon": 72.88}, mock_data)
    assert result["cell_id"] == "r16_c10"
    assert result["master"]["risk_score"] == 75
