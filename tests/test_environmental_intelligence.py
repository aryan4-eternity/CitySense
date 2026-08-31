"""
test_environmental_intelligence.py
====================================
Unit tests for the Phase 2 Environmental Intelligence modules.

All tests use a synthetic 10-row GeoDataFrame with known extreme and median
values so they run without the real Mumbai dataset.

Coverage
--------
- environment.comparative_analysis  : compute_city_stats, compute_cell_comparisons
- environment.environmental_health  : compute_ehi, get_environmental_status, compute_ehi_batch
- environment.indicator_interpreter : detect_conditions, get_primary_and_secondary_issues,
                                      generate_spatial_context
- environment.environmental_summary : generate_summary
"""

from __future__ import annotations

import math
import re

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

# ---------------------------------------------------------------------------
# Synthetic dataset fixture
# ---------------------------------------------------------------------------

def _make_box(i: int) -> box:
    """Create a tiny bounding box for cell i (0-indexed)."""
    lon = 72.80 + i * 0.01
    return box(lon, 19.10, lon + 0.01, 19.11)


@pytest.fixture(scope="module")
def synthetic_gdf() -> gpd.GeoDataFrame:
    """
    10-row GeoDataFrame covering the full range of each indicator so that
    percentile and EHI tests produce deterministic, verifiable results.

    Row layout:
      0 – maximum stress (hottest, no vegetation, most built-up, lowest DEM, highest UHI)
      9 – minimum stress (coolest, most vegetation, least built-up, highest DEM, lowest UHI)
      1-8 – evenly interpolated between the two extremes
    """
    n = 10
    lst_vals  = np.linspace(42.0, 24.0, n)   # 42 → 24 °C
    ndvi_vals = np.linspace(0.05, 0.65, n)   # 0.05 → 0.65
    ndbi_vals = np.linspace(0.55, 0.05, n)   # 0.55 → 0.05
    dem_vals  = np.linspace(2.0,  80.0, n)   # 2 → 80 m
    uhi_vals  = np.linspace(8.0,  -1.0, n)   # 8 → -1 °C (hot to cool)
    risk_vals = np.linspace(90.0,  5.0, n)   # 90 → 5

    data = {
        "cell_id":        [f"CELL_{i:03d}" for i in range(n)],
        "mean_lst":       lst_vals,
        "mean_ndvi":      ndvi_vals,
        "mean_ndbi":      ndbi_vals,
        "mean_dem":       dem_vals,
        "uhi_intensity":  uhi_vals,
        "risk_score":     risk_vals,
        "geometry":       [_make_box(i) for i in range(n)],
    }
    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
    return gdf


# ---------------------------------------------------------------------------
# comparative_analysis tests
# ---------------------------------------------------------------------------

class TestCityStats:
    def test_returns_all_indicator_keys(self, synthetic_gdf):
        from environment.comparative_analysis import compute_city_stats
        stats = compute_city_stats(synthetic_gdf)
        expected = {"mean_lst", "mean_ndvi", "mean_ndbi", "uhi_intensity", "mean_dem", "risk_score"}
        assert expected.issubset(set(stats.keys())), (
            f"Missing keys: {expected - set(stats.keys())}"
        )

    def test_stat_values_are_numeric(self, synthetic_gdf):
        from environment.comparative_analysis import compute_city_stats
        stats = compute_city_stats(synthetic_gdf)
        for indicator, stat_dict in stats.items():
            for stat_name, value in stat_dict.items():
                assert isinstance(value, float), (
                    f"{indicator}.{stat_name} should be float, got {type(value)}"
                )
                assert math.isfinite(value), (
                    f"{indicator}.{stat_name} = {value} is not finite"
                )

    def test_min_less_than_max(self, synthetic_gdf):
        from environment.comparative_analysis import compute_city_stats
        stats = compute_city_stats(synthetic_gdf)
        for indicator, s in stats.items():
            assert s["min"] <= s["max"], f"{indicator}: min > max"
            assert s["min"] <= s["mean"] <= s["max"], f"{indicator}: mean outside [min, max]"

    def test_skips_missing_column_gracefully(self, synthetic_gdf):
        """compute_city_stats should skip an absent column without raising."""
        from environment.comparative_analysis import compute_city_stats
        gdf_no_uhi = synthetic_gdf.drop(columns=["uhi_intensity"])
        stats = compute_city_stats(gdf_no_uhi)
        assert "uhi_intensity" not in stats
        # All other indicators must still be present
        assert "mean_lst" in stats


