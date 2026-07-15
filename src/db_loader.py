

import sqlite3
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Default DB path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pipeline_data.db")


def get_connection(db_path=None):
    """Get a connection to the SQLite database."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn


def create_tables(conn):
    """
    Create the tables if they don't exist.
    Schema is based on the canonical column spec from the assignment.
    """
    cursor = conn.cursor()

    # Main records table - stores lab report rows
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT,
            record_type TEXT,
            trace_id TEXT,
            correlation_id TEXT,
            source_system TEXT,
            claim_no TEXT,
            nt_code TEXT,
            consumer_client_id TEXT,
            destination_identifier TEXT,
            patient_name TEXT,
            age TEXT,
            age_years REAL,
            gender TEXT,
            uhid TEXT,
            hospital_name TEXT,
            doctor_name TEXT,
            bill_date TEXT,
            reports_date TEXT,
            test_name_canonical TEXT,
            test_name_original TEXT,
            result_value REAL,
            result_text TEXT,
            unit_canonical TEXT,
            unit_original TEXT,
            range_low REAL,
            range_high REAL,
            range_text TEXT,
            test_analytics TEXT,
            analytics_classification TEXT,
            normalization_method TEXT,
            normalization_confidence REAL,
            is_outlier INTEGER DEFAULT 0,
            is_flagged INTEGER DEFAULT 0,
            flag_reason TEXT,
            admission_date TEXT,
            discharge_date TEXT,
            diagnosis TEXT,
            brief_history TEXT,
            general_examinations TEXT,
            recommendations TEXT,
            hospital_address TEXT,
            ward TEXT,
            post_discharge_advice TEXT,
            medicine TEXT,
            medicine_original TEXT,
            dose TEXT,
            frequency TEXT,
            medicine_type TEXT,
            page_no INTEGER,
            processed_at TEXT,
            ingested_at TEXT,
            UNIQUE(document_id, test_name_original, result_text, medicine)
        )
    """)

    # Error log table (FR-4.2)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS error_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT,
            error_message TEXT,
            timestamp TEXT
        )
    """)

    # Pipeline run summary table (for the dashboard)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT,
            total_files INTEGER,
            processed_files INTEGER,
            failed_files INTEGER,
            total_records INTEGER,
            flagged_records INTEGER
        )
    """)

    conn.commit()
    logger.info("Database tables created/verified")


def insert_records(conn, rows):
    """
    Insert rows into the records table.
    Uses INSERT OR IGNORE so duplicates are skipped (idempotent - FR-3.2 equivalent).
    """
    cursor = conn.cursor()
    inserted = 0
    skipped = 0

    now = datetime.now().isoformat()

    # All possible fields with defaults - ensures no missing parameter errors
    FIELD_DEFAULTS = {
        "document_id": None, "record_type": None, "trace_id": None,
        "source_system": None, "claim_no": None, "nt_code": None,
        "consumer_client_id": None, "destination_identifier": None,
        "patient_name": None, "age": None, "age_years": None,
        "gender": None, "uhid": None, "hospital_name": None,
        "doctor_name": None, "bill_date": None, "reports_date": None,
        "test_name_canonical": None, "test_name_original": None,
        "result_value": None, "result_text": None,
        "unit_canonical": None, "unit_original": None,
        "range_low": None, "range_high": None, "range_text": None,
        "test_analytics": None, "analytics_classification": None,
        "normalization_method": None, "normalization_confidence": None,
        "is_outlier": 0, "is_flagged": 0, "flag_reason": None,
        "admission_date": None, "discharge_date": None,
        "diagnosis": None, "brief_history": None,
        "general_examinations": None, "recommendations": None,
        "hospital_address": None, "ward": None, "post_discharge_advice": None,
        "medicine": None, "medicine_original": None,
        "dose": None, "frequency": None, "medicine_type": None,
        "page_no": None, "correlation_id": None,
        "processed_at": now,
    }

    for row in rows:
        # merge defaults with the actual row data
        row_with_ts = {**FIELD_DEFAULTS, **row}
        row_with_ts["processed_at"] = now

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO records (
                    document_id, record_type, trace_id, source_system,
                    claim_no, nt_code, consumer_client_id, destination_identifier,
                    patient_name, age, age_years, gender, uhid,
                    hospital_name, doctor_name, bill_date, reports_date,
                    test_name_canonical, test_name_original,
                    result_value, result_text,
                    unit_canonical, unit_original,
                    range_low, range_high, range_text,
                    test_analytics, analytics_classification,
                    normalization_method, normalization_confidence,
                    is_outlier, is_flagged, flag_reason,
                    admission_date, discharge_date, diagnosis, brief_history,
                    general_examinations, recommendations, hospital_address,
                    ward, post_discharge_advice,
                    medicine, medicine_original, dose, frequency, medicine_type,
                    page_no, processed_at
                ) VALUES (
                    :document_id, :record_type, :trace_id, :source_system,
                    :claim_no, :nt_code, :consumer_client_id, :destination_identifier,
                    :patient_name, :age, :age_years, :gender, :uhid,
                    :hospital_name, :doctor_name, :bill_date, :reports_date,
                    :test_name_canonical, :test_name_original,
                    :result_value, :result_text,
                    :unit_canonical, :unit_original,
                    :range_low, :range_high, :range_text,
                    :test_analytics, :analytics_classification,
                    :normalization_method, :normalization_confidence,
                    :is_outlier, :is_flagged, :flag_reason,
                    :admission_date, :discharge_date, :diagnosis, :brief_history,
                    :general_examinations, :recommendations, :hospital_address,
                    :ward, :post_discharge_advice,
                    :medicine, :medicine_original, :dose, :frequency, :medicine_type,
                    :page_no, :processed_at
                )
            """, row_with_ts)

            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1

        except Exception as e:
            logger.error(f"Error inserting row: {e}")
            skipped += 1

    conn.commit()
    logger.info(f"DB: {inserted} inserted, {skipped} skipped (duplicates)")
    return inserted, skipped


def log_errors(conn, error_records):
    """Save error records to the error_log table (FR-4.2)."""
    cursor = conn.cursor()
    for err in error_records:
        cursor.execute("""
            INSERT INTO error_log (filepath, error_message, timestamp)
            VALUES (?, ?, ?)
        """, (err.get("filepath", ""), err.get("error", ""), err.get("timestamp", "")))
    conn.commit()


def save_pipeline_run(conn, stats):
    """Save stats from this pipeline run."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pipeline_runs (run_at, total_files, processed_files, failed_files, total_records, flagged_records)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        stats.get("total_files", 0),
        stats.get("processed_files", 0),
        stats.get("failed_files", 0),
        stats.get("total_records", 0),
        stats.get("flagged_records", 0),
    ))
    conn.commit()


def load_to_database(rows, error_records, stats, db_path=None):
    """
    Main function to load everything into the database.
    """
    conn = get_connection(db_path)
    create_tables(conn)

    inserted, skipped = insert_records(conn, rows)
    log_errors(conn, error_records)
    save_pipeline_run(conn, stats)

    conn.close()
    logger.info(f"Database loading complete. Inserted: {inserted}, Skipped: {skipped}")
    return inserted, skipped
