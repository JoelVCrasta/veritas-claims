from __future__ import annotations

import argparse
import json
import logging
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


class MedicalDataPipeline:
    """Execution pipeline for medical claims data standardisation."""

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
        self.standardiser = StandardisationEngine(self.config)
        self.validator = ValidationEngine(self.config)

    def process_document(self, doc: IngestedDocument) -> List[Dict[str, Any]]:
        """Transform an ingested document into database records."""
        now_ts = datetime.now(timezone.utc).isoformat()
        records: List[Dict[str, Any]] = []

        # Resolve clinic adapter profile for field mapping (case-insensitive)
        sys_key = str(doc.source_system).strip().upper()
        adapter = (
            self.config.clinic_mappings.get(sys_key)
            or self.config.clinic_mappings.get(doc.source_system)
            or self.config.clinic_mappings.get("DEFAULT")
            or {}
        )
        patient_field_map = adapter.get("patient_fields", {})

        # Common envelope metadata for all records derived from this document
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

        # Track demographics
        doc_demographics: Dict[str, Any] = {}

        lab_fields = adapter.get("lab_fields", {})
        med_fields = adapter.get("medication_fields", {})

        for resp_idx, resp_item in enumerate(doc.response_details):
            classifier = resp_item.get("classifier", "").lower()
            data_block = resp_item.get("data", {})
            if not isinstance(data_block, dict):
                continue

            tests_array_key = lab_fields.get("tests_array", "report_details")
            has_lab_tests = any(k in data_block for k in (tests_array_key, "report_details", "tests", "investigations"))

            # Lab Report Classifier
            if classifier in ("lab_report", "lab", "laboratory", "pathology") or (not classifier and has_lab_tests):
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

                doc_demographics = {
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

                report_details = (
                    data_block.get(tests_array_key)
                    or data_block.get("report_details")
                    or data_block.get("tests")
                    or data_block.get("investigations")
                    or []
                )
                t_name_key = lab_fields.get("test_name", "test_name")
                t_res_key = lab_fields.get("result", "result")
                t_unit_key = lab_fields.get("unit", "unit")
                t_range_key = lab_fields.get("range", "range")
                t_analytics_key = lab_fields.get("test_analytics", "test_analytics")

                for test_idx, raw_test in enumerate(report_details):
                    if not isinstance(raw_test, dict):
                        continue

                    normalized_raw_test = {
                        "test_name": raw_test.get(t_name_key, raw_test.get("test_name", "")),
                        "result": raw_test.get(t_res_key, raw_test.get("result")),
                        "unit": raw_test.get(t_unit_key, raw_test.get("unit", "")),
                        "range": raw_test.get(t_range_key, raw_test.get("range", "")),
                        "test_analytics": raw_test.get(t_analytics_key, raw_test.get("test_analytics", "")),
                        "page_no": raw_test.get(lab_fields.get("page_no", "page_no"), raw_test.get("page_no", 0)),
                    }

                    # Standardize lab test
                    std_test = self.standardiser.standardize_lab_test(normalized_raw_test)
                    if not std_test:
                        continue

                    # Validate against biological ranges
                    std_test = self.validator.enrich_test(std_test)

                    record_id = f"{doc_id}_LAB_{resp_idx}_{test_idx}"
                    rec = CanonicalRecord.create_lab_test(
                        record_id=record_id,
                        base_meta=base_meta,
                        demographics=doc_demographics,
                        std_test=std_test,
                    )
                    records.append(rec.model_dump())

            # Discharge Summary Classifier
            elif classifier == "discharge_summary":

                raw_patient_name = resolve_field_value(
                    data_block,
                    patient_field_map.get("patient_name") or ["patientName", "patient_name", "name"],
                )
                raw_age = resolve_field_value(
                    data_block,
                    patient_field_map.get("age") or ["age", "patient_age"],
                )
                raw_gender = resolve_field_value(
                    data_block,
                    patient_field_map.get("gender") or ["gender", "sex"],
                )

                age_norm, age_years, age_text = self.standardiser.parse_age(raw_age)
                gender_norm = self.standardiser.normalize_gender(raw_gender)

                admission_date = self.standardiser.parse_iso_date(
                    data_block.get("admissionDate", "")
                )
                discharge_date = self.standardiser.parse_iso_date(
                    data_block.get("dischargeDate", "")
                )

                discharge_demo = {
                    "patient_name": str(raw_patient_name).strip(),
                    "age": age_norm,
                    "age_years": age_years,
                    "age_text": age_text,
                    "gender": gender_norm,
                    "hospital_name": str(data_block.get("hospitalName", "")).strip(),
                    "doctor_name": str(data_block.get("doctorName", "")).strip(),
                }

                # Summary root record
                summary_id = f"{doc_id}_DISCHARGE_{resp_idx}"
                summary_details = {
                    "admission_date": admission_date,
                    "discharge_date": discharge_date,
                    "diagnosis": str(data_block.get("diagnosis", "") or "").strip(),
                    "brief_history": str(
                        data_block.get("briefHistory", "") or ""
                    ).strip(),
                    "general_examinations": str(
                        data_block.get("generalExaminations", "") or ""
                    ).strip(),
                    "recommendations": str(
                        data_block.get("recommendations", "") or ""
                    ).strip(),
                    "hospital_address": str(
                        data_block.get("hospitalAddress", "") or ""
                    ).strip(),
                    "ward": str(data_block.get("ward", "") or "").strip(),
                    "post_discharge_advice": str(
                        data_block.get("postDischargeAdvice", "") or ""
                    ).strip(),
                    "medicine_injections_investigation": json.dumps(
                        data_block.get("medicineInjectionsInvestigation", [])
                    ),
                    "other_med_inj_investigations": json.dumps(
                        data_block.get("medicineInjectionsInvestigation", [])
                    ),
                    "course_during_hospitalisation": json.dumps(
                        data_block.get("courseDuringHospitalisation", [])
                    ),
                    "course_during_hospitalization": json.dumps(
                        data_block.get("courseDuringHospitalisation", [])
                    ),
                }
                rec = CanonicalRecord.create_discharge_summary(
                    record_id=summary_id,
                    base_meta=base_meta,
                    discharge_demo=discharge_demo,
                    summary_details=summary_details,
                )
                records.append(rec.model_dump())

                # Discharge medications
                meds_array_key = med_fields.get("meds_array", "dischargeMedications")
                medications = (
                    data_block.get(meds_array_key)
                    or data_block.get("dischargeMedications")
                    or data_block.get("medications")
                    or data_block.get("prescriptions")
                    or []
                )
                m_name_key = med_fields.get("medicine", "medicine")
                m_dose_key = med_fields.get("dose", "dose")
                m_freq_key = med_fields.get("frequency", "frequency")
                m_type_key = med_fields.get("type", "type")

                for med_idx, raw_med in enumerate(medications):
                    if not isinstance(raw_med, dict):
                        continue
                    med_name = str(raw_med.get(m_name_key, raw_med.get("medicine", ""))).strip()
                    if not med_name or med_name.lower() in ("n/a", "na", "none", "-"):
                        continue

                    normalized_med = {
                        "medicine": med_name,
                        "dose": raw_med.get(m_dose_key, raw_med.get("dose", "")),
                        "frequency": raw_med.get(m_freq_key, raw_med.get("frequency", "")),
                        "type": raw_med.get(m_type_key, raw_med.get("type", "")),
                    }
                    std_med = self.standardiser.standardize_medication(normalized_med)
                    med_id = f"{doc_id}_MED_{resp_idx}_{med_idx}"
                    med_rec = CanonicalRecord.create_medication(
                        record_id=med_id,
                        base_meta=base_meta,
                        discharge_demo=discharge_demo,
                        std_med=std_med,
                    )
                    records.append(med_rec.model_dump())

        return records

    def run(self, input_dir: str | Path) -> Dict[str, Any]:
        """Execute the pipeline across all files in the input directory."""
        run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        start_time = datetime.now(timezone.utc).isoformat()
        logger.info(f"Starting pipeline execution {run_id} on directory: {input_dir}")

        files = self.ingestion.discover_files(input_dir)
        total_scanned = len(files)
        files_processed = 0
        files_failed = 0
        duplicates_suppressed = 0
        total_records_loaded = 0
        total_flagged = 0

        # Reset ingestion cache for batch execution
        self.ingestion.reset()

        for file_path in files:
            doc = self.ingestion.ingest_file(file_path)

            if doc.status == IngestionStatus.DUPLICATE_SUPPRESSED:
                duplicates_suppressed += 1
                self.db.insert_dead_letter(
                    record_id=f"DUP-{doc.file_hash[:16]}",
                    file_path=str(file_path),
                    source_system=doc.source_system,
                    error_type="DUPLICATE",
                    error_message=doc.error_message or "Duplicate content suppressed",
                    raw_payload=doc.raw_payload,
                )
                logger.info(f"Suppressed duplicate file: {doc.file_name}")
                continue

            if doc.status in (
                IngestionStatus.MALFORMED_JSON,
                IngestionStatus.SCHEMA_ERROR,
            ):
                files_failed += 1
                self.db.insert_dead_letter(
                    record_id=f"ERR-{uuid.uuid4().hex[:12]}",
                    file_path=str(file_path),
                    source_system=doc.source_system,
                    error_type="ERROR",
                    error_message=doc.error_message or "Ingestion failure",
                    raw_payload=doc.raw_payload,
                )
                logger.warning(
                    f"File failed ingestion: {doc.file_name} ({doc.status.value})"
                )
                continue

            # Process successfully ingested file
            try:
                records = self.process_document(doc)
                loaded_count = self.db.insert_records(records)
                total_records_loaded += loaded_count
                files_processed += 1

                for r in records:
                    if r.get("test_analytics") in (
                        "OUTLIER",
                        "ABOVE_RANGE",
                        "BELOW_RANGE",
                        "INVALID",
                    ):
                        total_flagged += 1

                logger.info(
                    f"Processed {doc.file_name}: {loaded_count} canonical records generated."
                )
            except Exception as exc:
                files_failed += 1
                logger.error(f"Error processing {doc.file_name}: {exc}", exc_info=True)
                self.db.insert_dead_letter(
                    record_id=f"ERR-{uuid.uuid4().hex[:12]}",
                    file_path=str(file_path),
                    source_system=doc.source_system,
                    error_type="ERROR",
                    error_message=str(exc),
                    raw_payload=doc.raw_payload,
                )

        end_time = datetime.now(timezone.utc).isoformat()
        status = "COMPLETED" if files_failed == 0 else "COMPLETED_WITH_ERRORS"

        run_stats = {
            "run_id": run_id,
            "start_time": start_time,
            "end_time": end_time,
            "status": status,
            "files_scanned": total_scanned,
            "files_processed": files_processed,
            "files_failed": files_failed,
            "records_loaded": total_records_loaded,
            "records_flagged": total_flagged,
            "duplicates_suppressed": duplicates_suppressed,
        }
        self.db.record_pipeline_run(run_stats)

        logger.info(
            f"Pipeline run {run_id} finished: {files_processed}/{total_scanned} files processed, "
            f"{duplicates_suppressed} duplicates suppressed, {total_records_loaded} records stored, "
            f"{total_flagged} records flagged."
        )
        return run_stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Veritas Claims Medical Data Standardisation Pipeline"
    )
    parser.add_argument(
        "--input",
        "-i",
        default="sample_data",
        help="Path to input directory containing JSON files",
    )
    parser.add_argument(
        "--config", "-c", default="config", help="Path to configuration directory"
    )
    parser.add_argument(
        "--db", "-d", default="data/veritas.db", help="Path to SQLite database file"
    )
    parser.add_argument(
        "--checks",
        default=None,
        help="Comma-separated active deduplication checks (e.g., document_id,content_hash,claim_no)",
    )
    args = parser.parse_args()

    active_checks = [c.strip() for c in args.checks.split(",")] if args.checks else None
    pipeline = MedicalDataPipeline(
        config_dir=args.config, db_path=args.db, active_checks=active_checks
    )
    stats = pipeline.run(args.input)

    print("\n" + "=" * 50)
    print("PIPELINE RUN EXECUTION SUMMARY")
    print("=" * 50)
    for k, v in stats.items():
        print(f"  {k:<25}: {v}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
