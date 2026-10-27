from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("veritas.onboarder")

DEFAULT_MODEL = "qwen/qwen3.8-27b"


SYSTEM_PROMPT = """You are an expert healthcare data integration AI specializing in electronic health record (EHR) schemas.
The input JSON is a specimen/template report from a clinic.
Your objective is purely SCHEMA INDUCTION & FIELD MAPPING to map the clinic's report hierarchy into our canonical database ingestion schema.
DO NOT extract or generate observation data rows or mock records. Only extract the structural field paths and keys.

Analyze the structure and return ONLY a valid JSON object matching this schema:
{
  "clinic_key": "IDENTIFIER_OF_THE_CLINIC (e.g. METROPOLIS_CARE, APOLLO_LABS, FORTIS in UPPER_SNAKE_CASE)",
  "adapter_config": {
    "system_name": "IDENTIFIER_OF_THE_CLINIC",
    "source_system_field": "dot-separated path to clinic/source system identifier (e.g. 'header.source_system' or 'data.source_system')",
    "facility_field": "dot-separated path to facility or hospital name if in header (e.g. 'header.facility')",
    "document_id_field": "dot-separated path to document/report id (e.g. 'header.doc_id' or 'data.documentId')",
    "correlation_id_field": "dot-separated path to request/correlation id if present, else null",
    "meta_details_field": "dot-separated path to header/metadata block if present, else null",
    "response_details_field": "dot-separated path to array of report sections/details (e.g. 'sections' or 'data.responseDetails')",
    "patient_fields": {
      "patient_name": ["candidate", "keys", "for", "patient_name", "inside demographics/patient block"],
      "age": ["candidate", "keys", "for", "age"],
      "gender": ["candidate", "keys", "for", "gender", "or", "sex"],
      "uhid": ["candidate", "keys", "for", "mrn", "or", "uhid"],
      "hospital_name": ["candidate", "keys", "for", "facility", "or", "hospital_name"],
      "doctor_name": ["candidate", "keys", "for", "doctor_name", "or", "consultant"]
    },
    "lab_fields": {
      "tests_array": "key for investigations/tests array within a section (e.g. 'investigations' or 'report_details', or null if not a lab report)",
      "test_name": "key for test parameter name inside each test item (e.g. 'parameter' or 'test_name', or null)",
      "result": "key for observed result value inside each test item (e.g. 'observed_value' or 'result', or null)",
      "unit": "key for unit of measurement inside each test item (e.g. 'uom' or 'unit', or null)",
      "range": "key for reference interval/range inside each test item (e.g. 'reference_interval' or 'range', or null)",
      "test_analytics": "key for flag or status if present, else null"
    },
    "medication_fields": {
      "meds_array": "key for medications array inside a section if present (e.g. 'dischargeMedications' or 'medications'), else null",
      "medicine": "key for medicine/drug name",
      "dose": "key for dosage",
      "frequency": "key for frequency",
      "type": "key for medicine form/type"
    }
  },
  "field_mappings": [
    {
      "category": "Envelope",
      "canonical_field": "source_system",
      "clinic_path": "path in template (e.g. 'header.source_system')",
      "description": "Source clinic or laboratory system identifier"
    },
    {
      "category": "Envelope",
      "canonical_field": "hospital_name",
      "clinic_path": "path in template (e.g. 'header.facility')",
      "description": "Clinical facility or hospital name"
    },
    {
      "category": "Envelope",
      "canonical_field": "document_id",
      "clinic_path": "path in template (e.g. 'header.doc_id')",
      "description": "Unique document or report identifier"
    },
    {
      "category": "Envelope",
      "canonical_field": "response_details",
      "clinic_path": "path in template (e.g. 'sections')",
      "description": "Array of report section items"
    },
    {
      "category": "Patient Demographics",
      "canonical_field": "patient_name",
      "clinic_path": "path/key in template (e.g. 'sections.data.demographics.patient_name')",
      "description": "Patient full name"
    },
    {
      "category": "Patient Demographics",
      "canonical_field": "age",
      "clinic_path": "path/key in template (e.g. 'sections.data.demographics.patient_age')",
      "description": "Patient age"
    },
    {
      "category": "Patient Demographics",
      "canonical_field": "gender",
      "clinic_path": "path/key in template (e.g. 'sections.data.demographics.sex')",
      "description": "Patient biological sex / gender"
    },
    {
      "category": "Patient Demographics",
      "canonical_field": "uhid",
      "clinic_path": "path/key in template (e.g. 'sections.data.demographics.mrn')",
      "description": "Patient MRN / UHID number"
    },
    {
      "category": "Lab Observations",
      "canonical_field": "tests_array",
      "clinic_path": "key in section (e.g. 'investigations')",
      "description": "Array of laboratory test results"
    },
    {
      "category": "Lab Observations",
      "canonical_field": "test_name",
      "clinic_path": "key in item (e.g. 'parameter')",
      "description": "Analyte or laboratory parameter name"
    },
    {
      "category": "Lab Observations",
      "canonical_field": "result_value",
      "clinic_path": "key in item (e.g. 'observed_value')",
      "description": "Observed test result value"
    },
    {
      "category": "Lab Observations",
      "canonical_field": "unit",
      "clinic_path": "key in item (e.g. 'uom')",
      "description": "Unit of measurement"
    },
    {
      "category": "Lab Observations",
      "canonical_field": "reference_range",
      "clinic_path": "key in item (e.g. 'reference_interval')",
      "description": "Normal biological reference interval"
    }
  ]
}
"""


