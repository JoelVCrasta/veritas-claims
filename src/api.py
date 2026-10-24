from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import load_jsonc
from src.db_loader import DatabaseManager
from src.pipeline import MedicalDataPipeline

logger = logging.getLogger("veritas.api")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "data/veritas.db"
INPUT_DIR = "sample_data"
CONFIG_DIR = "config"


def get_db() -> DatabaseManager:
    return DatabaseManager(DB_PATH)


class PipelineRunResponse(BaseModel):
    status: str
    run_stats: Dict[str, Any]


@app.get("/api/stats")
def get_stats() -> Dict[str, Any]:
    """Retrieve aggregate KPI statistics for dashboard."""
    db = get_db()
    return db.get_summary_stats()


@app.get("/api/flagged")
def get_flagged(
    limit: int = Query(default=100, ge=1, le=500),
    flag: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    """Retrieve flagged anomalies."""
    db = get_db()
    records = db.get_flagged_records(limit=limit)
    if flag and flag.upper() != "ALL":
        records = [r for r in records if r.get("test_analytics") == flag.upper()]
    return records


@app.get("/api/clinics")
def get_clinics() -> List[Dict[str, Any]]:
    """Retrieve metrics grouped by healthcare facility."""
    db = get_db()
    return db.get_clinic_quality_stats()


@app.get("/api/search")
def search_records(
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """Search canonical records by document_id, patient_name, UHID, claim_no, or test/medicine name."""
    db = get_db()
    return db.search_records(query=q, limit=limit)


@app.get("/api/documents")
def get_documents(limit: int = Query(default=50, ge=1, le=200)) -> List[Dict[str, Any]]:
    """Retrieve aggregated reports grouped by document_id."""
    db = get_db()
    return db.get_documents(limit=limit)


@app.get("/api/document/{document_id}")
def get_document_bundle(document_id: str) -> Dict[str, Any]:
    """Retrieve complete report bundle including lab tests, medications, and raw JSON."""
    db = get_db()
    bundle = db.get_document_bundle(document_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Document report not found")
    return bundle


@app.get("/api/records")
def get_records(
    record_type: Optional[str] = Query(default=None),
    flag: Optional[str] = Query(default=None),
    q: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
) -> List[Dict[str, Any]]:
    """Retrieve records filtered by record_type, flag, or query."""
    db = get_db()
    return db.get_records(record_type=record_type, flag=flag, query=q, limit=limit)


@app.get("/api/runs")
def get_runs(limit: int = Query(default=10, ge=1, le=50)) -> List[Dict[str, Any]]:
    """Retrieve execution log history."""
    db = get_db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM pipeline_runs ORDER BY start_time DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


@app.get("/api/dead_letters")
def get_dead_letters(
    limit: int = Query(default=50, ge=1, le=100)
) -> List[Dict[str, Any]]:
    """Retrieve records from dead-letter queue."""
    db = get_db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM dead_letter_records ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


@app.post("/api/run_pipeline", response_model=PipelineRunResponse)
def run_pipeline() -> PipelineRunResponse:
    """Trigger an execution run of the ingestion, standardisation, and validation pipeline."""
    try:
        pipeline = MedicalDataPipeline(config_dir=CONFIG_DIR, db_path=DB_PATH)
        stats = pipeline.run(INPUT_DIR)
        return PipelineRunResponse(status="SUCCESS", run_stats=stats)
    except Exception as exc:
        logger.error(f"Pipeline execution error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# Configuration Management Endpoints


def get_clinic_mappings_path() -> Path:
    return Path(CONFIG_DIR) / "clinic_mappings.jsonc"


def get_dedup_config_path() -> Path:
    return Path(CONFIG_DIR) / "deduplication.jsonc"


def read_clinic_config() -> Dict[str, Any]:
    p = get_clinic_mappings_path()
    return load_jsonc(p) if p.exists() else {}


def save_clinic_config(data: Dict[str, Any]) -> None:
    p = get_clinic_mappings_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_dedup_config() -> Dict[str, Any]:
    p = get_dedup_config_path()
    return load_jsonc(p) if p.exists() else {}


def save_dedup_config(data: Dict[str, Any]) -> None:
    p = get_dedup_config_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class ClinicAdapterPayload(BaseModel):
    clinic_key: str
    config: Dict[str, Any]


class DedupSettingsPayload(BaseModel):
    checks: Dict[str, bool]


@app.get("/api/configs/clinics")
def get_clinic_configs() -> Dict[str, Any]:
    """Retrieve all configured clinic adapters and deduplication settings."""
    clinics = read_clinic_config()
    dedup = read_dedup_config()
    return {
        "deduplication": dedup,
        "clinics": clinics,
    }


@app.post("/api/configs/clinics")
def add_or_update_clinic_config(body: ClinicAdapterPayload) -> Dict[str, Any]:
    """Add a new clinic adapter profile or update an existing one."""
    key = body.clinic_key.strip().upper()
    if not key:
        raise HTTPException(status_code=400, detail="Clinic key cannot be empty")
    data = read_clinic_config()
    data[key] = body.config
    save_clinic_config(data)
    logger.info(f"Saved clinic configuration for: {key}")
    return {"status": "SUCCESS", "clinic_key": key, "config": body.config}


@app.delete("/api/configs/clinics/{clinic_key}")
def delete_clinic_config(clinic_key: str) -> Dict[str, Any]:
    """Remove a clinic adapter profile."""
    key = clinic_key.strip().upper()
    if key == "DEFAULT":
        raise HTTPException(status_code=400, detail="Cannot delete default adapter")
    data = read_clinic_config()
    if key not in data:
        raise HTTPException(
            status_code=404, detail=f"Clinic configuration '{key}' not found"
        )
    del data[key]
    save_clinic_config(data)
    logger.info(f"Deleted clinic configuration for: {key}")
    return {"status": "SUCCESS", "deleted_key": key}


@app.put("/api/configs/dedup")
def update_dedup_settings(body: DedupSettingsPayload) -> Dict[str, Any]:
    """Update active deduplication check toggles."""
    data = read_dedup_config()
    data["checks"] = body.checks
    save_dedup_config(data)
    logger.info(f"Updated active deduplication checks: {body.checks}")
    return {"status": "SUCCESS", "checks": body.checks}


# -------------------------------------------------------------------------
# Test Dictionary Configs
# -------------------------------------------------------------------------


def get_config_file_path(name: str) -> Path:
    return Path(CONFIG_DIR) / f"{name}.jsonc"


def read_config_file(name: str) -> Dict[str, Any]:
    p = get_config_file_path(name)
    return load_jsonc(p) if p.exists() else {}


def save_config_file(name: str, data: Dict[str, Any]) -> None:
    p = get_config_file_path(name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class TestConfigPayload(BaseModel):
    test_name: str
    aliases: List[str]
    canonical_unit: str = ""
    unit_conversions: Dict[str, float] = {}


@app.get("/api/configs/tests")
def get_test_configs() -> Dict[str, Any]:
    """Retrieve all canonical tests and alias mappings."""
    return read_config_file("test_dictionary")


@app.post("/api/configs/tests")
def add_or_update_test_config(body: TestConfigPayload) -> Dict[str, Any]:
    """Add or update a canonical test definition."""
    name = body.test_name.strip().upper()
    if not name:
        raise HTTPException(status_code=400, detail="Test name cannot be empty")
    data = read_config_file("test_dictionary")
    data[name] = {
        "aliases": body.aliases,
        "canonical_unit": body.canonical_unit,
        "unit_conversions": body.unit_conversions,
    }
    save_config_file("test_dictionary", data)
    return {"status": "SUCCESS", "test_name": name, "config": data[name]}


@app.delete("/api/configs/tests/{test_name}")
def delete_test_config(test_name: str) -> Dict[str, Any]:
    """Delete a canonical test definition."""
    name = test_name.strip().upper()
    data = read_config_file("test_dictionary")
    if name not in data:
        raise HTTPException(status_code=404, detail=f"Test '{name}' not found")
    del data[name]
    save_config_file("test_dictionary", data)
    return {"status": "SUCCESS", "deleted_test": name}


# Reference Ranges Configs


class RangeConfigPayload(BaseModel):
    test_name: str
    unit: str = ""
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    outlier_low: Optional[float] = None
    outlier_high: Optional[float] = None


@app.get("/api/configs/ranges")
def get_range_configs() -> Dict[str, Any]:
    """Retrieve reference ranges and outlier thresholds."""
    return read_config_file("reference_ranges")


@app.post("/api/configs/ranges")
def add_or_update_range_config(body: RangeConfigPayload) -> Dict[str, Any]:
    """Add or update a reference range definition."""
    name = body.test_name.strip().upper()
    if not name:
        raise HTTPException(status_code=400, detail="Test name cannot be empty")
    data = read_config_file("reference_ranges")
    data[name] = {
        "unit": body.unit,
        "range_low": body.range_low,
        "range_high": body.range_high,
        "outlier_low": body.outlier_low,
        "outlier_high": body.outlier_high,
    }
    save_config_file("reference_ranges", data)
    return {"status": "SUCCESS", "test_name": name, "config": data[name]}


@app.delete("/api/configs/ranges/{test_name}")
def delete_range_config(test_name: str) -> Dict[str, Any]:
    """Delete a reference range definition."""
    name = test_name.strip().upper()
    data = read_config_file("reference_ranges")
    if name not in data:
        raise HTTPException(status_code=404, detail=f"Range for '{name}' not found")
    del data[name]
    save_config_file("reference_ranges", data)
    return {"status": "SUCCESS", "deleted_range": name}


# Medicine Brand Mappings Configs


class MedicineConfigPayload(BaseModel):
    brand: str
    generic: str


@app.get("/api/configs/medicines")
def get_medicine_configs() -> Dict[str, Any]:
    """Retrieve brand-to-generic medicine mappings."""
    return read_config_file("medicine_mapping")


@app.post("/api/configs/medicines")
def add_or_update_medicine_config(body: MedicineConfigPayload) -> Dict[str, Any]:
    """Add or update a brand-to-generic medicine mapping."""
    brand = body.brand.strip().lower()
    generic = body.generic.strip()
    if not brand or not generic:
        raise HTTPException(
            status_code=400, detail="Brand and generic names cannot be empty"
        )
    data = read_config_file("medicine_mapping")
    data[brand] = generic
    save_config_file("medicine_mapping", data)
    return {"status": "SUCCESS", "brand": brand, "generic": generic}


@app.delete("/api/configs/medicines/{brand}")
def delete_medicine_config(brand: str) -> Dict[str, Any]:
    """Delete a brand-to-generic medicine mapping."""
    b = brand.strip().lower()
    data = read_config_file("medicine_mapping")
    if b not in data:
        raise HTTPException(status_code=404, detail=f"Medicine brand '{b}' not found")
    del data[b]
    save_config_file("medicine_mapping", data)
    return {"status": "SUCCESS", "deleted_brand": b}
