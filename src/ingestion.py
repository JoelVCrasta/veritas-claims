from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import jmespath

logger = logging.getLogger("veritas.ingestion")


class IngestionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    DUPLICATE_SUPPRESSED = "DUPLICATE_SUPPRESSED"
    MALFORMED_JSON = "MALFORMED_JSON"
    SCHEMA_ERROR = "SCHEMA_ERROR"


@dataclass
class IngestedDocument:
    file_path: str
    file_name: str
    status: IngestionStatus
    ingested_at: str
    trace_id: str = ""
    document_id: str = ""
    correlation_id: str = ""
    source_system: str = "UNKNOWN"
    claim_no: str = ""
    nt_code: str = ""
    consumer_client_id: str = ""
    destination_identifier: str = ""
    file_hash: str = ""
    payload_hash: str = ""
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    response_details: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None


def extract_nested_field(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Extract a value from nested data structures."""
    if not path or not isinstance(data, (dict, list)):
        return default
    try:
        val = jmespath.search(path, data)
        if val is not None:
            return val
    except Exception:
        pass

    curr = data
    for part in path.split("."):
        if isinstance(curr, dict):
            curr = curr.get(part)
        else:
            return default
    return curr if curr is not None else default


def _flatten_meta_details(meta_source: Any) -> Dict[str, str]:
    """Normalize list of dicts or dict metadata into a flat key-value dict."""
    res: Dict[str, str] = {}
    if isinstance(meta_source, list):
        for item in meta_source:
            if isinstance(item, dict) and "key" in item and "value" in item:
                res[item["key"]] = str(item["value"])
    elif isinstance(meta_source, dict):
        for k, v in meta_source.items():
            res[k] = str(v)
    return res


class IngestionEngine:
    """Manages file discovery, parsing, and deduplication of incoming JSON reports."""

    def __init__(
        self,
        active_checks: Optional[List[str]] = None,
        clinic_mappings: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Deduplication engine with active checks list and configurable clinic adapters.

        active_checks: List of enabled checks, e.g. ["document_id", "content_hash", "claim_no"].
        clinic_mappings: Dictionary of clinic adapter profiles.
        """
        if active_checks is not None:
            self.active_checks = list(active_checks)
        else:
            self.active_checks = ["document_id", "content_hash", "claim_no"]

        self.clinic_mappings = clinic_mappings or {}
        self.seen_payload_hashes: Set[str] = set()
        self.seen_document_ids: Set[str] = set()
        self.seen_claim_hashes: Set[str] = set()

    def reset(self) -> None:
        """Reset seen sets for a clean batch execution."""
        self.seen_payload_hashes.clear()
        self.seen_document_ids.clear()
        self.seen_claim_hashes.clear()

    def load_existing_seen(
        self,
        document_ids: Optional[Set[str]] = None,
        payload_hashes: Optional[Set[str]] = None,
    ) -> None:
        """Preload already ingested document IDs and hashes from persistent database."""
        if document_ids:
            self.seen_document_ids.update(document_ids)
        if payload_hashes:
            self.seen_payload_hashes.update(payload_hashes)

    def register_seen(
        self,
        payload_hash: str,
        document_id: str,
        claim_no: str = "",
        source_system: str = "",
    ) -> None:
        """Register a successfully processed document for future duplicate checking."""
        if payload_hash:
            self.seen_payload_hashes.add(payload_hash)
        if document_id:
            self.seen_document_ids.add(document_id)
        if claim_no and source_system and payload_hash:
            self.seen_claim_hashes.add(f"{source_system}:{claim_no}:{payload_hash}")

    def check_duplicate(
        self,
        payload_hash: str,
        document_id: str,
        claim_no: str = "",
        source_system: str = "",
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check for duplicates against the active checks list:
          - 'document_id': envelope documentId check
          - 'claim_no': claim submission context check
          - 'content_hash': underlying clinical content hash check
        """
        if "document_id" in self.active_checks:
            if document_id and document_id in self.seen_document_ids:
                return (
                    True,
                    "DUPLICATE",
                    f"Duplicate document_id '{document_id}' already ingested.",
                )

        if "claim_no" in self.active_checks:
            if claim_no and source_system and payload_hash:
                claim_key = f"{source_system}:{claim_no}:{payload_hash}"
                if claim_key in self.seen_claim_hashes:
                    return (
                        True,
                        "DUPLICATE",
                        f"Duplicate claim submission for claim '{claim_no}' at facility '{source_system}'.",
                    )

        if "content_hash" in self.active_checks:
            if payload_hash and payload_hash in self.seen_payload_hashes:
                return (
                    True,
                    "DUPLICATE",
                    f"Duplicate report content previously ingested and suppressed (hash={payload_hash[:12]}...).",
                )

        return (False, None, None)

    @staticmethod
    def compute_content_hash(data: Any) -> str:
        """Compute hash of sorted, compact JSON representation."""
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def discover_files(self, input_dir: str | Path) -> List[Path]:
        """Scan directory for JSON input files."""
        directory = Path(input_dir)
        if not directory.exists() or not directory.is_dir():
            logger.warning(f"Input directory does not exist: {directory}")
            return []
        files = sorted(
            [
                f
                for f in directory.iterdir()
                if f.is_file() and f.suffix.lower() == ".json"
            ]
        )
        logger.info(f"Discovered {len(files)} JSON file(s) in {directory}")
        return files

    def ingest_file(self, file_path: str | Path) -> IngestedDocument:
        """Read, parse, and evaluate a single report JSON file."""
        path = Path(file_path)
        timestamp = datetime.now(timezone.utc).isoformat()

        # Step 1: Read raw content
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as exc:
            logger.error(f"Failed to read file {path}: {exc}")
            return IngestedDocument(
                file_path=str(path),
                file_name=path.name,
                status=IngestionStatus.MALFORMED_JSON,
                ingested_at=timestamp,
                error_message=f"I/O Error: {exc}",
            )

        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Step 2: Parse JSON
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning(f"Malformed JSON in {path.name}: {exc}")
            return IngestedDocument(
                file_path=str(path),
                file_name=path.name,
                status=IngestionStatus.MALFORMED_JSON,
                ingested_at=timestamp,
                file_hash=file_hash,
                error_message=f"JSON Decode Error at line {exc.lineno}, col {exc.colno}: {exc.msg}",
            )

        if not isinstance(payload, dict):
            logger.warning(f"Root JSON is not an object in {path.name}")
            return IngestedDocument(
                file_path=str(path),
                file_name=path.name,
                status=IngestionStatus.SCHEMA_ERROR,
                ingested_at=timestamp,
                file_hash=file_hash,
                error_message="Root JSON payload must be an object/dict",
            )

        # Step 3: Extract envelope metadata
        trace_id = str(payload.get("traceId", "")).strip()
        data_block = payload.get("data", {})
        if not isinstance(data_block, dict):
            data_block = {}

        # Extract metaDetails array or object flexibly
        meta_list = (
            extract_nested_field(payload, "data.metaDetails")
            or extract_nested_field(payload, "metaDetails")
            or payload.get("metadata")
            or data_block.get("metaDetails")
        )
        meta_dict = _flatten_meta_details(meta_list)

        header_block = (
            payload.get("header", {}) if isinstance(payload.get("header"), dict) else {}
        )
        source_system = (
            meta_dict.get("source_system")
            or payload.get("source_system")
            or data_block.get("source_system")
            or header_block.get("source_system")
            or "UNKNOWN"
        )
        claim_no = meta_dict.get("claim_no", "") or header_block.get("claim_no", "")
        nt_code = meta_dict.get("nt_code", "") or header_block.get("nt_code", "")
        consumer_client_id = meta_dict.get("ConsumerClientId", "") or header_block.get(
            "ConsumerClientId", ""
        )
        destination_identifier = meta_dict.get(
            "DestinationIdentifier", ""
        ) or header_block.get("DestinationIdentifier", "")

        # Resolve configured clinic adapter profile
        sys_key = str(source_system).strip().upper()
        adapter = (
            self.clinic_mappings.get(sys_key)
            or self.clinic_mappings.get(source_system)
            or self.clinic_mappings.get("DEFAULT")
            or {}
        )

        # Support custom meta_details_field from adapter
        custom_meta_field = adapter.get("meta_details_field")
        if custom_meta_field and custom_meta_field != "data.metaDetails":
            meta_dict.update(
                _flatten_meta_details(extract_nested_field(payload, custom_meta_field))
            )

        doc_field = adapter.get("document_id_field", "data.documentId")
        corr_field = adapter.get("correlation_id_field", "data.correlationId")
        resp_field = adapter.get("response_details_field", "data.responseDetails")

        document_id = str(
            extract_nested_field(
                payload, doc_field, default=data_block.get("documentId", "")
            )
            or ""
        ).strip()
        correlation_id = str(
            extract_nested_field(
                payload, corr_field, default=data_block.get("correlationId", "")
            )
            or ""
        ).strip()

        # Step 4: Extract response details via configured adapter path
        response_details = extract_nested_field(
            payload, resp_field, default=data_block.get("responseDetails", [])
        )
        if not isinstance(response_details, list):
            response_details = []

        # Deduplication hash
        payload_hash = self.compute_content_hash(response_details)

        # Step 5: duplicate check (Metadata -> Claim Context -> Content Hash)
        is_dup, err_type, err_msg = self.check_duplicate(
            payload_hash=payload_hash,
            document_id=document_id,
            claim_no=claim_no,
            source_system=source_system,
        )
        if is_dup:
            logger.info(
                f"Duplicate document detected ({err_type}): {path.name} "
                f"(doc_id={document_id or 'N/A'}, hash={payload_hash[:10]}...)"
            )
        else:
            self.register_seen(
                payload_hash=payload_hash,
                document_id=document_id,
                claim_no=claim_no,
                source_system=source_system,
            )

        return IngestedDocument(
            file_path=str(path),
            file_name=path.name,
            status=(
                IngestionStatus.DUPLICATE_SUPPRESSED
                if is_dup
                else IngestionStatus.SUCCESS
            ),
            ingested_at=timestamp,
            trace_id=trace_id,
            document_id=document_id,
            correlation_id=correlation_id,
            source_system=source_system,
            claim_no=claim_no,
            nt_code=nt_code,
            consumer_client_id=consumer_client_id,
            destination_identifier=destination_identifier,
            file_hash=file_hash,
            payload_hash=payload_hash,
            raw_payload=payload,
            response_details=response_details,
            error_message=(
                (
                    err_msg
                    or "Duplicate report content previously ingested and suppressed"
                )
                if is_dup
                else None
            ),
        )
