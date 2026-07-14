# Assumptions Document

## Business Assumptions

1. **Volume**: The 200k files/day mentioned is for the production system. For this assignment I'm working with the 5 sample files provided.

2. **Clinics**: I assumed all sample files come from the "FASTTRACK" source system, which is shown in the metaDetails of each JSON. A new clinic would have a different source_system value.

3. **PII**: Patient names, ages, genders, doctor names, hospital names, etc. are already redacted in the sample data (shown as "[PATIENT NAME REDACTED]"). I kept them as-is. In production, these would need proper PII tokenization before storage.

4. **Claim processing**: I focused on data standardization/ingestion. The actual claim adjudication logic (fraud detection, risk modeling) is out of scope for this assignment.

5. **Medical reference ranges**: I used commonly accepted normal ranges for lab tests. These would need to be verified with a clinical team in production since ranges can vary by patient demographics (age, gender, pregnancy status, etc.).

## Technical Assumptions

1. **Database**: I used SQLite for simplicity. It works perfectly for this prototype. In production with 200k files/day, I'd switch to BigQuery or PostgreSQL.

2. **File storage**: I read files from a local folder. In production, this would be a GCS bucket with event triggers on file upload.

3. **Deduplication**: I hash document_id + traceId to detect duplicates. If both are empty, I hash the full JSON content.

4. **Test name fuzzy matching**: I used Python's built-in `difflib` with a threshold of 0.7 similarity. In production, a more sophisticated NLP model or a pre-built medical NLP library would work better.

5. **Date parsing**: I handle the most common date formats seen in the sample data. Edge cases with unusual formats will return the original string.

6. **Flask UI**: The web UI is intentionally simple. It's functional for an ops team but not production-grade. In production you'd use something more robust with proper auth.

## Data Assumptions

1. **Redacted fields**: Many fields are shown as "[PATIENT NAME REDACTED]" etc. I treat these as null values in the database. I didn't try to de-anonymize them.

2. **Mixed result formats**: Some test results have the value and unit combined in the result field (e.g., "13.7 g/dl"). I extract just the numeric part for result_value and keep the full string as result_text.

3. **Multi-value results**: Some fields have comma-separated values like "NEUTROPHILS 2230.8 cells/cu.mm, LYMPHOCYTES 1716 cells/cu.mm, ...". I flag these but don't try to split them into separate rows - that would need more careful domain knowledge.

4. **Duplicate JSON files**: File3.json and File3 (1).json appear to be the same file (same document_id). My deduplication logic correctly handles this.

5. **Missing reference ranges**: Not every test name in the sample data has a reference range in my config. For those, I classify them as "Not Evaluated" instead of guessing.

## Scope Exclusions

| What I left out | Why | Production approach |
|----------------|-----|---------------------|
| GCS integration | Would need cloud credentials | Use google-cloud-storage library |
| Authentication for UI | Out of scope for prototype | Add OAuth or basic auth |
| Real-time streaming | Not needed for batch files | Use Pub/Sub + Cloud Run |
| Horizontal scaling | Single machine is fine for prototype | Containerize and use Cloud Run |
| Advanced NLP for test names | difflib works well for this dataset | Use a medical NLP model |
| PDF/image parsing | Sample data is already parsed JSON | Use OCR pipeline upstream |
| Alerting | No monitoring infra | Use Cloud Monitoring |
| Data lineage tracking | Partial - source file is recorded | Use a proper lineage tool |

## Known Limitations

1. The fuzzy matching for test names can sometimes map to wrong canonical names if variants are too ambiguous
2. SQLite doesn't support concurrent writes well - would need PostgreSQL for multiple workers
3. The UI has no pagination limit on clinic stats page if there are many clinics
4. Medicine mapping is manually maintained and will miss new brand names

## What I Would Do With More Time

1. Add a proper config validation step to check all config files are consistent
2. Build a better test name normalization using embeddings or a medical terminology API
3. Add more unit tests especially for edge cases in the ingestion module
4. Add proper logging rotation so log files don't grow forever
5. Write a proper data dictionary explaining each column in the output schema
