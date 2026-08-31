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
    geo_meta = {
        # Centroid of the cell containing (19.05, 72.88)
        "r16_c10": {"centroid_lat": 19.055, "centroid_lon": 72.885},
    }
    assert coords_to_cell_id(19.05, 72.88, geo_meta) == "r16_c10"
    # Outside MMR coverage bounds → no cell
    assert coords_to_cell_id(20.05, 72.88, geo_meta) is None

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
        "geo_meta": {
            "r16_c10": {"centroid_lat": 19.055, "centroid_lon": 72.885},
        },
    }
    result = dispatch_tool("find_cell_by_coordinates", {"lat": 19.05, "lon": 72.88}, mock_data)
    assert result["cell_id"] == "r16_c10"
    assert result["master"]["risk_score"] == 75


def test_dispatch_tool_search_cells_by_location_and_condition():
    mock_data = {
        "cell_props": {
            "r17_c8": {"risk_score": 77.3},
            "r15_c3": {"risk_score": 9.3},
        },
        "geo_meta": {
            "r17_c8": {"primary_locality": "Bandra East", "ward": "H/East Ward", "secondary_localities": []},
            "r15_c3": {"primary_locality": "Bandra West", "ward": "H/West Ward", "secondary_localities": []},
            "r20_c5": {"primary_locality": "Andheri West", "ward": "K/West Ward", "secondary_localities": []},
        },
        "env_intel": {
            "r17_c8": {"primary_issue": "Urban Heat Island", "detected_conditions": ["Urban Heat Island"]},
            "r15_c3": {"primary_issue": None, "detected_conditions": []},
        },
        "fsi_data": {
            "r17_c8": {"flood_susceptibility_score": 89.43, "flood_susceptibility_status": "Severe"},
            "r15_c3": {"flood_susceptibility_score": 86.30, "flood_susceptibility_status": "Severe"},
        },
        "plans": {
            "r17_c8": {"planning_priority": "High", "recommended_intervention": "Cool Roof Program"},
            "r15_c3": {"planning_priority": "Low", "recommended_intervention": "Drainage Infrastructure Upgrade"},
        },
        "iai_data": {},
        "burden_data": {},
    }

    # 1. Location search only
    loc_results = dispatch_tool("search_cells_by_location", {"location": "Bandra"}, mock_data)
    assert len(loc_results) == 2
    cell_ids = [r["cell_id"] for r in loc_results]
    assert "r17_c8" in cell_ids and "r15_c3" in cell_ids

    # 2. Location search with flood condition
    flood_results = dispatch_tool("search_cells_by_location", {"location": "Bandra", "condition": "Flood Susceptibility"}, mock_data)
    assert len(flood_results) == 2
    assert flood_results[0]["flood_susceptibility_status"] == "Severe"

    # 3. Condition search with location filter
    cond_results = dispatch_tool("search_cells_by_condition", {"condition": "flood", "location": "Bandra"}, mock_data)
    assert len(cond_results) == 2