def _prune_sample_for_prompt(obj: Any, max_items: int = 4) -> Any:
    """Trim large arrays in json entries."""
    if isinstance(obj, dict):
        return {k: _prune_sample_for_prompt(v, max_items) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_prune_sample_for_prompt(item, max_items) for item in obj[:max_items]]
    return obj


def _build_field_mappings_from_adapter(adapter_config: Dict[str, Any]) -> List[Dict[str, str]]:
    """Create structured field mappings from an adapter config if missing."""
    mappings: List[Dict[str, str]] = []

    # Envelope
    envelope_fields = [
        ("source_system_field", "source_system", "Source clinic or laboratory system identifier"),
        ("facility_field", "hospital_name", "Clinical facility or laboratory name"),
        ("document_id_field", "document_id", "Unique report or document identifier"),
        ("correlation_id_field", "correlation_id", "Request or correlation tracking identifier"),
        ("meta_details_field", "meta_details", "Header or facility metadata container"),
        ("response_details_field", "response_details", "Array containing report clinical sections"),
    ]
    for key, canon, desc in envelope_fields:
        val = adapter_config.get(key)
        if val:
            mappings.append({
                "category": "Envelope",
                "canonical_field": canon,
                "clinic_path": str(val),
                "description": desc,
            })

    # Patient Demographics
    p_fields = adapter_config.get("patient_fields", {})
    if isinstance(p_fields, dict):
        for canon, desc in [
            ("patient_name", "Patient full name"),
            ("age", "Patient age in years or compound format"),
            ("gender", "Patient biological sex / gender"),
            ("uhid", "Unique hospital identifier or medical record number (MRN)"),
            ("hospital_name", "Hospital or clinic facility name"),
            ("doctor_name", "Attending physician or consultant name"),
        ]:
            val = p_fields.get(canon)
            if val:
                path_str = ", ".join(val) if isinstance(val, list) else str(val)
                mappings.append({
                    "category": "Patient Demographics",
                    "canonical_field": canon,
                    "clinic_path": path_str,
                    "description": desc,
                })

    # Lab Fields
    lab = adapter_config.get("lab_fields", {})
    if isinstance(lab, dict):
        for canon, key, desc in [
            ("tests_array", "tests_array", "Key holding laboratory investigations array"),
            ("test_name", "test_name", "Laboratory parameter or test name"),
            ("result_value", "result", "Observed laboratory numerical/textual result"),
            ("unit", "unit", "Unit of measurement (e.g. g/dL, mmol/L)"),
            ("reference_range", "range", "Normal biological reference interval"),
            ("test_analytics", "test_analytics", "Flag or indicator for abnormal results"),
        ]:
            val = lab.get(key)
            if val:
                mappings.append({
                    "category": "Lab Observations",
                    "canonical_field": canon,
                    "clinic_path": str(val),
                    "description": desc,
                })

    # Medication Fields
    med = adapter_config.get("medication_fields", {})
    if isinstance(med, dict) and med.get("meds_array"):
        for canon, key, desc in [
            ("medications_array", "meds_array", "Key holding prescription or medication list"),
            ("medicine_name", "medicine", "Reported brand or generic drug name"),
            ("dosage", "dose", "Dosage strength (e.g. 500mg)"),
            ("frequency", "frequency", "Administration frequency (e.g. 1-0-1)"),
            ("medicine_type", "type", "Medication form (e.g. Tablet, Syrup)"),
        ]:
            val = med.get(key)
            if val:
                mappings.append({
                    "category": "Medications",
                    "canonical_field": canon,
                    "clinic_path": str(val),
                    "description": desc,
                })

    return mappings


class SchemaInferenceEngine:
    """Schema Mapper that creates canonical schema adapters from clinic template JSON."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        **kwargs: Any,
    ) -> None:
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is not configured."
            )
        self.model = model

    def infer_and_preview(
        self, payload: Dict[str, Any], suggested_clinic_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Call LLM to map canonical schema field from clinic template JSON."""
        from groq import Groq

        client = Groq(api_key=self.api_key)
        sample_payload = _prune_sample_for_prompt(payload, max_items=4)
        prompt = (
            f"Suggested Clinic Name: {suggested_clinic_key or 'Auto-detect'}\n\n"
            f"Clinic Template JSON:\n{json.dumps(sample_payload, indent=2)}"
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        result = json.loads(response.choices[0].message.content)
        clinic_key = (
            suggested_clinic_key
            or result.get("clinic_key")
            or "NEW_CLINIC"
        ).strip().upper()
        result["clinic_key"] = clinic_key

        adapter_config = result.get("adapter_config") or {}
        adapter_config["system_name"] = clinic_key

        # Standardize patient_fields to lists of string keys
        patient_fields = adapter_config.get("patient_fields", {})
        if isinstance(patient_fields, dict):
            for k, v in patient_fields.items():
                if isinstance(v, str):
                    patient_fields[k] = [v]
            adapter_config["patient_fields"] = patient_fields
        result["adapter_config"] = adapter_config

        field_mappings = result.get("field_mappings")
        if not field_mappings or not isinstance(field_mappings, list):
            field_mappings = _build_field_mappings_from_adapter(adapter_config)
        result["field_mappings"] = field_mappings

        return {
            "clinic_key": clinic_key,
            "adapter_config": adapter_config,
            "field_mappings": field_mappings,
        }

    def infer_envelope(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience helper to extract envelope paths."""
        mapping = self.infer_and_preview(payload)
        return mapping.get("adapter_config", {})
