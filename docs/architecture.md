# Architecture Overview

## Problem Summary

Multiple hospitals/clinics send medical JSON files (lab reports and discharge summaries) to a central system. These files have different field names, different units, misspelled test names, etc. We need to standardize all of this and load it into a database for analytics and fraud detection.

## High Level Architecture

```
[Clinic JSON Files]
       |
       v
[1. Ingestion Layer]   <-- ingestion.py
   - Read JSON files from a folder (simulating GCS bucket)
   - Detect and skip duplicates using hash of document_id + traceId
   - Log malformed files to error log
       |
       v
[2. Standardization Layer]   <-- standardisation.py
   - Normalize test names: "aemoglobin" -> "Hemoglobin" (exact + fuzzy match)
   - Extract numeric values from strings: "12.0 g/dL" -> 12.0
   - Standardize units: "mil/cu.mm" -> "Million/cu.mm"
   - Normalize gender: "M" -> "Male", "F" -> "Female"
   - Normalize dates to ISO 8601: "07-Oct-2025" -> "2025-10-07"
   - Map brand medicines to generic: "Tab. miso" -> "Misoprostol"
       |
       v
[3. Validation Layer]   <-- validation.py
   - Check each numeric result against reference ranges
   - Flag outliers (physiologically impossible values)
   - Classify as: Within Range / Above Range / Below Range / Outlier / Invalid
       |
       v
[4. Database Layer]   <-- db_loader.py
   - Load into SQLite (local) - would be BigQuery/PostgreSQL in production
   - Idempotent inserts using INSERT OR IGNORE
   - Error log table for failed records
   - Pipeline run history table
       |
       v
[5. Web Dashboard]   <-- app.py
   - Flask web app
   - Pipeline run summary
   - Record inspector with search
   - Flagged records queue
   - Clinic-level stats
```

## Configuration-Driven Design (NFR-2.1: Zero-Code Onboarding)

All mappings are stored in JSON config files under `/config`:

| File | Purpose |
|------|---------|
| test_name_mapping.json | Maps variant test names to canonical names |
| unit_mapping.json | Maps unit variants to canonical units per test |
| reference_ranges.json | Medical reference ranges for each test |
| medicine_mapping.json | Brand to generic medicine mapping |
| clinic_config.json | Per-clinic field mappings |

To add a new clinic, just update the config files. No code changes needed.

## Technology Choices

| Component | Choice | Reason |
|-----------|--------|--------|
| Language | Python 3 | Simple, good for data processing, many libraries |
| Database | SQLite | Easy to set up locally, no server needed |
| Web Framework | Flask | Lightweight, simple to understand |
| Fuzzy Matching | difflib (stdlib) | No extra dependency needed |
| Testing | unittest + pytest | Standard Python testing |

## Production Considerations

In production (at 200k files/day scale) I would change:
- **Storage**: GCS bucket for input files instead of local folder
- **Processing**: Cloud Run jobs or Dataflow for parallel processing
- **Database**: BigQuery for columnar storage and analytics at scale
- **Monitoring**: Cloud Monitoring / Prometheus for metrics and alerting
- **Queue**: Pub/Sub or Cloud Tasks for file arrival events
- **Error handling**: Dead-letter queue in a separate GCS bucket or BigQuery table

## Error Handling

- Malformed JSON files are logged and skipped (pipeline continues)
- Records that fail standardization go to error_log table
- Failed records don't block processing of other records (FR-3.1 equivalent)
