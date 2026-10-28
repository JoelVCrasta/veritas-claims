from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import load_pipeline_config
from src.db_loader import DatabaseManager
from src.ingestion import IngestedDocument, IngestionEngine, IngestionStatus
from src.models import CanonicalRecord, resolve_field_value
from src.standardisation import StandardisationEngine
from src.validation import ValidationEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("veritas.pipeline")


class Pipeline:
    def __init__(
        self,
        config_dir: str | Path = "config",
        db_path: str | Path = "data/veritas.db",
        active_checks: Optional[List[str]] = None,
    ) -> None:
        self.config = load_pipeline_config(config_dir)
        self.db = DatabaseManager(db_path)
        checks = (
            active_checks
            if active_checks is not None
            else self.config.dedup_active_checks
        )
        self.ingestion = IngestionEngine(
            active_checks=checks, clinic_mappings=self.config.clinic_mappings
        )
        existing_doc_ids = self.db.get_existing_document_ids()
        if existing_doc_ids:
            self.ingestion.load_existing_seen(document_ids=existing_doc_ids)
        self.standardiser = StandardisationEngine(self.config)
        self.validator = ValidationEngine(self.config)

    def _extract_labs(
        self,
        doc: IngestedDocument,
        data_block: Dict[str, Any],
        adapter: Dict[str, Any],
        base_meta: Dict[str, Any],
        doc_id: str,
        resp_idx: int,
    ) -> List[Dict[str, Any]]:
        """Extract and validate canonical lab test records from a report block."""
        patient_field_map = adapter.get("patient_fields", {})
        lab_fields = adapter.get("lab_fields", {})
        basic_info = (
            data_block.get("basic_info")
            or data_block.get("demographics")
            or data_block.get("patient")
            or data_block.get("patient_info")
            or data_block
        )
        demo = self.standardiser.standardize_demographics(
            basic_info, field_map=patient_field_map
        )
        header_facility = (
            doc.raw_payload.get("header", {}).get("facility", "")
            if isinstance(doc.raw_payload.get("header"), dict)
            else ""
        )
        facility_name = demo.hospital_name or header_facility

        demographics = {
            "patient_name": demo.patient_name,
            "age": demo.age,
            "age_years": demo.age_years,
            "age_text": demo.age_text,
            "gender": demo.gender,
            "uhid": demo.uhid,
            "hospital_name": facility_name,
            "doctor_name": demo.doctor_name,
            "bill_date": demo.bill_date,
            "reports_date": demo.reports_date,
            "basic_info_age": str(basic_info.get("age", "")),
            "basic_info_bill_date": str(basic_info.get("bill_date", "")),
            "lab_or_hospital_name": facility_name,
            "report_date": demo.reports_date,
        }

        tests_key = lab_fields.get("tests_array", "report_details")
        details = (
            data_block.get(tests_key)
            or data_block.get("report_details")
            or data_block.get("tests")
            or data_block.get("investigations")
            or []
        )
        t_name = lab_fields.get("test_name", "test_name")
        t_res = lab_fields.get("result", "result")
        t_unit = lab_fields.get("unit", "unit")
        t_range = lab_fields.get("range", "range")
        t_analytics = lab_fields.get("test_analytics", "test_analytics")
        t_page = lab_fields.get("page_no", "page_no")

        records: List[Dict[str, Any]] = []
        for test_idx, raw in enumerate(details):
            if not isinstance(raw, dict):
                continue
            normalized_test = {
                "test_name": raw.get(t_name, raw.get("test_name", "")),
                "result": raw.get(t_res, raw.get("result")),
                "unit": raw.get(t_unit, raw.get("unit", "")),
                "range": raw.get(t_range, raw.get("range", "")),
                "test_analytics": raw.get(t_analytics, raw.get("test_analytics", "")),
                "page_no": raw.get(t_page, raw.get("page_no", 0)),
            }
            std_test = self.standardiser.standardize_lab_test(normalized_test)
            if not std_test:
                continue
            std_test = self.validator.enrich_test(std_test)
            rec = CanonicalRecord.create_lab_test(
                record_id=f"{doc_id}_LAB_{resp_idx}_{test_idx}",
                base_meta=base_meta,
                demographics=demographics,
                std_test=std_test,
            )
            records.append(rec.model_dump())
        return records

    def _extract_discharge(
        self,
        data_block: Dict[str, Any],
        adapter: Dict[str, Any],
        base_meta: Dict[str, Any],
        doc_id: str,
        resp_idx: int,
    ) -> List[Dict[str, Any]]:
        """Extract discharge summary and prescribed medications."""
        patient_field_map = adapter.get("patient_fields", {})
        raw_name = resolve_field_value(
            data_block,
            patient_field_map.get("patient_name")
            or ["patientName", "patient_name", "name"],
        )
        raw_age = resolve_field_value(
            data_block, patient_field_map.get("age") or ["age", "patient_age"]
        )
        raw_gender = resolve_field_value(
            data_block, patient_field_map.get("gender") or ["gender", "sex"]
        )

        age_norm, age_years, age_text = self.standardiser.parse_age(raw_age)
        gender_norm = self.standardiser.normalize_gender(raw_gender)
        demo = {
            "patient_name": str(raw_name).strip(),
            "age": age_norm,
            "age_years": age_years,
            "age_text": age_text,
            "gender": gender_norm,
            "hospital_name": str(data_block.get("hospitalName", "")).strip(),
            "doctor_name": str(data_block.get("doctorName", "")).strip(),
        }

        med_inj = json.dumps(data_block.get("medicineInjectionsInvestigation", []))
        course = json.dumps(data_block.get("courseDuringHospitalisation", []))
        summary_details = {
            "admission_date": self.standardiser.parse_iso_date(
                data_block.get("admissionDate", "")
            ),
            "discharge_date": self.standardiser.parse_iso_date(
                data_block.get("dischargeDate", "")
            ),
            "diagnosis": str(data_block.get("diagnosis", "") or "").strip(),
            "brief_history": str(data_block.get("briefHistory", "") or "").strip(),
            "general_examinations": str(
                data_block.get("generalExaminations", "") or ""
            ).strip(),
            "recommendations": str(data_block.get("recommendations", "") or "").strip(),
            "hospital_address": str(
                data_block.get("hospitalAddress", "") or ""
            ).strip(),
            "ward": str(data_block.get("ward", "") or "").strip(),
            "post_discharge_advice": str(
                data_block.get("postDischargeAdvice", "") or ""
            ).strip(),
            "medicine_injections_investigation": med_inj,
            "other_med_inj_investigations": med_inj,
            "course_during_hospitalisation": course,
            "course_during_hospitalization": course,
        }

        records = [
            CanonicalRecord.create_discharge_summary(
                record_id=f"{doc_id}_DISCHARGE_{resp_idx}",
                base_meta=base_meta,
                discharge_demo=demo,
                summary_details=summary_details,
            ).model_dump()
        ]

        # Extract medications
        med_fields = adapter.get("medication_fields", {})
        meds_key = med_fields.get("meds_array", "dischargeMedications")
        medications = (
            data_block.get(meds_key)
            or data_block.get("dischargeMedications")
            or data_block.get("medications")
            or data_block.get("prescriptions")
            or []
        )
        m_name = med_fields.get("medicine", "medicine")
        m_dose = med_fields.get("dose", "dose")
        m_freq = med_fields.get("frequency", "frequency")
        m_type = med_fields.get("type", "type")

        for med_idx, raw in enumerate(medications):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get(m_name, raw.get("medicine", ""))).strip()
            if not name or name.lower() in ("n/a", "na", "none", "-"):
                continue

            std_med = self.standardiser.standardize_medication(
                {
                    "medicine": name,
                    "dose": raw.get(m_dose, raw.get("dose", "")),
                    "frequency": raw.get(m_freq, raw.get("frequency", "")),
                    "type": raw.get(m_type, raw.get("type", "")),
                }
            )
            records.append(
                CanonicalRecord.create_medication(
                    record_id=f"{doc_id}_MED_{resp_idx}_{med_idx}",
                    base_meta=base_meta,
                    discharge_demo=demo,
                    std_med=std_med,
                ).model_dump()
            )
        return records

    def process_document(self, doc: IngestedDocument) -> List[Dict[str, Any]]:
        """Transform an ingested document into canonical database records."""
        now_ts = datetime.now(timezone.utc).isoformat()
        sys_key = str(doc.source_system).strip().upper()
        adapter = (
            self.config.clinic_mappings.get(sys_key)
            or self.config.clinic_mappings.get(doc.source_system)
            or self.config.clinic_mappings.get("DEFAULT")
            or {}
        )
        doc_id = doc.document_id or f"DOC-{uuid.uuid4().hex[:12].upper()}"
        base_meta = {
            "document_id": doc_id,
            "file_gcs_path": doc.file_path,
            "trace_id": doc.trace_id,
            "correlation_id": doc.correlation_id,
            "source_system": doc.source_system,
            "claim_no": doc.claim_no,
            "nt_code": doc.nt_code,
            "consumer_client_id": doc.consumer_client_id,
            "destination_identifier": doc.destination_identifier,
            "ingested_at": doc.ingested_at,
            "processed_at": now_ts,
            "metadetails": json.dumps(
                doc.raw_payload.get("data", {}).get("metaDetails", [])
            ),
        }

        lab_fields = adapter.get("lab_fields", {})
        tests_key = lab_fields.get("tests_array", "report_details")
        records: List[Dict[str, Any]] = []

        for resp_idx, resp_item in enumerate(doc.response_details):
            classifier = resp_item.get("classifier", "").lower()
            data_block = resp_item.get("data", {})
            if not isinstance(data_block, dict):
                continue

            has_labs = any(
                k in data_block
                for k in (tests_key, "report_details", "tests", "investigations")
            )
            if classifier in ("lab_report", "lab", "laboratory", "pathology") or (
                not classifier and has_labs
            ):
                records.extend(
                    self._extract_labs(
                        doc, data_block, adapter, base_meta, doc_id, resp_idx
                    )
                )
            elif classifier == "discharge_summary":
                records.extend(
                    self._extract_discharge(
                        data_block, adapter, base_meta, doc_id, resp_idx
                    )
                )

        return records

    def _record_run(
        self,
        run_id: str,
        file_name: str,
        start_time: str,
        start_perf: float,
        status: str,
        loaded: int = 0,
        flagged: int = 0,
        dups: int = 0,
        failed: int = 0,
    ) -> Dict[str, Any]:
        """Save a streaming execution audit entry to the database."""
        duration_ms = round((time.perf_counter() - start_perf) * 1000, 2)
        end_time = datetime.now(timezone.utc).isoformat()
        stats = {
            "run_id": run_id,
            "start_time": start_time,
            "end_time": end_time,
            "status": status,
            "files_scanned": 1,
            "files_processed": 1 if status == "COMPLETED" else 0,
            "files_failed": failed,
            "records_loaded": loaded,
            "records_flagged": flagged,
            "duplicates": dups,
            "duplicates_suppressed": dups,
            "file_name": file_name,
            "duration_ms": duration_ms,
        }
        self.db.record_pipeline_run(stats)
        return stats

    def process_file(self, file_path: str | Path) -> Dict[str, Any]:
        """Stream a single JSON file through ingestion, standardisation, and audit logging."""
        file_path = Path(file_path)
        start_perf = time.perf_counter()
        start_time = datetime.now(timezone.utc).isoformat()
        file_name = file_path.name
        run_id = str(uuid.uuid4())

        doc = self.ingestion.ingest_file(file_path)

        if doc.status in (IngestionStatus.DUPLICATE, IngestionStatus.DUPLICATE_SUPPRESSED):
            self.db.insert_dead_letter(
                record_id=f"DUP-{doc.file_hash[:16]}",
                file_path=str(file_path),
                source_system=doc.source_system,
                error_type="DUPLICATE",
                error_message=doc.error_message or "Duplicate content suppressed",
                raw_payload=doc.raw_payload,
            )
            logger.info(f"Duplicate file detected: {file_name}")
            return self._record_run(
                run_id,
                file_name,
                start_time,
                start_perf,
                "DUPLICATE",
                dups=1,
            )

        if doc.status in (IngestionStatus.MALFORMED_JSON, IngestionStatus.SCHEMA_ERROR):
            self.db.insert_dead_letter(
                record_id=f"ERR-{uuid.uuid4().hex[:12]}",
                file_path=str(file_path),
                source_system=doc.source_system,
                error_type="ERROR",
                error_message=doc.error_message or "Ingestion failure",
                raw_payload=doc.raw_payload,
            )
            logger.warning(f"File failed ingestion: {file_name} ({doc.status.value})")
            return self._record_run(
                run_id, file_name, start_time, start_perf, "FAILED", failed=1
            )

        try:
            records = self.process_document(doc)
            loaded = self.db.insert_records(records)
            flagged = sum(
                1
                for r in records
                if r.get("test_analytics")
                in ("OUTLIER", "ABOVE_RANGE", "BELOW_RANGE", "INVALID")
            )
            stat = self._record_run(
                run_id,
                file_name,
                start_time,
                start_perf,
                "COMPLETED",
                loaded=loaded,
                flagged=flagged,
            )
            logger.info(
                f"Streamed {file_name} in {stat['duration_ms']}ms: {loaded} records, {flagged} flagged."
            )
            return stat
        except Exception as exc:
            logger.error(f"Error processing {file_name}: {exc}", exc_info=True)
            self.db.insert_dead_letter(
                record_id=f"ERR-{uuid.uuid4().hex[:12]}",
                file_path=str(file_path),
                source_system=doc.source_system,
                error_type="ERROR",
                error_message=str(exc),
                raw_payload=doc.raw_payload,
            )
            return self._record_run(
                run_id, file_name, start_time, start_perf, "FAILED", failed=1
            )

    def run(self, input_dir: str | Path) -> Dict[str, Any]:
        """Process all files in directory in streaming fashion and return summary."""
        files = self.ingestion.discover_files(input_dir)
        runs = [self.process_file(f) for f in files]
        return {
            "files_scanned": len(files),
            "files_processed": sum(r["files_processed"] for r in runs),
            "files_failed": sum(r["files_failed"] for r in runs),
            "records_loaded": sum(r["records_loaded"] for r in runs),
            "records_flagged": sum(r["records_flagged"] for r in runs),
            "duplicates": sum(r.get("duplicates", r.get("duplicates_suppressed", 0)) for r in runs),
            "duplicates_suppressed": sum(r.get("duplicates_suppressed", 0) for r in runs),
            "file_runs": runs,
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Veritas Claims Medical Data Standardisation Streaming Pipeline"
    )
    parser.add_argument(
        "--input",
        "-i",
        default="sample_data",
        help="Input directory containing JSON report files",
    )
    parser.add_argument(
        "--config", "-c", default="config", help="Path to configuration directory"
    )
    parser.add_argument(
        "--db", "-d", default="data/veritas.db", help="Path to SQLite database file"
    )
    parser.add_argument(
        "--checks", default=None, help="Comma-separated active deduplication checks"
    )
    parser.add_argument(
        "--watch",
        "-w",
        action="store_true",
        help="Run continuous streaming watcher on input directory",
    )
    args = parser.parse_args()

    active_checks = [c.strip() for c in args.checks.split(",")] if args.checks else None
    pipeline = Pipeline(
        config_dir=args.config, db_path=args.db, active_checks=active_checks
    )

    if args.watch:
        from src.watcher import StreamingEngine

        engine = StreamingEngine(pipeline, watch_dir=args.input)
        engine.start(process_existing=True)
        print(
            f"\n[STREAMING] Watcher active on '{args.input}'. Drop JSON files into the folder. Press Ctrl+C to stop.\n"
        )
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            engine.stop()
            print("\n[STREAMING] Watcher stopped.")
    else:
        summary = pipeline.run(args.input)
        print("\n" + "=" * 50)
        print("PER-FILE STREAMING INGESTION SUMMARY")
        print("=" * 50)
        for k, v in summary.items():
            print(f"  {k:<25}: {len(v) if k == 'file_runs' else v}")
        print("=" * 50 + "\n")


# Backward compatibility alias
MedicalDataPipeline = Pipeline

if __name__ == "__main__":
    main()
