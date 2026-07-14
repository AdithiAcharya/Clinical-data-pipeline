# Medical Data Pipeline 

> **Note**: All the source code and required files for this assignment are located in the `master` branch of this repository.

A data pipeline that reads clinical JSON files, standardizes the data, validates it, and stores it in a database. Also includes a simple web dashboard for monitoring.

## What This Does

The pipeline reads JSON files containing lab reports and discharge summaries from hospitals. It:

- Normalizes test names (e.g., "aemoglobin" → "Hemoglobin")
- Extracts numeric values from text (e.g., "12.0 g/dL" → 12.0)
- Standardizes units across clinics
- Validates results against medical reference ranges
- Flags outliers and out-of-range values
- Loads everything into a SQLite database
- Shows a web dashboard for the ops team

## Project Structure

```
├── README.md
├── requirements.txt
├── src/
│   ├── ingestion.py        # reads JSON files, handles duplicates
│   ├── standardisation.py  # test name, unit, and demographic normalization
│   ├── validation.py       # range checks and outlier detection
│   ├── db_loader.py        # loads data into SQLite
│   ├── pipeline.py         # main runner that ties everything together
│   └── app.py              # Flask web dashboard
├── config/
│   ├── test_name_mapping.json      # test name variants → canonical
│   ├── unit_mapping.json           # unit variants → canonical
│   ├── reference_ranges.json       # normal ranges per test
│   ├── medicine_mapping.json       # brand → generic medicine
│   └── clinic_config.json          # per-clinic field mappings
├── templates/
│   ├── index.html          # dashboard home
│   ├── records.html        # record inspector
│   ├── flagged.html        # flagged records queue
│   └── clinic_stats.html   # clinic-level quality stats
├── tests/
│   ├── test_standardisation.py
│   └── test_validation.py
├── docs/
│   ├── architecture.md
│   └── assumptions.md
└── sample-data/            # the 5 input JSON files
```

## Setup Instructions

### Requirements

- Python 3.8 or higher
- pip

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the pipeline

This will read all JSON files from the `sample-data` folder and load them into the database:

```bash
python src/pipeline.py
```

You can also point it to a different folder:

```bash
python src/pipeline.py --folder sample-data
```

### Start the web dashboard

```bash
python src/app.py
```

Then open your browser at: **http://localhost:5000**

You can also click "Run Pipeline Now" in the dashboard to trigger the pipeline.

### Run the tests

```bash
python -m pytest tests/ -v
```

## Key Design Decisions

### 1. Config-driven, not code-driven

All test name mappings, unit conversions, and reference ranges are in JSON config files. To add support for a new clinic or a new test name variant, you just update the config file. No code changes needed.

### 2. Idempotent pipeline

Running the pipeline multiple times on the same files will not create duplicate records in the database. It uses `INSERT OR IGNORE` with a unique constraint on document_id + test_name + result.

### 3. Fail-safe ingestion

If one JSON file is malformed or fails to process, the pipeline skips it, logs the error, and continues with the remaining files. One bad file doesn't break the whole pipeline.

### 4. Two-step test name matching

Test names are matched first by exact lookup, then by fuzzy string matching (difflib). This handles typos and minor spelling variations.

## Architecture Summary

```
JSON Files → Ingestion → Standardization → Validation → SQLite DB → Web UI
```

See `docs/architecture.md` for more details.

## Assumptions

See `docs/assumptions.md` for the full list of assumptions made.

## Known Limitations

- Uses SQLite instead of BigQuery/PostgreSQL (fine for prototype, not for production scale)
- UI is simple and has no authentication
- Fuzzy matching can occasionally misidentify test names with very different spelling
- Medicine mapping is manually maintained

## Sample Data

The `sample-data` folder contains 5 JSON files provided with the assignment:

- Files 1, 3: Discharge summaries (maternity case)
- File 2: Lab report + discharge summary (fever case)
- File 4: Large lab report (multiple test categories)
- File 5: Lab report with vital signs and CBC
