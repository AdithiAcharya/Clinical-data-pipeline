"""
pipeline.py - Main Pipeline Runner

Ties together ingestion, standardization, validation, and DB loading.
Run this script to process all JSON files.

Usage:
    python src/pipeline.py
    python src/pipeline.py --folder sample-data
"""

import os
import sys
import logging
import argparse
from datetime import datetime

# Add parent dir to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.ingestion import ingest_files
from src.standardisation import standardize_record
from src.validation import validate_records
from src.db_loader import load_to_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_pipeline(input_folder, db_path=None):
    """
    Run the full pipeline:
    1. Ingest JSON files
    2. Standardize each record
    3. Validate records
    4. Load to DB
    """
    start_time = datetime.now()
    logger.info(f"=== Pipeline started at {start_time} ===")
    logger.info(f"Reading from: {input_folder}")

    # Step 1: Ingest
    logger.info("--- Step 1: Ingesting files ---")
    valid_records, error_records = ingest_files(input_folder)

    total_files = len(valid_records) + len(error_records)
    logger.info(f"Total files: {total_files}, Valid: {len(valid_records)}, Errors: {len(error_records)}")

    # Step 2: Standardize
    logger.info("--- Step 2: Standardizing records ---")
    all_rows = []
    for record in valid_records:
        try:
            rows = standardize_record(record)
            all_rows.extend(rows)
        except Exception as e:
            logger.error(f"Error standardizing record: {e}")
            error_records.append({
                "filepath": record.get("_source_file", "unknown"),
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

    logger.info(f"Standardization complete: {len(all_rows)} rows")

    # Step 3: Validate
    logger.info("--- Step 3: Validating records ---")
    validated_rows, flagged_rows = validate_records(all_rows)
    logger.info(f"Flagged records: {len(flagged_rows)}")

    # Step 4: Load to DB
    logger.info("--- Step 4: Loading to database ---")
    stats = {
        "total_files": total_files,
        "processed_files": len(valid_records),
        "failed_files": len(error_records),
        "total_records": len(validated_rows),
        "flagged_records": len(flagged_rows),
    }

    inserted, skipped = load_to_database(validated_rows, error_records, stats, db_path)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    logger.info("=== Pipeline complete ===")
    logger.info(f"Duration: {duration:.2f} seconds")
    logger.info(f"Files processed: {len(valid_records)}/{total_files}")
    logger.info(f"Records inserted: {inserted}, Skipped (duplicates): {skipped}")
    logger.info(f"Flagged records: {len(flagged_rows)}")

    return {
        "total_files": total_files,
        "processed_files": len(valid_records),
        "failed_files": len(error_records),
        "total_records": len(validated_rows),
        "inserted": inserted,
        "skipped": skipped,
        "flagged_records": len(flagged_rows),
        "duration_seconds": duration
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the medical data pipeline")
    parser.add_argument(
        "--folder",
        default="sample-data",
        help="Folder containing JSON files (default: sample-data)"
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite database file (default: pipeline_data.db)"
    )
    args = parser.parse_args()

    # Get the project root folder
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_folder = os.path.join(project_root, args.folder)

    result = run_pipeline(input_folder, args.db)
    print("\n=== Summary ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
