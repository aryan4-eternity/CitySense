"""Centralized, cached access to the City Sense YAML configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load the project configuration from *path* and return a dictionary.

    The loader deliberately returns a fresh mapping on each call so callers that
    adjust a local copy cannot accidentally alter configuration seen elsewhere.
    """
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    if not isinstance(config, dict):
        raise ValueError(f"Configuration file '{config_path}' must contain a mapping.")
    return config


def project_path(config: Mapping[str, Any], output_key: str) -> Path:
    """Resolve an ``output_paths`` entry into an absolute project path."""
    try:
        relative_path = config["output_paths"][output_key]
    except KeyError as exc:
        raise KeyError(f"Missing output_paths.{output_key} in configuration.") from exc
    return PROJECT_ROOT / relative_path
