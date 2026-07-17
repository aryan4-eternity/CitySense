"""Single entry point for the City Sense geospatial processing pipeline."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from config_loader import load_config, project_path
from utils import setup_logging, validate_config


def run_stage(
    name: str,
    stage: Callable[[], None],
    logger: logging.Logger,
    expected_output: Path | None = None,
) -> None:
    """Run one stage unless its expected reusable output already exists."""
    if expected_output is not None and expected_output.exists():
        logger.info("Skipping stage '%s'; output already exists: %s", name, expected_output)
        return
    logger.info("Running stage: %s", name)
    t0 = time.time()
    try:
        stage()
    except Exception:
        elapsed = time.time() - t0
        logger.error(
            "Stage '%s' FAILED after %.2fs", name, elapsed, exc_info=True,
        )
        raise
    elapsed = time.time() - t0
    logger.info("Completed stage: %s (%.2fs)", name, elapsed)


def main() -> None:
    """Validate configuration and execute City Sense stages in dependency order."""
    logger = setup_logging()
    logger.info("=== City Sense Pipeline Started ===")
    config = load_config()
    validate_config(config)

    # Importing modules, rather than shelling out to placeholder filenames,
    # preserves each standalone script's existing ``main`` entry point.
    from ingestion import fetch_dem, fetch_lst, fetch_ndbi, fetch_ndvi, generate_grid
    from processing import (
        compute_uhi,
        generate_explanations_json,
        kmeans_clustering,
        lst_ndvi_analysis,
        merge_indicators,
        pca_scoring,
        train_explainability,
        validate_scores,
    )
    from metadata import geo_enrichment
    from environment import generate_environmental_intelligence
    from planning import generate_planning_profiles

    stages: list[tuple[str, Callable[[], None], Path | None]] = [
        ("Generate grid", generate_grid.main, project_path(config, "grid")),
        ("Fetch NDVI", fetch_ndvi.main, project_path(config, "ndvi_grid")),
        ("Fetch land-surface temperature", fetch_lst.main, project_path(config, "lst_grid")),
        ("Fetch NDBI", fetch_ndbi.main, project_path(config, "ndbi_grid")),
        ("Fetch DEM", fetch_dem.main, project_path(config, "dem_grid")),
        ("Merge indicators", merge_indicators.main, None),
        ("Compute UHI", compute_uhi.main, None),
        ("Analyze LST and NDVI", lst_ndvi_analysis.main, None),
        ("Score cells with PCA", pca_scoring.main, None),
        ("Cluster urban typologies", kmeans_clustering.main, None),
        ("Train explainability model", train_explainability.main, None),
        ("Create dashboard explanations", generate_explanations_json.main, None),
        ("Generate environmental intelligence", generate_environmental_intelligence.main, project_path(config, "environmental_intelligence")),
        ("Generate planning profiles", generate_planning_profiles.main, project_path(config, "planning_profiles")),
        ("Enrich geographic metadata", geo_enrichment.main, project_path(config, "geographic_metadata")),
        ("Generate validation plots", validate_scores.main, None),
    ]
    for name, stage, expected_output in stages:
        run_stage(name, stage, logger, expected_output)
    logger.info("=== City Sense Pipeline Finished ===")


if __name__ == "__main__":
    main()
