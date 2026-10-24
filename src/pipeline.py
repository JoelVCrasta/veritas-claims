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

        # Resolve clinic adapter profile for field mapping
        adapter = (
            self.config.clinic_mappings.get(doc.source_system)
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

        for resp_idx, resp_item in enumerate(doc.response_details):
            classifier = resp_item.get("classifier", "")
            data_block = resp_item.get("data", {})
            if not isinstance(data_block, dict):
                continue

            # Lab Report Classifier
            if classifier == "lab_report":
                basic_info = data_block.get("basic_info", {})
                demo = self.standardiser.standardize_demographics(
                    basic_info, field_map=patient_field_map
                )

                doc_demographics = {
                    "patient_name": demo.patient_name,
                    "age": demo.age,
                    "age_years": demo.age_years,
                    "age_text": demo.age_text,
                    "gender": demo.gender,
                    "uhid": demo.uhid,
                    "hospital_name": demo.hospital_name,
                    "doctor_name": demo.doctor_name,
                    "bill_date": demo.bill_date,
                    "reports_date": demo.reports_date,
                    "basic_info_age": str(basic_info.get("age", "")),
                    "basic_info_bill_date": str(basic_info.get("bill_date", "")),
                    "lab_or_hospital_name": demo.hospital_name,
                    "report_date": demo.reports_date,
                }

                report_details = data_block.get("report_details", [])
                for test_idx, raw_test in enumerate(report_details):
                    if not isinstance(raw_test, dict):
                        continue

                    # Standardize lab test
                    std_test = self.standardiser.standardize_lab_test(raw_test)
                    if not std_test:
                        continue

                    # Validate against biological ranges
                    std_test = self.validator.enrich_test(std_test)

                    record_id = f"{doc_id}_LAB_{resp_idx}_{test_idx}"
                    record: Dict[str, Any] = {
                        "id": record_id,
                        "record_type": "lab_test",
                        **base_meta,
                        **doc_demographics,
                        "test_name_canonical": std_test.test_name_canonical,
                        "test_name_original": std_test.test_name_original,
                        "result_value": std_test.result_value,
                        "result_text": std_test.result_text,
                        "unit_canonical": std_test.unit_canonical,
                        "unit_original": std_test.unit_original,
                        "range_low": std_test.range_low,
                        "range_high": std_test.range_high,
                        "range_text": std_test.range_text,
                        "test_analytics": std_test.test_analytics,
                        "normalization_method": std_test.normalization_method,
                        "normalization_confidence": std_test.normalization_confidence,
                        "report_details_page_no": std_test.page_no,
                        "report_details_range": std_test.range_text,
                        "report_details_result": std_test.result_text,
                        "report_details_test_analytics": std_test.test_analytics,
                        "report_details_test_name": std_test.test_name_original,
                        "report_details_unit": std_test.unit_original,
                        "page_no": std_test.page_no,
                        "page_number": std_test.page_no,
                        "test_name": std_test.test_name_original,
                        "result": std_test.result_text,
                        "result_text_original": std_test.result_text,
                        "unit": std_test.unit_original,
                        "range": std_test.range_text,
                        "range_text_original": std_test.range_text,
                    }
                    records.append(record)

            # Discharge Summary Classifier
            elif classifier == "discharge_summary":

                def get_patient_val(field_name: str, fallback_keys: List[str]) -> Any:
                    keys = patient_field_map.get(field_name) or fallback_keys
                    for k in keys:
                        if k in data_block and data_block[k] not in (None, ""):
                            return data_block[k]
                    return ""

                raw_patient_name = get_patient_val(
                    "patient_name", ["patientName", "patient_name", "name"]
                )
                raw_age = get_patient_val("age", ["age", "patient_age"])
                raw_gender = get_patient_val("gender", ["gender", "sex"])

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
                summary_record: Dict[str, Any] = {
                    "id": summary_id,
                    "record_type": "discharge_summary",
                    **base_meta,
                    **discharge_demo,
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
                records.append(summary_record)

                # Discharge medications
                medications = data_block.get("dischargeMedications", [])
                for med_idx, raw_med in enumerate(medications):
                    if not isinstance(raw_med, dict):
                        continue
                    med_name = str(raw_med.get("medicine", "")).strip()
                    if not med_name or med_name.lower() in ("n/a", "na", "none", "-"):
                        continue

                    std_med = self.standardiser.standardize_medication(raw_med)
                    med_id = f"{doc_id}_MED_{resp_idx}_{med_idx}"

                    med_record: Dict[str, Any] = {
                        "id": med_id,
                        "record_type": "medication",
                        **base_meta,
                        **discharge_demo,
                        "medicine": std_med.medicine,
                        "dose": std_med.dose,
                        "frequency": std_med.frequency,
                        "medicine_type": std_med.medicine_type,
                        "medication_name": std_med.medicine,
                        "medication_medicine": std_med.medicine_original,
                        "medication_dose": std_med.dose,
                        "medication_frequency": std_med.frequency,
                        "discharge_medications_medicine": std_med.medicine_original,
                        "discharge_medications_dose": std_med.dose,
                        "discharge_medications_frequency": std_med.frequency,
                    }
                    records.append(med_record)

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
