"""
test_planning_engine.py
=======================
Unit tests for all Phase 3 planning modules.

All tests use synthetic data — no real dataset required.

Coverage
--------
TestKnowledgeBase      (6)  — catalog loading, intervention resolution
TestPriorityEngine     (7)  — score bounds, ordering, labels, batch
TestInterventionEngine (8)  — confidence, evidence, intervention selection
TestPlanningSummary    (5)  — profile structure and types
TestDecisionEngine     (4)  — end-to-end run() output
"""

from __future__ import annotations

import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

# ---------------------------------------------------------------------------
# Synthetic GeoDataFrame fixture (reused across test classes)
# ---------------------------------------------------------------------------

def _make_box(i: int):
    lon = 72.80 + i * 0.01
    return box(lon, 19.10, lon + 0.01, 19.11)


@pytest.fixture(scope="module")
def synthetic_gdf() -> gpd.GeoDataFrame:
    """10-row GDF: row 0 = max stress, row 9 = min stress."""
    n = 10
    data = {
        "cell_id":            [f"CELL_{i:03d}" for i in range(n)],
        "mean_lst":           np.linspace(42.0, 24.0, n),
        "mean_ndvi":          np.linspace(0.05, 0.65, n),
        "mean_ndbi":          np.linspace(0.55, 0.05, n),
        "mean_dem":           np.linspace(2.0,  80.0, n),
        "uhi_intensity":      np.linspace(8.0,  -1.0, n),
        "risk_score":         np.linspace(90.0,  5.0, n),
        "top_positive_driver":["mean_lst"] * n,
        "top_positive_shap":  np.linspace(5.0,   0.5, n),
        "geometry":           [_make_box(i) for i in range(n)],
    }
    return gpd.GeoDataFrame(data, crs="EPSG:4326")


@pytest.fixture(scope="module")
def synthetic_env_intel(synthetic_gdf) -> dict:
    """Minimal env_intel dict covering all 10 cells."""
    intel = {}
    for i, row in synthetic_gdf.iterrows():
        cell_id = row["cell_id"]
        ehi = float(np.clip(100.0 - row["risk_score"], 0, 100))
        conditions = []
        if row["uhi_intensity"] > 5.0:
            conditions.append("Urban Heat Island")
        if row["mean_ndvi"] < 0.2:
            conditions.append("Low Vegetation")
        if row["mean_ndbi"] > 0.4:
            conditions.append("High Built-up Density")
        intel[cell_id] = {
            "environmental_health":   round(ehi, 2),
            "environmental_status":   "Poor" if ehi < 40 else "Moderate",
            "detected_conditions":    conditions,
            "primary_issue":          conditions[0] if conditions else None,
            "secondary_issue":        conditions[1] if len(conditions) > 1 else None,
            "city_rank_lst":          float(90 - i * 8),
            "city_rank_ndvi":         float(10 + i * 8),
            "city_rank_ndbi":         float(85 - i * 8),
            "city_rank_uhi":          float(88 - i * 8),
            "city_rank_dem":          float(10 + i * 8),
        }
    return intel


@pytest.fixture(scope="module")
def synthetic_geo_meta(synthetic_gdf) -> dict:
    """Minimal geo_meta dict."""
    meta = {}
    land_uses = [
        "Dense Commercial / Industrial", "Residential", "Mixed Urban",
        "Mixed Residential", "Sparse Vegetation / Open Land",
        "Green Space / Forest", "Residential", "Mixed Urban",
        "Water Body / Coastal", "Green Space / Forest",
    ]
    for i, row in synthetic_gdf.iterrows():
        meta[row["cell_id"]] = {
            "population":       50000 * (10 - i),
            "dominant_land_use": land_uses[i],
            "ward":             "S Ward",
        }
    return meta


# ===========================================================================
# TestKnowledgeBase
# ===========================================================================

