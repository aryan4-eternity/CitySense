import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

# Resolve the project root so the log directory is always relative to the project
_PROJECT_ROOT = Path(__file__).resolve().parent


def setup_logging(
    log_file: str | Path | None = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> logging.Logger:
    """
    Sets up structured logging to both console and a file.

    Parameters
    ----------
    log_file : str or Path, optional
        Path to the log file.  Defaults to ``logs/pipeline.log`` inside the
        project root.  Parent directories are created automatically.
    console_level : int
        Minimum severity shown on the console (default ``INFO``).
    file_level : int
        Minimum severity written to the log file (default ``DEBUG``).

    Returns
    -------
    logging.Logger
        The configured root project logger (``"CitySense"``).
    """
    if log_file is None:
        log_file = _PROJECT_ROOT / "logs" / "pipeline.log"
    log_file = Path(log_file)

    # Create a custom logger
    logger = logging.getLogger("CitySense")
    logger.setLevel(logging.DEBUG)

    # Prevent adding handlers multiple times if called again
    if not logger.handlers:
        # Ensure the log directory exists
        os.makedirs(log_file.parent, exist_ok=True)

        # Create handlers
        c_handler = logging.StreamHandler(sys.stdout)
        f_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')

        c_handler.setLevel(console_level)
        f_handler.setLevel(file_level)

        # Create formatters and add it to handlers
        c_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        f_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        )

        c_handler.setFormatter(c_format)
        f_handler.setFormatter(f_format)

        # Add handlers to the logger
        logger.addHandler(c_handler)
        logger.addHandler(f_handler)

    return logger

def validate_config(config: Mapping[str, Any]) -> bool:
    """
    Validates the parsed configuration dictionary to ensure required keys exist
    and values are sensible.
    Raises ValueError if validation fails.
    """
    logger = logging.getLogger("CitySense")
    logger.info("Validating configuration...")

    required_keys = ["aoi", "grid", "time_window", "output_paths"]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required configuration key: '{key}'")
            
    # Validate bbox
    bbox = config.get("aoi", {})
    bbox_keys = ['west', 'south', 'east', 'north']
    for b_key in bbox_keys:
        if b_key not in bbox:
            raise ValueError(f"bbox missing required key: '{b_key}'")
            
    if not (bbox['west'] < bbox['east']):
        raise ValueError("Invalid bounding box: 'west' must be less than 'east'")
    if not (bbox['south'] < bbox['north']):
        raise ValueError("Invalid bounding box: 'south' must be less than 'north'")
        
    # Validate date range if present
    dates = config.get("time_window", {})
    if 'start' in dates and 'end' in dates:
        try:
            start_date = datetime.strptime(dates['start'], "%Y-%m-%d")
            end_date = datetime.strptime(dates['end'], "%Y-%m-%d")
            if start_date > end_date:
                raise ValueError("Invalid dates: 'start' date must be before 'end' date")
        except ValueError as e:
            # If it's a parsing error from strptime or our custom ValueError
            raise ValueError(f"Date validation failed: {e}")
            
    logger.info("Configuration is valid.")
    return True