class TestCellComparisons:
    def test_median_cell_rank_near_50(self, synthetic_gdf):
        """The median-ish cell (index 4 or 5) should have LST rank near 50."""
        from environment.comparative_analysis import compute_city_stats, compute_cell_comparisons
        city_stats = compute_city_stats(synthetic_gdf)
        # Row 4 is close to the median of 10 rows
        cell = synthetic_gdf.iloc[4]
        comparisons = compute_cell_comparisons(cell, city_stats, synthetic_gdf)
        rank = comparisons["city_rank_lst"]
        assert 30.0 <= rank <= 70.0, f"Median-ish cell LST rank = {rank}, expected ~50"

    def test_hottest_cell_rank_100(self, synthetic_gdf):
        """The hottest cell (row 0) should have LST rank = 100 (or very close)."""
        from environment.comparative_analysis import compute_city_stats, compute_cell_comparisons
        city_stats = compute_city_stats(synthetic_gdf)
        cell = synthetic_gdf.iloc[0]   # max LST
        comparisons = compute_cell_comparisons(cell, city_stats, synthetic_gdf)
        assert comparisons["city_rank_lst"] >= 90.0, (
            f"Hottest cell LST rank should be >=90, got {comparisons['city_rank_lst']}"
        )

    def test_coolest_cell_rank_low(self, synthetic_gdf):
        """The coolest cell (row 9) should have a low LST rank."""
        from environment.comparative_analysis import compute_city_stats, compute_cell_comparisons
        city_stats = compute_city_stats(synthetic_gdf)
        cell = synthetic_gdf.iloc[9]   # min LST
        comparisons = compute_cell_comparisons(cell, city_stats, synthetic_gdf)
        assert comparisons["city_rank_lst"] <= 15.0, (
            f"Coolest cell LST rank should be <=15, got {comparisons['city_rank_lst']}"
        )

    def test_vs_city_avg_sign_is_correct(self, synthetic_gdf):
        """Hot cell should have positive lst_vs_city_avg; cool cell negative."""
        from environment.comparative_analysis import compute_city_stats, compute_cell_comparisons
        city_stats = compute_city_stats(synthetic_gdf)
        hot_cell  = synthetic_gdf.iloc[0]
        cool_cell = synthetic_gdf.iloc[9]
        hot_cmp  = compute_cell_comparisons(hot_cell,  city_stats, synthetic_gdf)
        cool_cmp = compute_cell_comparisons(cool_cell, city_stats, synthetic_gdf)
        assert hot_cmp["mean_lst_vs_city_avg"]  > 0, "Hot cell should be above city avg"
        assert cool_cmp["mean_lst_vs_city_avg"] < 0, "Cool cell should be below city avg"

    def test_all_expected_keys_present(self, synthetic_gdf):
        from environment.comparative_analysis import compute_city_stats, compute_cell_comparisons
        city_stats = compute_city_stats(synthetic_gdf)
        comparisons = compute_cell_comparisons(synthetic_gdf.iloc[0], city_stats, synthetic_gdf)
        for key in ("city_rank_lst", "city_rank_ndvi", "city_rank_ndbi",
                    "mean_lst_vs_city_avg", "mean_ndvi_pct_diff"):
            assert key in comparisons, f"Expected key '{key}' missing from comparisons"


# ---------------------------------------------------------------------------
# environmental_health tests
# ---------------------------------------------------------------------------