class TestKnowledgeBase:

    def test_catalog_loads_without_error(self):
        from planning.knowledge_base import load_catalog
        catalog = load_catalog()
        assert isinstance(catalog, dict)
        assert "interventions" in catalog
        assert "multi_condition_overrides" in catalog

    def test_all_single_condition_entries_have_required_keys(self):
        from planning.knowledge_base import load_catalog, _REQUIRED_ENTRY_KEYS
        catalog = load_catalog()
        for key, entry in catalog["interventions"].items():
            for req in _REQUIRED_ENTRY_KEYS:
                assert req in entry, f"Entry '{key}' missing key '{req}'"

    def test_single_condition_lookup_uhi(self):
        from planning.knowledge_base import get_intervention
        result = get_intervention(["Urban Heat Island"])
        assert result["primary"] == "Urban Forest"

    def test_multi_condition_override_uhi_vegetation(self):
        from planning.knowledge_base import get_intervention
        result = get_intervention(["Urban Heat Island", "Low Vegetation"])
        assert result["primary"] == "Urban Forest"
        # The 2-condition override secondary should include Bioswales
        assert any("Bioswale" in s for s in result["secondary"])

    def test_three_condition_override_wins_over_two_condition(self):
        from planning.knowledge_base import get_intervention
        result = get_intervention(
            ["Urban Heat Island", "Low Vegetation", "High Built-up Density"]
        )
        # 3-condition override: secondary should include Vertical Greening
        assert any("Vertical" in s for s in result["secondary"])

    def test_empty_conditions_returns_default(self):
        from planning.knowledge_base import get_intervention
        result = get_intervention([])
        assert result["primary"] == "Environmental Monitoring"

    def test_strategic_weight_residential(self):
        from planning.knowledge_base import get_strategic_weight
        assert get_strategic_weight("Residential") == 80.0

    def test_strategic_weight_green_space(self):
        from planning.knowledge_base import get_strategic_weight
        assert get_strategic_weight("Green Space / Forest") == 30.0

    def test_strategic_weight_unknown(self):
        from planning.knowledge_base import get_strategic_weight
        assert get_strategic_weight(None) == 50.0
        assert get_strategic_weight("Something New") == 50.0


# ===========================================================================
# TestPriorityEngine
# ===========================================================================

class TestPriorityEngine:

    def test_priority_score_bounds_all_cells(self, synthetic_gdf, synthetic_env_intel, synthetic_geo_meta):
        from planning.priority_engine import compute_priority_batch
        result = compute_priority_batch(synthetic_gdf, synthetic_env_intel, synthetic_geo_meta)
        for score in result["priority_score"]:
            assert 0.0 <= score <= 100.0, f"Score {score} out of bounds"

    def test_high_stress_cell_has_higher_priority_than_healthy(self, synthetic_gdf, synthetic_env_intel, synthetic_geo_meta):
        from planning.priority_engine import compute_priority_batch
        result = compute_priority_batch(synthetic_gdf, synthetic_env_intel, synthetic_geo_meta)
        score_stressed = result.loc[result["cell_id"] == "CELL_000", "priority_score"].iloc[0]
        score_healthy  = result.loc[result["cell_id"] == "CELL_009", "priority_score"].iloc[0]
        assert score_stressed > score_healthy, (
            f"Stressed cell ({score_stressed:.1f}) should score higher than healthy ({score_healthy:.1f})"
        )

    def test_all_five_priority_labels_reachable(self):
        from planning.priority_engine import get_priority_label
        assert get_priority_label(90.0) == "Critical"
        assert get_priority_label(70.0) == "High"
        assert get_priority_label(50.0) == "Medium"
        assert get_priority_label(30.0) == "Low"
        assert get_priority_label(10.0) == "Very Low"

    def test_priority_label_boundaries(self):
        from planning.priority_engine import get_priority_label
        assert get_priority_label(80.0) == "Critical"
        assert get_priority_label(79.9) == "High"
        assert get_priority_label(60.0) == "High"
        assert get_priority_label(59.9) == "Medium"

    def test_batch_returns_all_cells(self, synthetic_gdf, synthetic_env_intel, synthetic_geo_meta):
        from planning.priority_engine import compute_priority_batch
        result = compute_priority_batch(synthetic_gdf, synthetic_env_intel, synthetic_geo_meta)
        assert len(result) == len(synthetic_gdf)

    def test_batch_has_required_columns(self, synthetic_gdf, synthetic_env_intel, synthetic_geo_meta):
        from planning.priority_engine import compute_priority_batch
        result = compute_priority_batch(synthetic_gdf, synthetic_env_intel, synthetic_geo_meta)
        assert "cell_id" in result.columns
        assert "priority_score" in result.columns
        assert "planning_priority" in result.columns

    def test_nan_population_handled(self):
        from planning.priority_engine import compute_population_score
        assert compute_population_score(float("nan"), 100000) == 0.0
        assert compute_population_score(None, 100000) == 0.0

    def test_zero_max_population_handled(self):
        from planning.priority_engine import compute_population_score
        assert compute_population_score(50000, 0) == 0.0


