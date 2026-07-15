"""

Run with:
    python src/app.py
Then open http://localhost:5000
"""

import os
import sys
import sqlite3
from flask import Flask, render_template, request, redirect, url_for

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.db_loader import get_connection, DB_PATH
from src.pipeline import run_pipeline

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)


def get_db():
    """Get DB connection. Returns None if DB doesn't exist yet."""
    if not os.path.exists(DB_PATH):
        return None
    return get_connection()


def get_pipeline_stats(conn):
    """Get the latest pipeline run stats."""
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


@app.route("/")
def index():
    """Dashboard home page - shows pipeline stats."""
    conn = get_db()
    stats = get_pipeline_stats(conn)
    total_records = 0
    total_flagged = 0
    lab_records = 0
    discharge_records = 0
    run_history = []

    if conn:
        try:
            total_records = conn.execute(
                "SELECT COUNT(*) FROM records"
            ).fetchone()[0]

            total_flagged = conn.execute(
                "SELECT COUNT(*) FROM records WHERE is_flagged = 1"
            ).fetchone()[0]

            lab_records = conn.execute(
                "SELECT COUNT(*) FROM records WHERE record_type = 'lab_report'"
            ).fetchone()[0]

            discharge_records = conn.execute(
                "SELECT COUNT(*) FROM records WHERE record_type = 'discharge_summary'"
            ).fetchone()[0]

            runs = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 5"
            ).fetchall()
            run_history = [dict(r) for r in runs]
        except Exception as e:
            pass
        conn.close()

    return render_template(
        "index.html",
        stats=stats,
        total_records=total_records,
        total_flagged=total_flagged,
        lab_records=lab_records,
        discharge_records=discharge_records,
        run_history=run_history
    )


@app.route("/records")
def records():
    """Record inspector - search and view records (FR-5.2)."""
    conn = get_db()
    all_records = []
    search_query = request.args.get("q", "")
    record_type = request.args.get("type", "all")
    page = int(request.args.get("page", 1))
    per_page = 25

    if conn:
        try:
            offset = (page - 1) * per_page
            base_query = "SELECT * FROM records WHERE 1=1"
            params = []

            if search_query:
                base_query += " AND (patient_name LIKE ? OR test_name_canonical LIKE ? OR document_id LIKE ?)"
                params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

            if record_type != "all":
                base_query += " AND record_type = ?"
                params.append(record_type)

            count = conn.execute(
                f"SELECT COUNT(*) FROM ({base_query})", params
            ).fetchone()[0]

            rows = conn.execute(
                base_query + f" ORDER BY id DESC LIMIT {per_page} OFFSET {offset}",
                params
            ).fetchall()
            all_records = [dict(r) for r in rows]
            conn.close()

        except Exception as e:
            pass

    total_pages = max(1, (count // per_page) + (1 if count % per_page else 0)) if all_records else 1

    return render_template(
        "records.html",
        records=all_records,
        search_query=search_query,
        record_type=record_type,
        page=page,
        total_pages=total_pages,
        total_count=count if all_records else 0
    )


@app.route("/flagged")
def flagged():
    """Show flagged records queue (FR-5.3)."""
    conn = get_db()
    flagged_records = []

    if conn:
        try:
            rows = conn.execute("""
                SELECT * FROM records
                WHERE is_flagged = 1
                ORDER BY is_outlier DESC, id DESC
                LIMIT 100
            """).fetchall()
            flagged_records = [dict(r) for r in rows]
            conn.close()
        except Exception as e:
            pass

    return render_template("flagged.html", flagged_records=flagged_records)


@app.route("/clinic-stats")
def clinic_stats():
    """Per-clinic data quality stats (FR-5.4)."""
    conn = get_db()
    stats_by_clinic = []

    if conn:
        try:
            rows = conn.execute("""
                SELECT
                    source_system,
                    COUNT(*) as total_records,
                    SUM(is_flagged) as flagged_count,
                    SUM(is_outlier) as outlier_count,
                    COUNT(CASE WHEN result_value IS NULL AND record_type='lab_report' THEN 1 END) as missing_numeric,
                    ROUND(CAST(SUM(is_flagged) AS FLOAT) / COUNT(*) * 100, 1) as flag_rate
                FROM records
                GROUP BY source_system
            """).fetchall()
            stats_by_clinic = [dict(r) for r in rows]
            conn.close()
        except Exception as e:
            pass

    return render_template("clinic_stats.html", stats_by_clinic=stats_by_clinic)


@app.route("/run-pipeline", methods=["POST"])
def trigger_pipeline():
    """Trigger a pipeline run from the UI."""
    project_root = os.path.dirname(os.path.dirname(__file__))
    input_folder = os.path.join(project_root, "sample-data")

    try:
        result = run_pipeline(input_folder)
        return redirect(url_for("index"))
    except Exception as e:
        return f"Pipeline error: {e}", 500


if __name__ == "__main__":
    print("Starting dashboard at http://localhost:5000")
    print("Make sure to run the pipeline first: python src/pipeline.py")
    app.run(debug=True, port=5000)