class TestComputeEHI:
    def test_ehi_bounds_all_cells(self, synthetic_gdf):
        """EHI must be in [0, 100] for every cell."""
        from environment.comparative_analysis import compute_city_stats
        from environment.environmental_health import compute_ehi
        city_stats = compute_city_stats(synthetic_gdf)
        for _, row in synthetic_gdf.iterrows():
            ehi = compute_ehi(row, city_stats)
            assert 0.0 <= ehi <= 100.0, f"EHI={ehi} out of bounds for cell {row['cell_id']}"

    def test_highest_stress_cell_lowest_ehi(self, synthetic_gdf):
        """Row 0 (max stress) must have a lower EHI than row 9 (min stress)."""
        from environment.comparative_analysis import compute_city_stats
        from environment.environmental_health import compute_ehi
        city_stats = compute_city_stats(synthetic_gdf)
        ehi_stressed = compute_ehi(synthetic_gdf.iloc[0], city_stats)
        ehi_healthy  = compute_ehi(synthetic_gdf.iloc[9], city_stats)
        assert ehi_stressed < ehi_healthy, (
            f"Stressed cell EHI ({ehi_stressed:.1f}) should be < healthy cell EHI ({ehi_healthy:.1f})"
        )

    def test_max_stress_ehi_below_threshold(self, synthetic_gdf):
        """Row 0 should have EHI < 30 (well below healthy)."""
        from environment.comparative_analysis import compute_city_stats
        from environment.environmental_health import compute_ehi
        city_stats = compute_city_stats(synthetic_gdf)
        ehi = compute_ehi(synthetic_gdf.iloc[0], city_stats)
        assert ehi < 30.0, f"Max-stress cell EHI={ehi:.1f} should be < 30"

    def test_min_stress_ehi_above_threshold(self, synthetic_gdf):
        """Row 9 should have EHI > 70 (well into healthy range)."""
        from environment.comparative_analysis import compute_city_stats
        from environment.environmental_health import compute_ehi
        city_stats = compute_city_stats(synthetic_gdf)
        ehi = compute_ehi(synthetic_gdf.iloc[9], city_stats)
        assert ehi > 70.0, f"Min-stress cell EHI={ehi:.1f} should be > 70"

    def test_nan_indicator_handled_gracefully(self, synthetic_gdf):
        """A cell with one NaN indicator should still return a finite EHI."""
        from environment.comparative_analysis import compute_city_stats
        from environment.environmental_health import compute_ehi
        city_stats = compute_city_stats(synthetic_gdf)
        cell = synthetic_gdf.iloc[3].copy()
        cell["uhi_intensity"] = float("nan")
        ehi = compute_ehi(cell, city_stats)
        assert math.isfinite(ehi) and 0.0 <= ehi <= 100.0, (
            f"EHI={ehi} is not finite or out of bounds with NaN uhi_intensity"
        )

    def test_batch_matches_single_cell(self, synthetic_gdf):
        """Batch EHI values must match single-cell values within 0.01."""
        from environment.comparative_analysis import compute_city_stats
        from environment.environmental_health import compute_ehi, compute_ehi_batch
        city_stats = compute_city_stats(synthetic_gdf)
        batch = compute_ehi_batch(synthetic_gdf, city_stats)
        for idx, row in synthetic_gdf.iterrows():
            single = compute_ehi(row, city_stats)
            assert abs(batch.loc[idx] - single) < 0.01, (
                f"Batch EHI ({batch.loc[idx]:.3f}) != single EHI ({single:.3f}) for idx {idx}"
            )


class TestEnvironmentalStatus:
    def test_all_five_statuses_reachable(self):
        from environment.environmental_health import get_environmental_status
        mapping = {
            90.0: "Excellent",
            70.0: "Good",
            50.0: "Moderate",
            30.0: "Poor",
            10.0: "Critical",
        }
        for ehi, expected in mapping.items():
            result = get_environmental_status(ehi)
            assert result == expected, f"EHI={ehi} → '{result}', expected '{expected}'"

    def test_boundary_values(self):
        from environment.environmental_health import get_environmental_status
        assert get_environmental_status(80.0) == "Excellent"
        assert get_environmental_status(79.9) == "Good"
        assert get_environmental_status(60.0) == "Good"
        assert get_environmental_status(59.9) == "Moderate"
        assert get_environmental_status(40.0) == "Moderate"
        assert get_environmental_status(39.9) == "Poor"
        assert get_environmental_status(20.0) == "Poor"
        assert get_environmental_status(19.9) == "Critical"
        assert get_environmental_status(0.0)  == "Critical"
        assert get_environmental_status(100.0) == "Excellent"


# ---------------------------------------------------------------------------
# indicator_interpreter tests
# ---------------------------------------------------------------------------

