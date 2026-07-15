import os
import json
import hashlib
import logging
from datetime import datetime

# set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_json_file(filepath):
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded file: {filepath}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {filepath}: {e}")
        return None
    except Exception as e:
        logger.error(f"Could not read file {filepath}: {e}")
        return None


def get_all_json_files(folder_path):
    """
    Find all JSON files in the given folder.
    Returns a list of file paths.
    """
    json_files = []
    if not os.path.exists(folder_path):
        logger.error(f"Folder not found: {folder_path}")
        return json_files

    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            full_path = os.path.join(folder_path, filename)
            json_files.append(full_path)

    logger.info(f"Found {len(json_files)} JSON files in {folder_path}")
    return json_files


def compute_hash(data):
    """
    Create a unique hash of the JSON content.
    Used for duplicate detection (FR-1.2).
    We hash based on document_id + trace_id if available,
    else hash the full content.
    """
    try:
        doc_id = data.get("data", {}).get("documentId", "")
        trace_id = data.get("traceId", "")
        # combine them as a unique key
        key = f"{doc_id}_{trace_id}"
        if key == "_":
            # fallback: hash full content
            key = json.dumps(data, sort_keys=True)
        return hashlib.md5(key.encode()).hexdigest()
    except Exception:
        # if anything goes wrong just hash the full thing
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()


def ingest_files(folder_path):
    """
    Main ingestion function.
    - Reads all JSON files from folder
    - Validates them
    - Removes duplicates
    - Returns list of unique, valid records
    """
    files = get_all_json_files(folder_path)

    seen_hashes = set()
    valid_records = []
    error_records = []

    for filepath in files:
        data = load_json_file(filepath)

        if data is None:
            # file failed to load - add to errors
            error_records.append({
                "filepath": filepath,
                "error": "Could not parse JSON",
                "timestamp": datetime.now().isoformat()
            })
            continue

        # basic validation - check required fields exist
        if "data" not in data:
            logger.warning(f"File missing 'data' key: {filepath}")
            error_records.append({
                "filepath": filepath,
                "error": "Missing 'data' field in JSON",
                "timestamp": datetime.now().isoformat()
            })
            continue

        # check for duplicate
        record_hash = compute_hash(data)
        if record_hash in seen_hashes:
            logger.warning(f"Duplicate file skipped: {filepath}")
            continue

        seen_hashes.add(record_hash)

        # add source file info for audit trail (FR-4.3)
        data["_source_file"] = filepath
        data["_ingested_at"] = datetime.now().isoformat()
        data["_record_hash"] = record_hash

        valid_records.append(data)

    logger.info(f"Ingestion done: {len(valid_records)} valid, {len(error_records)} errors")
    return valid_records, error_records
