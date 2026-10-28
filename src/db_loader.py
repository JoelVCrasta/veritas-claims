from __future__ import annotations

import csv
import json
import logging
import sqlite3
import sqlite_utils
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("veritas.db_loader")

SCHEMA_CSV_PATH = Path("assets/OUTPUT_database table/Ourput-table-ideal-schema.csv")


def load_schema_from_csv(
    path: Path = SCHEMA_CSV_PATH,
) -> List[Tuple[str, str]]:
    columns: List[Tuple[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            col_name = row["column_name"].strip()
            data_type = row.get("data_type", "STRING").strip().upper()
            if col_name == "id":
                sqlite_type = "TEXT PRIMARY KEY"
            elif data_type in ("FLOAT64", "FLOAT", "REAL"):
                sqlite_type = "REAL"
            elif data_type in ("INT64", "INTEGER", "INT"):
                sqlite_type = "INTEGER"
            else:
                sqlite_type = "TEXT"
            columns.append((col_name, sqlite_type))
    return columns


COLUMNS: List[Tuple[str, str]] = load_schema_from_csv()
COLUMN_NAMES: List[str] = [col[0] for col in COLUMNS]


class DatabaseManager:
    """Handles schema creation, upserts, and dead-letter operations."""

    def __init__(self, db_path: str | Path = "data/veritas.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self) -> None:
        cols_ddl = ",\n    ".join([f"{name} {dtype}" for name, dtype in COLUMNS])

        create_canonical_sql = f"""
        CREATE TABLE IF NOT EXISTS canonical_records (
            {cols_ddl}
        );
        """

        create_dlq_sql = """
        CREATE TABLE IF NOT EXISTS dead_letter_records (
            id TEXT PRIMARY KEY,
            file_path TEXT,
            source_system TEXT,
            error_type TEXT,
            error_message TEXT,
            raw_payload TEXT,
            created_at TEXT
        );
        """

        create_runs_sql = """
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id TEXT PRIMARY KEY,
            file_name TEXT,
            start_time TEXT,
            end_time TEXT,
            duration_ms REAL DEFAULT 0.0,
            status TEXT,
            files_scanned INTEGER DEFAULT 1,
            files_processed INTEGER DEFAULT 0,
            files_failed INTEGER DEFAULT 0,
            records_loaded INTEGER DEFAULT 0,
            records_flagged INTEGER DEFAULT 0,
            duplicates INTEGER DEFAULT 0,
            duplicates_suppressed INTEGER DEFAULT 0
        );
        """

        indexes_sql = """
        CREATE INDEX IF NOT EXISTS idx_canonical_doc_id ON canonical_records(document_id);
        CREATE INDEX IF NOT EXISTS idx_canonical_record_type ON canonical_records(record_type);
        CREATE INDEX IF NOT EXISTS idx_canonical_test_canonical ON canonical_records(test_name_canonical);
        CREATE INDEX IF NOT EXISTS idx_canonical_analytics ON canonical_records(test_analytics);
        CREATE INDEX IF NOT EXISTS idx_canonical_source_system ON canonical_records(source_system);
        CREATE INDEX IF NOT EXISTS idx_dlq_source_system ON dead_letter_records(source_system);
        """

        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(create_canonical_sql)
                cursor.execute(create_dlq_sql)
                cursor.execute(create_runs_sql)
                for stmt in indexes_sql.strip().split(";"):
                    if stmt.strip():
                        cursor.execute(stmt)
        finally:
            conn.close()

        logger.info(f"Database initialized at {self.db_path} with schema.")

    def insert_records(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0

        conn = self._get_connection()
        try:
            db = sqlite_utils.Database(conn)
            db["canonical_records"].upsert_all(records, pk="id", alter=True)
        finally:
            conn.close()

        logger.debug(f"Inserted {len(records)} canonical records.")
        return len(records)

    def insert_dead_letter(
        self,
        record_id: str,
        file_path: str,
        source_system: str,
        error_type: str,
        error_message: str,
        raw_payload: Any,
    ) -> None:
        """Insert a failed record or malformed file into dead_letter_records."""
        payload_str = (
            json.dumps(raw_payload) if not isinstance(raw_payload, str) else raw_payload
        )
        now_ts = datetime.now(timezone.utc).isoformat()

        conn = self._get_connection()
        try:
            db = sqlite_utils.Database(conn)
            db["dead_letter_records"].upsert(
                {
                    "id": record_id,
                    "file_path": file_path,
                    "source_system": source_system,
                    "error_type": error_type,
                    "error_message": error_message,
                    "raw_payload": payload_str,
                    "created_at": now_ts,
                },
                pk="id",
            )
        finally:
            conn.close()

    def record_pipeline_run(self, run_stats: Dict[str, Any]) -> None:
        """Log pipeline execution statistics."""
        conn = self._get_connection()
        try:
            db = sqlite_utils.Database(conn)
            db["pipeline_runs"].upsert(
                {
                    "run_id": run_stats.get("run_id"),
                    "file_name": run_stats.get("file_name", ""),
                    "start_time": run_stats.get("start_time"),
                    "end_time": run_stats.get("end_time"),
                    "duration_ms": run_stats.get("duration_ms", 0.0),
                    "status": run_stats.get("status"),
                    "files_scanned": run_stats.get("files_scanned", 1),
                    "files_processed": run_stats.get("files_processed", 0),
                    "files_failed": run_stats.get("files_failed", 0),
                    "records_loaded": run_stats.get("records_loaded", 0),
                    "records_flagged": run_stats.get("records_flagged", 0),
                    "duplicates": run_stats.get(
                        "duplicates", run_stats.get("duplicates_suppressed", 0)
                    ),
                    "duplicates_suppressed": run_stats.get(
                        "duplicates_suppressed", run_stats.get("duplicates", 0)
                    ),
                },
                pk="run_id",
                alter=True,
            )
        finally:
            conn.close()

    def _query(
        self, sql: str, params: Tuple[Any, ...] | List[Any] = ()
    ) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            db = sqlite_utils.Database(conn)
            return list(db.query(sql, tuple(params)))
        finally:
            conn.close()

    def get_summary_stats(self) -> Dict[str, Any]:
        """Aggregate total counts for dashboard cards."""
        summary_sql = """
        SELECT 
            COUNT(*) AS total_records,
            COUNT(DISTINCT document_id) AS total_documents,
            SUM(CASE WHEN test_analytics IN ('OUTLIER', 'ABOVE_RANGE', 'BELOW_RANGE', 'INVALID') THEN 1 ELSE 0 END) AS flagged_records,
            SUM(CASE WHEN test_analytics = 'OUTLIER' THEN 1 ELSE 0 END) AS outlier_records
        FROM canonical_records
        """
        rows = self._query(summary_sql)
        res = rows[0] if rows else {}
        dlq_rows = self._query("SELECT COUNT(*) AS dlq_count FROM dead_letter_records")
        runs_rows = self._query("SELECT COUNT(*) AS total_runs FROM pipeline_runs")
        return {
            "total_records": res.get("total_records") or 0,
            "total_documents": res.get("total_documents") or 0,
            "flagged_records": res.get("flagged_records") or 0,
            "outlier_records": res.get("outlier_records") or 0,
            "dead_letter_count": (dlq_rows[0].get("dlq_count") if dlq_rows else 0) or 0,
            "total_runs": (runs_rows[0].get("total_runs") if runs_rows else 0) or 0,
        }

    def get_flagged_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve flagged records (outliers, out-of-range, invalid)."""
        sql = """
        SELECT id, document_id, record_type, source_system, claim_no, uhid, patient_name,
               test_name_canonical, test_name_original, result_value, result_text,
               unit_canonical, range_text, test_analytics, normalization_method, processed_at
        FROM canonical_records
        WHERE test_analytics IN ('OUTLIER', 'ABOVE_RANGE', 'BELOW_RANGE', 'INVALID')
        ORDER BY processed_at DESC
        LIMIT ?
        """
        return self._query(sql, (limit,))

    def get_clinic_quality_stats(self) -> List[Dict[str, Any]]:
        """Calculate quality metrics by source system."""
        sql = """
        SELECT
            source_system,
            COUNT(*) AS total_records,
            COUNT(DISTINCT document_id) AS total_documents,
            SUM(CASE WHEN test_analytics = 'OUTLIER' THEN 1 ELSE 0 END) AS outlier_count,
            SUM(CASE WHEN test_analytics IN ('ABOVE_RANGE', 'BELOW_RANGE') THEN 1 ELSE 0 END) AS out_of_range_count,
            SUM(CASE WHEN normalization_method = 'UNMAPPED' AND record_type = 'lab_test' THEN 1 ELSE 0 END) AS unmapped_tests,
            SUM(CASE WHEN age IS NULL OR age = '' THEN 1 ELSE 0 END) AS missing_age_count
        FROM canonical_records
        GROUP BY source_system
        """
        rows = self._query(sql)
        dlq_rows = self._query(
            "SELECT source_system, COUNT(*) AS cnt FROM dead_letter_records GROUP BY source_system"
        )
        dlq_map = {r["source_system"]: r["cnt"] for r in dlq_rows}

        for r in rows:
            r["dead_letters"] = dlq_map.get(r["source_system"], 0)
            tot = r["total_records"]
            r["outlier_rate"] = (
                round((r["outlier_count"] / tot) * 100, 2) if tot else 0.0
            )

        return rows

    def search_records(self, query: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        """Search canonical records by document_id, patient_name, uhid, claim_no, or test name."""
        if not query:
            return self._query(
                "SELECT * FROM canonical_records ORDER BY processed_at DESC LIMIT ?",
                (limit,),
            )
        pattern = f"%{query.strip()}%"
        sql = """
        SELECT * FROM canonical_records
        WHERE document_id LIKE ? OR patient_name LIKE ? OR uhid LIKE ?
           OR claim_no LIKE ? OR test_name_canonical LIKE ? OR medicine LIKE ?
        ORDER BY processed_at DESC LIMIT ?
        """
        return self._query(
            sql, (pattern, pattern, pattern, pattern, pattern, pattern, limit)
        )

    def get_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve aggregated reports grouped by document_id."""
        sql = """
        SELECT 
            document_id,
            MAX(claim_no) AS claim_no,
            MAX(patient_name) AS patient_name,
            MAX(age) AS age,
            MAX(gender) AS gender,
            MAX(uhid) AS uhid,
            MAX(hospital_name) AS hospital_name,
            MAX(doctor_name) AS doctor_name,
            MAX(source_system) AS source_system,
            MAX(file_gcs_path) AS file_gcs_path,
            MAX(admission_date) AS admission_date,
            MAX(discharge_date) AS discharge_date,
            MAX(reports_date) AS reports_date,
            MAX(CASE WHEN record_type = 'discharge_summary' THEN diagnosis ELSE NULL END) AS primary_diagnosis,
            SUM(CASE WHEN record_type = 'lab_test' THEN 1 ELSE 0 END) AS lab_count,
            SUM(CASE WHEN record_type = 'medication' THEN 1 ELSE 0 END) AS med_count,
            SUM(CASE WHEN test_analytics IN ('OUTLIER', 'ABOVE_RANGE', 'BELOW_RANGE', 'INVALID') THEN 1 ELSE 0 END) AS flag_count,
            MAX(processed_at) AS processed_at
        FROM canonical_records
        GROUP BY document_id
        ORDER BY processed_at DESC
        LIMIT ?
        """
        return self._query(sql, (limit,))

    def get_existing_document_ids(self) -> Set[str]:
        """Fetch set of all distinct document_ids currently stored in canonical_records."""
        rows = self._query(
            "SELECT DISTINCT document_id FROM canonical_records WHERE document_id IS NOT NULL AND document_id != ''"
        )
        return {r["document_id"] for r in rows if r.get("document_id")}

    def get_records(
        self,
        record_type: Optional[str] = None,
        flag: Optional[str] = None,
        query: str = "",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve records filtered by record_type, analytics flag, and search query."""
        clauses = []
        params: List[Any] = []

        if record_type and record_type.lower() != "all":
            clauses.append("record_type = ?")
            params.append(record_type)

        if flag and flag.upper() != "ALL":
            clauses.append("test_analytics = ?")
            params.append(flag.upper())

        if query and query.strip():
            pat = f"%{query.strip()}%"
            clauses.append(
                "(document_id LIKE ? OR patient_name LIKE ? OR uhid LIKE ? OR claim_no LIKE ? OR test_name_canonical LIKE ? OR medicine LIKE ?)"
            )
            params.extend([pat, pat, pat, pat, pat, pat])

        where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM canonical_records {where_str} ORDER BY processed_at DESC LIMIT ?"
        params.append(limit)
        return self._query(sql, params)

    def get_pipeline_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve pipeline run history."""
        return self._query(
            "SELECT * FROM pipeline_runs ORDER BY start_time DESC LIMIT ?", (limit,)
        )

    def get_audited_file_names(self) -> List[str]:
        """Retrieve distinct file names that have already been recorded in pipeline_runs."""
        rows = self._query(
            "SELECT DISTINCT file_name FROM pipeline_runs WHERE file_name IS NOT NULL AND file_name != ''"
        )
        return [r["file_name"] for r in rows]

    def get_dead_letter_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve records from dead-letter queue."""
        return self._query(
            "SELECT * FROM dead_letter_records ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    def get_document_bundle(self, document_id: str) -> Dict[str, Any]:
        """Fetch full report: document summary, lab tests, medications, and raw JSON."""
        rows = self._query(
            "SELECT * FROM canonical_records WHERE document_id = ? ORDER BY id",
            (document_id,),
        )

        if not rows:
            return {}

        lab_tests = [r for r in rows if r.get("record_type") == "lab_test"]
        medications = [r for r in rows if r.get("record_type") == "medication"]
        discharge_record = next(
            (r for r in rows if r.get("record_type") == "discharge_summary"), None
        )

        first = rows[0]
        file_path = first.get("file_gcs_path")
        raw_json = None
        if file_path:
            p = Path(file_path)
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as fp:
                        raw_json = json.load(fp)
                except Exception as err:
                    logger.warning(f"Could not read raw JSON file {file_path}: {err}")

        summary = {
            "document_id": document_id,
            "patient_name": first.get("patient_name")
            or (discharge_record.get("patient_name") if discharge_record else ""),
            "age": first.get("age")
            or (discharge_record.get("age") if discharge_record else ""),
            "gender": first.get("gender")
            or (discharge_record.get("gender") if discharge_record else ""),
            "uhid": first.get("uhid") or "",
            "hospital_name": first.get("hospital_name") or "",
            "doctor_name": first.get("doctor_name") or "",
            "claim_no": first.get("claim_no") or "",
            "source_system": first.get("source_system") or "",
            "file_gcs_path": file_path or "",
            "admission_date": (
                discharge_record.get("admission_date", "") if discharge_record else ""
            ),
            "discharge_date": (
                discharge_record.get("discharge_date", "") if discharge_record else ""
            ),
            "reports_date": first.get("reports_date") or "",
            "diagnosis": (
                discharge_record.get("diagnosis", "") if discharge_record else ""
            ),
            "brief_history": (
                discharge_record.get("brief_history", "") if discharge_record else ""
            ),
            "general_examinations": (
                discharge_record.get("general_examinations", "")
                if discharge_record
                else ""
            ),
            "recommendations": (
                discharge_record.get("recommendations", "") if discharge_record else ""
            ),
            "ward": discharge_record.get("ward", "") if discharge_record else "",
            "post_discharge_advice": (
                discharge_record.get("post_discharge_advice", "")
                if discharge_record
                else ""
            ),
            "lab_count": len(lab_tests),
            "med_count": len(medications),
            "processed_at": first.get("processed_at"),
        }

        return {
            "document_id": document_id,
            "summary": summary,
            "discharge_record": discharge_record,
            "lab_tests": lab_tests,
            "medications": medications,
            "raw_json": raw_json,
        }