class TestDetectConditions:
    def _make_comparisons(self, **overrides) -> dict:
        """Return a neutral comparisons dict with optional overrides."""
        base = {
            "city_rank_lst":  50.0,
            "city_rank_ndvi": 50.0,
            "city_rank_ndbi": 50.0,
            "city_rank_uhi":  50.0,
            "city_rank_dem":  50.0,
            "city_rank_risk": 50.0,
        }
        base.update(overrides)
        return base

    def test_urban_heat_island_detected(self):
        from environment.indicator_interpreter import detect_conditions
        cmp = self._make_comparisons(city_rank_uhi=80.0, city_rank_lst=75.0)
        conditions = detect_conditions(cmp, ehi=25.0)
        assert "Urban Heat Island" in conditions

    def test_urban_heat_island_not_detected_without_both_criteria(self):
        """UHI requires BOTH city_rank_uhi >= 75 AND city_rank_lst >= 70."""
        from environment.indicator_interpreter import detect_conditions
        # UHI high but LST moderate
        cmp = self._make_comparisons(city_rank_uhi=80.0, city_rank_lst=60.0)
        conditions = detect_conditions(cmp, ehi=40.0)
        assert "Urban Heat Island" not in conditions

    def test_low_vegetation_detected(self):
        from environment.indicator_interpreter import detect_conditions
        cmp = self._make_comparisons(city_rank_ndvi=20.0)
        conditions = detect_conditions(cmp, ehi=45.0)
        assert "Low Vegetation" in conditions

    def test_high_builtup_detected(self):
        from environment.indicator_interpreter import detect_conditions
        cmp = self._make_comparisons(city_rank_ndbi=80.0)
        conditions = detect_conditions(cmp, ehi=35.0)
        assert "High Built-up Density" in conditions

    def test_flood_susceptibility_detected(self):
        from environment.indicator_interpreter import detect_conditions
        cmp = self._make_comparisons(city_rank_dem=10.0)
        conditions = detect_conditions(cmp, ehi=45.0)
        assert "Flood Susceptibility" in conditions

    def test_ecological_stability_detected(self):
        from environment.indicator_interpreter import detect_conditions
        cmp = self._make_comparisons(city_rank_ndvi=75.0)
        conditions = detect_conditions(cmp, ehi=75.0)
        assert "Ecological Stability" in conditions

    def test_healthy_cell_minimal_issues(self):
        from environment.indicator_interpreter import detect_conditions
        cmp = self._make_comparisons(
            city_rank_uhi=40.0, city_rank_lst=35.0,
            city_rank_ndvi=70.0, city_rank_ndbi=30.0,
            city_rank_dem=60.0,
        )
        conditions = detect_conditions(cmp, ehi=78.0)
        issue_conditions = [c for c in conditions if c != "Ecological Stability"]
        assert len(issue_conditions) == 0, f"Healthy cell should have no issues, got {issue_conditions}"

    def test_priority_ordering(self):
        """When multiple conditions fire, Urban Heat Island must come before Low Vegetation."""
        from environment.indicator_interpreter import detect_conditions
        cmp = self._make_comparisons(
            city_rank_uhi=80.0, city_rank_lst=75.0, city_rank_ndvi=20.0
        )
        conditions = detect_conditions(cmp, ehi=20.0)
        if "Urban Heat Island" in conditions and "Low Vegetation" in conditions:
            assert conditions.index("Urban Heat Island") < conditions.index("Low Vegetation")


class TestPrimarySecondaryIssues:
    def test_two_issues_returns_both(self):
        from environment.indicator_interpreter import get_primary_and_secondary_issues
        conditions = ["Urban Heat Island", "Low Vegetation"]
        primary, secondary = get_primary_and_secondary_issues(conditions, ehi=25.0)
        assert primary == "Urban Heat Island"
        assert secondary == "Low Vegetation"

    def test_one_issue_returns_none_secondary(self):
        from environment.indicator_interpreter import get_primary_and_secondary_issues
        primary, secondary = get_primary_and_secondary_issues(["Low Vegetation"], ehi=35.0)
        assert primary == "Low Vegetation"
        assert secondary is None

    def test_empty_conditions_returns_none_none(self):
        from environment.indicator_interpreter import get_primary_and_secondary_issues
        primary, secondary = get_primary_and_secondary_issues([], ehi=70.0)
        assert primary is None
        assert secondary is None

    def test_ecological_stability_only_surfaces_as_primary(self):
        from environment.indicator_interpreter import get_primary_and_secondary_issues
        primary, secondary = get_primary_and_secondary_issues(["Ecological Stability"], ehi=80.0)
        assert primary == "Ecological Stability"
        assert secondary is None


