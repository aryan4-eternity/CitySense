import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

def setup_logging(log_file: str | Path = "citysense.log") -> logging.Logger:
    """
    Sets up structured logging to both console and a file.
    """
    # Create a custom logger
    logger = logging.getLogger("CitySense")
    logger.setLevel(logging.DEBUG)

    # Prevent adding handlers multiple times if called again
    if not logger.handlers:
        # Create handlers
        c_handler = logging.StreamHandler(sys.stdout)
        f_handler = logging.FileHandler(log_file, mode='a')

        c_handler.setLevel(logging.INFO)
        f_handler.setLevel(logging.DEBUG)

        # Create formatters and add it to handlers
        c_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
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
