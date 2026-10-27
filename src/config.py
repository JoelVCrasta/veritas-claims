from __future__ import annotations

import json5
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("veritas.config")


def load_jsonc(file_path: str | Path) -> Any:
    """Load and parse a JSON/JSONC file supporting comments and trailing commas."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            return json5.load(f)
        except Exception as exc:
            raise ValueError(f"Failed to parse JSONC config '{path}': {exc}") from exc


@dataclass(frozen=True)
class TestDefinition:
    canonical_name: str
    aliases: List[str]
    canonical_unit: str
    unit_conversions: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ReferenceRange:
    test_name: str
    range_low: Optional[float]
    range_high: Optional[float]
    outlier_low: Optional[float]
    outlier_high: Optional[float]
    unit: str = ""


@dataclass
class PipelineConfig:
    tests: Dict[str, TestDefinition] = field(default_factory=dict)
    alias_lookup: Dict[str, str] = field(default_factory=dict)
    ranges: Dict[str, ReferenceRange] = field(default_factory=dict)
    medicines: Dict[str, str] = field(default_factory=dict)
    clinic_mappings: Dict[str, Any] = field(default_factory=dict)
    dedup_active_checks: List[str] = field(
        default_factory=lambda: ["document_id", "content_hash", "claim_no"]
    )


def normalize_lookup_key(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(cleaned.split())


def load_pipeline_config(config_dir: str | Path = "config") -> PipelineConfig:
    base_dir = Path(config_dir)
    cfg = PipelineConfig()

    test_dict_path = base_dir / "test_dictionary.jsonc"
    if test_dict_path.exists():
        raw_tests = load_jsonc(test_dict_path)
        tests_map: Dict[str, TestDefinition] = {}
        alias_map: Dict[str, str] = {}

        for canonical_name, data in raw_tests.items():
            aliases = data.get("aliases", [])
            unit = data.get("canonical_unit", "")
            conversions = data.get("unit_conversions", {})

            tdef = TestDefinition(
                canonical_name=canonical_name,
                aliases=aliases,
                canonical_unit=unit,
                unit_conversions=conversions,
            )
            tests_map[canonical_name] = tdef

            alias_map[normalize_lookup_key(canonical_name)] = canonical_name

            for alias in aliases:
                norm_alias = normalize_lookup_key(alias)
                if norm_alias:
                    alias_map[norm_alias] = canonical_name

        cfg.tests = tests_map
        cfg.alias_lookup = alias_map
        logger.info(f"Loaded {len(tests_map)} tests with {len(alias_map)} aliases.")

    ranges_path = base_dir / "reference_ranges.jsonc"
    if ranges_path.exists():
        raw_ranges = load_jsonc(ranges_path)
        ranges_map: Dict[str, ReferenceRange] = {}
        for test_name, rdata in raw_ranges.items():
            ranges_map[test_name] = ReferenceRange(
                test_name=test_name,
                range_low=rdata.get("range_low"),
                range_high=rdata.get("range_high"),
                outlier_low=rdata.get("outlier_low"),
                outlier_high=rdata.get("outlier_high"),
                unit=rdata.get("unit", ""),
            )
        cfg.ranges = ranges_map
        logger.info(f"Loaded {len(ranges_map)} reference range definitions.")

    meds_path = base_dir / "medicine_mapping.jsonc"
    if meds_path.exists():
        raw_meds = load_jsonc(meds_path)
        meds_map: Dict[str, str] = {}
        for brand, generic in raw_meds.items():
            meds_map[normalize_lookup_key(brand)] = generic
        cfg.medicines = meds_map
        logger.info(f"Loaded {len(meds_map)} brand-to-generic medicine mappings.")

    clinics_path = base_dir / "clinic_mappings.jsonc"
    if clinics_path.exists():
        cfg.clinic_mappings = load_jsonc(clinics_path)
        logger.info(f"Loaded {len(cfg.clinic_mappings)} clinic adapter profiles.")

    dedup_path = base_dir / "deduplication.jsonc"
    if dedup_path.exists():
        dedup_cfg = load_jsonc(dedup_path)
        if isinstance(dedup_cfg, dict):
            checks_cfg = dedup_cfg.get("checks", {})
            if isinstance(checks_cfg, dict) and checks_cfg:
                cfg.dedup_active_checks = [
                    k for k, enabled in checks_cfg.items() if enabled
                ]
        logger.info(
            f"Configured active deduplication checks: {cfg.dedup_active_checks}"
        )

    return cfg