class TestSpatialContext:
    def _make_cell(self, lst: float = 35.0, ndvi: float = 0.25) -> pd.Series:
        return pd.Series({
            "cell_id":    "TEST",
            "mean_lst":   lst,
            "mean_ndvi":  ndvi,
            "mean_ndbi":  0.2,
            "mean_dem":   10.0,
            "uhi_intensity": 3.0,
            "risk_score": 50.0,
        })

    def test_returns_non_empty_string(self):
        from environment.indicator_interpreter import generate_spatial_context
        cmp = {"city_rank_lst": 90.0, "city_rank_ndvi": 15.0}
        result = generate_spatial_context(cmp, self._make_cell())
        assert isinstance(result, str) and len(result) > 10

    def test_very_hot_cell_mentions_temperature(self):
        from environment.indicator_interpreter import generate_spatial_context
        cmp = {"city_rank_lst": 93.0, "city_rank_ndvi": 50.0}
        result = generate_spatial_context(cmp, self._make_cell(lst=41.0))
        assert "41.0" in result or "hotter" in result.lower()

    def test_no_placeholder_tokens_in_output(self):
        from environment.indicator_interpreter import generate_spatial_context
        cmp = {"city_rank_lst": 75.0, "city_rank_ndvi": 30.0}
        result = generate_spatial_context(cmp, self._make_cell())
        assert "{" not in result, f"Unfilled placeholder found in: {result}"


# ---------------------------------------------------------------------------
# environmental_summary tests
# ---------------------------------------------------------------------------

PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")


class TestGenerateSummary:
    def _make_cell(self, lst: float = 38.0, ndvi: float = 0.18) -> pd.Series:
        return pd.Series({
            "cell_id":       "TEST",
            "mean_lst":      lst,
            "mean_ndvi":     ndvi,
            "mean_ndbi":     0.4,
            "mean_dem":      5.0,
            "uhi_intensity": 5.0,
            "risk_score":    75.0,
        })

    def _make_comparisons(self, **kw) -> dict:
        base = {
            "city_rank_lst":  85.0, "city_rank_ndvi": 20.0,
            "city_rank_ndbi": 78.0, "city_rank_uhi":  80.0,
            "city_rank_dem":  15.0, "city_rank_risk":  82.0,
            "mean_lst_vs_city_avg": 4.0, "mean_ndvi_vs_city_avg": -0.15,
        }
        base.update(kw)
        return base

    def test_returns_non_empty_string(self):
        from environment.environmental_summary import generate_summary
        result = generate_summary(
            self._make_cell(), ehi=25.0, status="Poor",
            conditions=["Urban Heat Island", "Low Vegetation"],
            cell_comparisons=self._make_comparisons(),
        )
        assert isinstance(result, str) and len(result) > 20

    def test_no_unfilled_placeholders(self):
        """Summary must never contain {placeholder} tokens."""
        from environment.environmental_summary import generate_summary
        for conditions, status in [
            (["Urban Heat Island"], "Critical"),
            (["Low Vegetation"], "Poor"),
            (["High Built-up Density"], "Moderate"),
            (["Flood Susceptibility"], "Moderate"),
            (["Ecological Stability"], "Excellent"),
            ([], "Good"),
        ]:
            result = generate_summary(
                self._make_cell(), ehi=50.0, status=status,
                conditions=conditions,
                cell_comparisons=self._make_comparisons(),
            )
            assert not PLACEHOLDER_RE.search(result), (
                f"Unfilled placeholder in summary for conditions={conditions}, status={status}: {result}"
            )

    def test_fallback_path_for_no_conditions(self):
        """Empty conditions list must still produce a valid summary."""
        from environment.environmental_summary import generate_summary
        result = generate_summary(
            self._make_cell(), ehi=65.0, status="Good",
            conditions=[],
            cell_comparisons=self._make_comparisons(),
        )
        assert len(result) > 10
        assert not PLACEHOLDER_RE.search(result)

    def test_critical_uhi_summary_mentions_temperature(self):
        from environment.environmental_summary import generate_summary
        result = generate_summary(
            self._make_cell(lst=41.5), ehi=12.0, status="Critical",
            conditions=["Urban Heat Island"],
            cell_comparisons=self._make_comparisons(),
        )
        # Should mention temperature or heat in some form
        assert any(word in result.lower() for word in ("temperature", "heat", "41", "urban")), (
            f"Critical UHI summary doesn't mention heat/temperature: {result}"
        )

    def test_ecological_stability_summary_positive_framing(self):
        from environment.environmental_summary import generate_summary
        result = generate_summary(
            self._make_cell(lst=26.0, ndvi=0.55), ehi=82.0, status="Excellent",
            conditions=["Ecological Stability"],
            cell_comparisons=self._make_comparisons(
                city_rank_lst=20.0, city_rank_ndvi=80.0,
            ),
        )
        assert any(word in result.lower() for word in ("excellent", "vegetation", "green", "cooling", "stable")), (
            f"Ecological stability summary lacks positive framing: {result}"
        )
