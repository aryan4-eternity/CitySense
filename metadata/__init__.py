"""
metadata
========
Package for Geographic Intelligence Layer enrichment.
Transforms grid cells into human-readable geographic entities.
"""

from .geo_enrichment import main as enrich_all_grids

__all__ = ["enrich_all_grids"]
