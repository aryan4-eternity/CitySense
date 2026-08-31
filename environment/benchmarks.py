"""
benchmarks.py
=============
Benchmark selection and anchor computation for recalibrating continuous
environmental health scores (EHI, Planning Priority, Composite Burden).

Methodology
-----------
1. Select "comparable urban cells":
   - Exclude water/sea cells (is_water flag or NDVI < 0.05 and DEM < 3.5 m).
   - Exclude the Sanjay Gandhi National Park (SGNP) reference bounding box.
   - Exclude non-urban outlier clusters (Ecological Sanctuary / Forest Ridge
     and Dense Industrial / High Thermal Risk).
2. Take the top 10% by NDVI from the remaining urban cells as the
   "greenest comparable urban neighborhoods" (green-urban benchmark).
3. Compute per-indicator anchor set:
   - For LST, UHI, NDBI (higher = worse):
       Good (G)  = median of benchmark cells
       Worst (W) = 95th percentile of city-wide cells
   - For NDVI, DEM (higher = better):
       Good (G)  = median of benchmark cells
       Worst (W) = 5th percentile of city-wide cells

Public API
----------
select_comparable_urban_cells(gdf, cfg)       -> gpd.GeoDataFrame
select_green_urban_benchmark_cells(gdf, cfg) -> gpd.GeoDataFrame
compute_benchmarks(gdf, cfg)                  -> dict[str, dict[str, float]]
save_benchmarks(benchmarks, path)             -> None
load_benchmarks(path)                         -> dict[str, dict[str, float]]
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd

logger = logging.getLogger("CitySense.environment.benchmarks")

# Default SGNP reference bounding box (used if config not passed)
_DEFAULT_SGNP_BBOX = {
    "west": 72.87,
    "east": 72.93,
    "south": 19.18,
    "north": 19.25,
}

_WATER_NDVI_MAX = 0.05
_WATER_DEM_MAX = 3.5


def select_comparable_urban_cells(
    gdf: gpd.GeoDataFrame,
    cfg: dict[str, Any] | None = None,
) -> gpd.GeoDataFrame:
    """Filter master dataset to standard comparable urban cells.

    Excludes:
    1. Water/sea cells (is_water == True or NDVI < 0.05 and DEM < 3.5m).
    2. SGNP baseline cells falling inside the reference bounding box.
    3. Non-urban clusters (Cluster 1: Green/Forested, Cluster 3: Industrial/Extreme Heat).

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Master dataset.
    cfg : dict, optional
        Project configuration dictionary.

    Returns
    -------
    gpd.GeoDataFrame
        Filtered GeoDataFrame containing comparable urban cells.
    """
    if gdf.empty:
        return gdf

    # 1. Identify water cells
    is_water = pd.Series(False, index=gdf.index)
    if "is_water" in gdf.columns:
        is_water = gdf["is_water"].fillna(False).astype(bool)

    if "mean_ndvi" in gdf.columns and "mean_dem" in gdf.columns:
        raw_water = (
            gdf["mean_ndvi"].isna()
            | gdf["mean_dem"].isna()
            | ((gdf["mean_ndvi"] < _WATER_NDVI_MAX) & (gdf["mean_dem"] < _WATER_DEM_MAX))
        )
        is_water = is_water | raw_water

    # 2. Identify SGNP bounding box
    bbox = _DEFAULT_SGNP_BBOX
    if cfg:
        bbox = (
            cfg.get("uhi", {}).get("reference_bbox")
            or cfg.get("processing", {}).get("uhi_baseline")
            or _DEFAULT_SGNP_BBOX
        )

    west = bbox.get("west", bbox.get("lon_min", 72.87))
    east = bbox.get("east", bbox.get("lon_max", 72.93))
    south = bbox.get("south", bbox.get("lat_min", 19.18))
    north = bbox.get("north", bbox.get("lat_max", 19.25))

    in_sgnp = pd.Series(False, index=gdf.index)
    if hasattr(gdf, "geometry") and gdf.geometry is not None:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=UserWarning)
                centroids = gdf.geometry.centroid
            in_sgnp = (
                (centroids.x >= west)
                & (centroids.x <= east)
                & (centroids.y >= south)
                & (centroids.y <= north)
            )
        except Exception as exc:
            logger.debug("Centroid calculation skipped: %s", exc)

    # 3. Identify non-urban clusters
    non_urban_cluster = pd.Series(False, index=gdf.index)
    if "cluster_id" in gdf.columns:
        non_urban_cluster = non_urban_cluster | gdf["cluster_id"].isin([1, 3])
    if "cluster" in gdf.columns:
        cluster_text = gdf["cluster"].astype(str).str.lower()
        non_urban_text = cluster_text.str.contains(
            r"green|forest|sanctuary|industrial|extreme",
            regex=True,
            na=False,
        )
        non_urban_cluster = non_urban_cluster | non_urban_text

    urban_mask = ~is_water & ~in_sgnp & ~non_urban_cluster
    urban_cells = gdf[urban_mask]

    # Graceful fallback if dataset lacks cluster / spatial fields (e.g. tiny synthetic test)
    if urban_cells.empty:
        logger.warning(
            "Comparable urban cell filter matched 0 cells; falling back to non-water cells."
        )
        urban_cells = gdf[~is_water] if (~is_water).any() else gdf

    logger.debug(
        "Comparable urban cells selected: %d / %d cells",
        len(urban_cells),
        len(gdf),
    )
    return urban_cells


def select_green_urban_benchmark_cells(
    gdf: gpd.GeoDataFrame,
    cfg: dict[str, Any] | None = None,
    top_pct: float = 0.10,
) -> gpd.GeoDataFrame:
    """Select top-10% NDVI urban cells as the green-urban benchmark.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Master dataset.
    cfg : dict, optional
        Project configuration dictionary.
    top_pct : float, default 0.10
        Fraction of highest NDVI cells to select from comparable urban cells.

    Returns
    -------
    gpd.GeoDataFrame
        Benchmark cells subset.
    """
    urban_cells = select_comparable_urban_cells(gdf, cfg)
    if urban_cells.empty:
        return gdf

    if "mean_ndvi" not in urban_cells.columns:
        logger.warning("mean_ndvi column missing; returning all urban cells as benchmark.")
        return urban_cells

    ndvi_series = urban_cells["mean_ndvi"].dropna()
    if ndvi_series.empty:
        return urban_cells

    cutoff = float(ndvi_series.quantile(1.0 - top_pct))
    benchmark_cells = urban_cells[urban_cells["mean_ndvi"] >= cutoff]

    if benchmark_cells.empty:
        benchmark_cells = urban_cells

    logger.debug(
        "Green-urban benchmark cells: %d cells (NDVI cutoff >= %.4f)",
        len(benchmark_cells),
        cutoff,
    )
    return benchmark_cells


def compute_benchmarks(
    gdf: gpd.GeoDataFrame,
    cfg: dict[str, Any] | None = None,
    top_pct: float = 0.10,
) -> dict[str, dict[str, float]]:
    """Compute indicator anchors (good G, worst W) for benchmark-based normalization.

    Anchors:
    - mean_lst:      good = benchmark median, worst = city-wide p95
    - uhi_intensity: good = benchmark median, worst = city-wide p95
    - mean_ndbi:     good = benchmark median, worst = city-wide p95
    - mean_ndvi:     good = benchmark median, worst = city-wide p5
    - mean_dem:      good = benchmark median, worst = city-wide p5

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Master dataset.
    cfg : dict, optional
        Project configuration.
    top_pct : float, default 0.10
        Percentile slice for benchmark selection.

    Returns
    -------
    dict[str, dict[str, float]]
        Nested dictionary with 'good' and 'worst' floats per indicator.
    """
    bench_cells = select_green_urban_benchmark_cells(gdf, cfg, top_pct=top_pct)

    indicators_high_bad = ["mean_lst", "uhi_intensity", "mean_ndbi"]
    indicators_high_good = ["mean_ndvi", "mean_dem"]

    anchors: dict[str, dict[str, float]] = {}

    for ind in indicators_high_bad:
        if ind in gdf.columns and not gdf[ind].dropna().empty:
            b_series = bench_cells[ind].dropna() if ind in bench_cells.columns else pd.Series(dtype=float)
            good_val = float(b_series.median()) if not b_series.empty else float(gdf[ind].median())
            worst_val = float(gdf[ind].quantile(0.95))
            # Guard against equality
            if good_val == worst_val:
                worst_val = float(gdf[ind].max()) if float(gdf[ind].max()) != good_val else good_val + 1.0
            anchors[ind] = {"good": round(good_val, 4), "worst": round(worst_val, 4)}

    for ind in indicators_high_good:
        if ind in gdf.columns and not gdf[ind].dropna().empty:
            b_series = bench_cells[ind].dropna() if ind in bench_cells.columns else pd.Series(dtype=float)
            good_val = float(b_series.median()) if not b_series.empty else float(gdf[ind].median())
            worst_val = float(gdf[ind].quantile(0.05))
            # Guard against equality
            if good_val == worst_val:
                worst_val = float(gdf[ind].min()) if float(gdf[ind].min()) != good_val else good_val - 1.0
            anchors[ind] = {"good": round(good_val, 4), "worst": round(worst_val, 4)}

    logger.info("Computed benchmark anchors for %d indicators.", len(anchors))
    for ind, vals in anchors.items():
        logger.info("  %-15s : Good (G) = %8.4f | Worst (W) = %8.4f", ind, vals["good"], vals["worst"])

    return anchors


def save_benchmarks(benchmarks: dict[str, Any], path: Path | str) -> None:
    """Save benchmark dictionary to JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(benchmarks, f, indent=2)
    logger.info("Saved benchmark anchors to %s", p)


def load_benchmarks(path: Path | str | None = None) -> dict[str, dict[str, float]]:
    """Load benchmark dictionary from JSON file."""
    if path is None:
        path = Path("data/benchmarks.json")
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Benchmark file not found at '{p}'.")
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data