# ===========================================================================
# TestInterventionEngine
# ===========================================================================

class TestInterventionEngine:

    def test_confidence_high_shap_all_indicators(self):
        from planning.intervention_engine import compute_confidence
        conf = compute_confidence(
            top_positive_shap=9.0,
            city_max_shap=10.0,
            n_conditions=2,
            n_indicators_present=5,
        )
        assert conf > 0.7, f"Expected confidence > 0.7, got {conf:.3f}"

    def test_confidence_zero_shap(self):
        from planning.intervention_engine import compute_confidence
        conf = compute_confidence(
            top_positive_shap=0.0,
            city_max_shap=10.0,
            n_conditions=0,
            n_indicators_present=3,
        )
        assert conf <= 0.5, f"Expected confidence <= 0.5 with zero SHAP, got {conf:.3f}"

    def test_confidence_never_exceeds_one(self):
        from planning.intervention_engine import compute_confidence
        conf = compute_confidence(
            top_positive_shap=1000.0,
            city_max_shap=1.0,
            n_conditions=10,
            n_indicators_present=5,
        )
        assert conf <= 1.0

    def test_confidence_never_below_zero(self):
        from planning.intervention_engine import compute_confidence
        conf = compute_confidence(
            top_positive_shap=None,
            city_max_shap=0.0,
            n_conditions=0,
            n_indicators_present=0,
        )
        assert conf >= 0.0

    def test_empty_conditions_returns_default_intervention(self):
        from planning.intervention_engine import select_intervention
        result = select_intervention([])
        assert result["primary"] == "Environmental Monitoring"

    def test_evidence_text_no_placeholders(self):
        from planning.intervention_engine import build_evidence_text
        cmp = {
            "city_rank_lst":  93.0,
            "city_rank_ndvi": 12.0,
            "city_rank_ndbi": 80.0,
        }
        text = build_evidence_text(
            primary_issue="Urban Heat Island",
            cell_comparisons=cmp,
            top_positive_driver="mean_lst",
            top_positive_shap=4.5,
            intervention_name="Urban Forest",
        )
        assert "{" not in text, f"Unfilled placeholder in: {text}"

    def test_evidence_text_mentions_shap_driver(self):
        from planning.intervention_engine import build_evidence_text
        text = build_evidence_text(
            primary_issue="Urban Heat Island",
            cell_comparisons={"city_rank_lst": 92.0},
            top_positive_driver="mean_lst",
            top_positive_shap=3.8,
            intervention_name="Urban Forest",
        )
        assert "temperature" in text.lower() or "lst" in text.lower()

    def test_multi_condition_override_selected(self):
        from planning.intervention_engine import select_intervention
        result = select_intervention(["Urban Heat Island", "Low Vegetation"])
        # Multi-condition override for UHI + Low Veg → Urban Forest with Bioswales
        assert result["primary"] == "Urban Forest"
        assert any("Bioswale" in s for s in result["secondary"])

    def test_confidence_with_missing_indicators(self):
        from planning.intervention_engine import compute_confidence
        conf = compute_confidence(
            top_positive_shap=5.0,
            city_max_shap=10.0,
            n_conditions=1,
            n_indicators_present=2,   # only 2 of 5 present
        )
        assert 0.0 <= conf <= 1.0
        # Should be lower than full-indicator confidence
        conf_full = compute_confidence(5.0, 10.0, 1, 5)
        assert conf < conf_full


