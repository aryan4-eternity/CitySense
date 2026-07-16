import os
import sys
import subprocess
import yaml
import time
from utils import setup_logging, validate_config

def run_step(step_name, script_path, output_file, logger):
    """
    Runs a pipeline step via subprocess if the expected output file does not exist.
    """
    if os.path.exists(output_file):
        logger.info(f"Skipping '{step_name}' - Output '{output_file}' already exists.")
        return True

    if not os.path.exists(script_path):
        logger.warning(f"Script for '{step_name}' not found at '{script_path}'. Please ensure it exists.")
        # We don't fail immediately, as the user might not have standard names for scripts
        return False

    logger.info(f"Running '{step_name}'...")
    start_time = time.time()
    
    try:
        # Run the script using the same python executable
        result = subprocess.run([sys.executable, script_path], check=True, capture_output=True, text=True)
        elapsed = time.time() - start_time
        logger.info(f"Successfully completed '{step_name}' in {elapsed:.2f} seconds.")
        logger.debug(f"Output of '{step_name}':\n{result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error occurred while running '{step_name}':\n{e.stderr}")
        return False

def main():
    # Setup structured logging
    logger = setup_logging()
    logger.info("=== City Sense Pipeline Started ===")
    
    # Load and validate configuration
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        logger.error(f"Configuration file '{config_path}' not found!")
        sys.exit(1)
        
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        validate_config(config)
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
        
    # Define pipeline steps
    # Each step: Name, Script Path, Expected Output File (to check if we can skip)
    pipeline = [
        {
            "name": "1. Data Ingestion & Gridding",
            "script": "ingestion/ingest_gee.py", # Example script name
            "output": "data/grid.geojson"
        },
        {
            "name": "2. Indicator Processing",
            "script": "processing/calculate_indicators.py", # Example script name
            "output": "data/indicators.geojson"
        },
        {
            "name": "3. Scoring & Clustering",
            "script": "modeling/score_and_cluster.py", # Example script name
            "output": "data/cells_master.geojson"
        },
        {
            "name": "4. Explanations (SHAP)",
            "script": "modeling/explain_shap.py", # Example script name
            "output": "data/cell_explanations.json"
        }
    ]
    
    logger.info("Executing Pipeline Steps...")
    
    # In a real run, if a previous step fails, we might want to stop.
    # Here we try to run them sequentially.
    for step in pipeline:
        success = run_step(step["name"], step["script"], step["output"], logger)
        if not success:
            logger.warning(f"Step '{step['name']}' did not complete successfully or script is missing. Continuing to next step...")
            
    logger.info("=== City Sense Pipeline Finished ===")

if __name__ == "__main__":
    main()
