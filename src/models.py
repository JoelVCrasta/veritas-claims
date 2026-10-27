from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict


def resolve_field_value(
    data: Dict[str, Any], candidate_keys: Union[str, List[str], None], default: Any = ""
) -> Any:
    """Extract first non-empty value from data matching candidate keys."""
    if not candidate_keys or not isinstance(data, dict):
        return default
    keys = [candidate_keys] if isinstance(candidate_keys, str) else candidate_keys
    for k in keys:
        if k in data and data[k] not in (None, ""):
            return data[k]
    return default


class CanonicalRecord(BaseModel):
    """Pydantic data model representing a standardized canonical healthcare record."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Identifiers & Envelope
    id: str
    document_id: str
    record_type: str
    file_gcs_path: str = ""
    trace_id: str = ""
    correlation_id: str = ""
    source_system: str = "UNKNOWN"
    claim_no: str = ""
    nt_code: str = ""
    consumer_client_id: str = ""
    destination_identifier: str = ""
    ingested_at: str = ""
    processed_at: str = ""
    metadetails: str = ""

    # Demographics
    patient_name: str = ""
    age: str = ""
    age_years: str = ""
    age_text: str = ""
    gender: str = ""
    uhid: str = ""
    hospital_name: str = ""
    doctor_name: str = ""
    bill_date: str = ""
    reports_date: str = ""

    # Lab specifics
    test_name_canonical: str = ""
    test_name_original: str = ""
    result_value: Optional[float] = None
    result_text: str = ""
    unit_canonical: str = ""
    unit_original: str = ""
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    range_text: str = ""
    test_analytics: str = ""
    normalization_method: str = ""
    normalization_confidence: float = 0.0

    # Discharge specifics
    admission_date: str = ""
    discharge_date: str = ""
    diagnosis: str = ""
    brief_history: str = ""
    general_examinations: str = ""
    recommendations: str = ""
    hospital_address: str = ""
    ward: str = ""
    post_discharge_advice: str = ""
    medicine_injections_investigation: str = ""
    other_med_inj_investigations: str = ""
    course_during_hospitalisation: str = ""
    course_during_hospitalization: str = ""

    # Medication specifics
    medicine: str = ""
    dose: str = ""
    frequency: str = ""
    medicine_type: str = ""

    @classmethod
    def create_lab_test(
        cls,
        record_id: str,
        base_meta: Dict[str, Any],
        demographics: Dict[str, Any],
        std_test: Any,
    ) -> CanonicalRecord:
        """Construct a validated CanonicalRecord for a standardized lab test."""
        payload = {
            **base_meta,
            **demographics,
            "id": record_id,
            "record_type": "lab_test",
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
            # Redundant CSV schema alias compatibility
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
        return cls(**payload)

    @classmethod
    def create_discharge_summary(
        cls,
        record_id: str,
        base_meta: Dict[str, Any],
        discharge_demo: Dict[str, Any],
        summary_details: Dict[str, Any],
    ) -> CanonicalRecord:
        """Construct a validated CanonicalRecord for a discharge summary root."""
        payload = {
            **base_meta,
            **discharge_demo,
            "id": record_id,
            "record_type": "discharge_summary",
            **summary_details,
        }
        return cls(**payload)

    @classmethod
    def create_medication(
        cls,
        record_id: str,
        base_meta: Dict[str, Any],
        discharge_demo: Dict[str, Any],
        std_med: Any,
    ) -> CanonicalRecord:
        """Construct a validated CanonicalRecord for a prescribed medication."""
        payload = {
            **base_meta,
            **discharge_demo,
            "id": record_id,
            "record_type": "medication",
            "medicine": std_med.medicine,
            "dose": std_med.dose,
            "frequency": std_med.frequency,
            "medicine_type": std_med.medicine_type,
            # Redundant CSV schema alias compatibility
            "medication_name": std_med.medicine,
            "medication_medicine": std_med.medicine_original,
            "medication_dose": std_med.dose,
            "medication_frequency": std_med.frequency,
            "discharge_medications_medicine": std_med.medicine_original,
            "discharge_medications_dose": std_med.dose,
            "discharge_medications_frequency": std_med.frequency,
        }
        return cls(**payload)