# ===========================================================================
# TestPlanningSummary
# ===========================================================================

class TestPlanningSummary:

    def _sample_intervention(self) -> dict:
        return {
            "primary":    "Urban Forest",
            "secondary":  ["Cool Roof Program", "Street Trees"],
            "objectives": ["Reduce Urban Heat", "Increase Green Cover"],
            "benefits":   ["Lower LST", "Higher NDVI"],
            "cost":       "Medium",
            "timeline":   "2-5 Years",
            "complexity": "Moderate",
        }

    def test_profile_has_all_required_keys(self):
        from planning.planning_summary import build_planning_profile, get_required_keys
        profile = build_planning_profile(
            cell_id="TEST_000",
            ehi=25.0,
            risk_score=80.0,
            priority_score=85.0,
            priority_label="Critical",
            intervention=self._sample_intervention(),
            confidence=0.88,
            evidence_text="Test evidence.",
        )
        for key in get_required_keys():
            assert key in profile, f"Required key '{key}' missing from profile"

    def test_priority_color_all_labels(self):
        from planning.planning_summary import get_priority_color
        valid = {"error", "warning", "success"}
        for label in ["Critical", "High", "Medium", "Low", "Very Low"]:
            color = get_priority_color(label)
            assert color in valid, f"Unexpected color '{color}' for label '{label}'"

    def test_priority_score_is_float(self):
        from planning.planning_summary import build_planning_profile
        profile = build_planning_profile(
            "X", 50.0, 50.0, 60.0, "High",
            self._sample_intervention(), 0.75, "Evidence."
        )
        assert isinstance(profile["priority_score"], float)

    def test_secondary_interventions_is_list(self):
        from planning.planning_summary import build_planning_profile
        profile = build_planning_profile(
            "X", 50.0, 50.0, 60.0, "High",
            self._sample_intervention(), 0.75, "Evidence."
        )
        assert isinstance(profile["secondary_interventions"], list)

    def test_confidence_is_float(self):
        from planning.planning_summary import build_planning_profile
        profile = build_planning_profile(
            "X", 50.0, 50.0, 60.0, "High",
            self._sample_intervention(), 0.75, "Evidence."
        )
        assert isinstance(profile["confidence"], float)


# ===========================================================================
# TestDecisionEngine
# ===========================================================================

class TestDecisionEngine:

    def test_run_returns_all_cells(self, synthetic_gdf, synthetic_env_intel, synthetic_geo_meta):
        from planning.decision_engine import run
        profiles = run(synthetic_gdf, synthetic_env_intel, synthetic_geo_meta, {})
        assert len(profiles) == len(synthetic_gdf)

    def test_all_profiles_have_required_keys(self, synthetic_gdf, synthetic_env_intel, synthetic_geo_meta):
        from planning.decision_engine import run
        from planning.planning_summary import get_required_keys
        profiles = run(synthetic_gdf, synthetic_env_intel, synthetic_geo_meta, {})
        required = get_required_keys()
        for cell_id, profile in profiles.items():
            for key in required:
                assert key in profile, f"Cell '{cell_id}' profile missing key '{key}'"

    def test_priority_scores_are_bounded(self, synthetic_gdf, synthetic_env_intel, synthetic_geo_meta):
        from planning.decision_engine import run
        profiles = run(synthetic_gdf, synthetic_env_intel, synthetic_geo_meta, {})
        for cell_id, profile in profiles.items():
            score = profile["priority_score"]
            assert 0.0 <= score <= 100.0, f"Cell '{cell_id}' score={score} out of bounds"

    def test_intervention_names_are_non_empty(self, synthetic_gdf, synthetic_env_intel, synthetic_geo_meta):
        from planning.decision_engine import run
        profiles = run(synthetic_gdf, synthetic_env_intel, synthetic_geo_meta, {})
        for cell_id, profile in profiles.items():
            name = profile.get("recommended_intervention", "")
            assert isinstance(name, str) and len(name) > 0, (
                f"Cell '{cell_id}' has empty/None recommended_intervention"
            )
