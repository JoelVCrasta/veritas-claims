from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from dateutil import parser
from rapidfuzz import fuzz, process

from src.config import PipelineConfig, normalize_lookup_key
from src.models import resolve_field_value

logger = logging.getLogger("veritas.standardisation")


@dataclass
class StandardizedLabTest:
    test_name_canonical: str
    test_name_original: str
    result_value: Optional[float]
    result_text: str
    unit_canonical: str
    unit_original: str
    range_low: Optional[float]
    range_high: Optional[float]
    range_text: str
    test_analytics: str = ""
    normalization_method: str = "UNMAPPED"
    normalization_confidence: float = 0.0
    page_no: str = ""


@dataclass
class StandardizedDemographics:
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


@dataclass
class StandardizedMedication:
    medicine: str
    medicine_original: str
    dose: str = ""
    frequency: str = ""
    medicine_type: str = ""


class StandardisationEngine:
    """Normalisation engine for medical tests, demographics, and medications."""

    def __init__(self, config: PipelineConfig, fuzzy_threshold: float = 0.85) -> None:
        self.config = config
        self.fuzzy_threshold = fuzzy_threshold

    HEADER_KEYWORDS = {
        "test_name": {"test_name", "test", "investigation", "parameter"},
        "result": {"result", "value", "observed_value", "findings"},
        "range": {"range", "reference_range", "biological_reference_interval", "normal"},
        "unit": {"unit", "units"},
    }

    @classmethod
    def is_header_row(cls, item: Dict[str, Any]) -> bool:
        """Identify if a row is a leaked table header."""
        signals = sum(
            str(item.get(k, "")).strip().lower() in words
            for k, words in cls.HEADER_KEYWORDS.items()
        )
        return signals >= 2

    def normalize_test_name(self, raw_name: str) -> Tuple[str, str, float]:
        """
        Normalize test name using exact match, alias lookup, or fuzzy matching.
        Returns: (canonical_name, method, confidence)
        """
        if not raw_name or not isinstance(raw_name, str):
            return "UNKNOWN", "UNMAPPED", 0.0

        cleaned = raw_name.strip()
        norm_key = normalize_lookup_key(cleaned)

        # 1. Alias dictionary lookup
        if norm_key in self.config.alias_lookup:
            canonical = self.config.alias_lookup[norm_key]
            method = (
                "EXACT"
                if norm_key == normalize_lookup_key(canonical)
                else "ALIAS_LOOKUP"
            )
            return canonical, method, 1.0

        # 2. Fuzzy match against all known aliases using rapidfuzz WRatio
        match = process.extractOne(
            norm_key,
            self.config.alias_lookup.keys(),
            scorer=fuzz.WRatio,
            score_cutoff=self.fuzzy_threshold * 100.0,
        )
        if match:
            best_key, score, _ = match
            return self.config.alias_lookup[best_key], "FUZZY_MATCH", round(score / 100.0, 3)

        return cleaned, "UNMAPPED", 0.0

    @staticmethod
    def parse_numeric_result(raw_result: Any) -> Tuple[Optional[float], str]:
        """
        Extract numeric float value from string while preserving full raw text.
        """
        if raw_result is None:
            return None, ""

        text = str(raw_result).strip()
        if not text:
            return None, ""

        lowered = text.lower()
        if lowered in (
            "result",
            "null",
            "none",
            "n/a",
            "na",
            "-",
            "nil",
            "negative",
            "positive",
        ):
            return None, text

        # Strip leading comparators like '<', '>', '<=', '>='
        clean_s = re.sub(r"^[<>=~]+", "", text).strip()

        # Match first float or integer
        match = re.search(r"[-+]?\d+(?:\.\d+)?", clean_s)
        if match:
            try:
                return float(match.group(0)), text
            except ValueError:
                pass

        return None, text

    @staticmethod
    def parse_range_bounds(
        range_str: Any,
    ) -> Tuple[Optional[float], Optional[float], str]:
        """Parse lower and upper bounds from a range string (e.g. '4000-10000', '<50')."""
        if range_str is None:
            return None, None, ""

        text = str(range_str).strip()
        if not text or text.lower() in ("range", "null", "none", "n/a", "na", "-"):
            return None, None, text

        # Interval format: '4000-10000' or '4.50 to 5.50'
        match_interval = re.search(
            r"(\d+(?:\.\d+)?)\s*[-–—to]+\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE
        )
        if match_interval:
            try:
                return (
                    float(match_interval.group(1)),
                    float(match_interval.group(2)),
                    text,
                )
            except ValueError:
                pass

        # Upper bound only: '<50' or '<= 50'
        match_lt = re.match(r"^<=?\s*(\d+(?:\.\d+)?)", text)
        if match_lt:
            try:
                return 0.0, float(match_lt.group(1)), text
            except ValueError:
                pass

        # Lower bound only: '>60' or '>= 60'
        match_gt = re.match(r"^>=?\s*(\d+(?:\.\d+)?)", text)
        if match_gt:
            try:
                return float(match_gt.group(1)), None, text
            except ValueError:
                pass

        return None, None, text

    def convert_unit(
        self, canonical_name: str, raw_unit: str, result_value: Optional[float]
    ) -> Tuple[str, Optional[float]]:
        """
        Convert incoming unit to canonical unit and scale numeric value.
        """
        test_def = self.config.tests.get(canonical_name)
        if not test_def:
            return raw_unit.strip() if raw_unit else "", result_value

        canonical_unit = test_def.canonical_unit
        if not raw_unit or not raw_unit.strip():
            return canonical_unit, result_value

        unit_str = raw_unit.strip()
        # Look up conversion factor
        multiplier = test_def.unit_conversions.get(unit_str)
        if multiplier is not None and result_value is not None:
            return canonical_unit, round(result_value * multiplier, 4)

        return canonical_unit if canonical_unit else unit_str, result_value

    def standardize_lab_test(
        self, raw_item: Dict[str, Any]
    ) -> Optional[StandardizedLabTest]:
        """Process a single raw test entry from report_details into StandardizedLabTest."""
        if self.is_header_row(raw_item):
            logger.debug(f"Skipping detected header row: {raw_item}")
            return None

        raw_test_name = str(raw_item.get("test_name", "")).strip()
        raw_result = raw_item.get("result")
        raw_unit = str(raw_item.get("unit", "")).strip()
        raw_range = raw_item.get("range")
        raw_analytics = str(raw_item.get("test_analytics", "")).strip()
        page_no = str(raw_item.get("page_no", ""))

        # 1. Normalize test name
        canonical_name, method, confidence = self.normalize_test_name(raw_test_name)

        # 2. Extract numeric result
        numeric_val, result_text = self.parse_numeric_result(raw_result)

        # 3. Unit conversion and scaling
        canonical_unit, scaled_value = self.convert_unit(
            canonical_name, raw_unit, numeric_val
        )

        # 4. Parse reference range bounds
        range_low, range_high, range_text = self.parse_range_bounds(raw_range)

        # If report had no range but config has standard reference range, fill bounds
        if (
            range_low is None
            and range_high is None
            and canonical_name in self.config.ranges
        ):
            cfg_range = self.config.ranges[canonical_name]
            range_low = cfg_range.range_low
            range_high = cfg_range.range_high
            if not range_text and (range_low is not None or range_high is not None):
                range_text = f"{range_low}-{range_high}"

        return StandardizedLabTest(
            test_name_canonical=canonical_name,
            test_name_original=raw_test_name,
            result_value=scaled_value,
            result_text=result_text,
            unit_canonical=canonical_unit,
            unit_original=raw_unit,
            range_low=range_low,
            range_high=range_high,
            range_text=range_text,
            test_analytics=raw_analytics,
            normalization_method=method,
            normalization_confidence=confidence,
            page_no=page_no,
        )

    @staticmethod
    def parse_age(raw_age: Any) -> Tuple[str, str, str]:
        """Parse age into (canonical_age_str, age_years_str, age_text)."""
        if raw_age is None:
            return "", "", ""

        text = str(raw_age).strip()
        if not text:
            return "", "", ""

        if text.startswith("[") and text.endswith("]"):
            return "", "", text

        # Compound strings
        match_compound = re.match(
            r"^(?:(\d+)\s*Y(?:ears?)?)?\s*(?:(\d+)\s*M(?:onths?)?)?\s*(?:(\d+)\s*D(?:ays?)?)?$",
            text,
            re.IGNORECASE,
        )
        if match_compound and any(match_compound.groups()):
            y = float(match_compound.group(1)) if match_compound.group(1) else 0.0
            m = float(match_compound.group(2)) if match_compound.group(2) else 0.0
            d = float(match_compound.group(3)) if match_compound.group(3) else 0.0
            total_years = y + (m / 12.0) + (d / 365.25)
            years_str = str(round(total_years, 1))
            return years_str, str(int(round(total_years))), text

        # Simple integer or decimal: '45 Y', '45'
        match_num = re.search(r"(\d+(?:\.\d+)?)", text)
        if match_num:
            val = float(match_num.group(1))
            return str(round(val, 1)), str(int(round(val))), text

        return text, "", text

    GENDER_MAP = {
        "m": "M", "male": "M", "man": "M",
        "f": "F", "female": "F", "woman": "F",
        "o": "OTHER", "other": "OTHER",
    }

    @classmethod
    def normalize_gender(cls, raw_gender: Any) -> str:
        """Standardize gender to 'M', 'F', 'OTHER', or redaction string."""
        if not raw_gender:
            return ""
        text = str(raw_gender).strip()
        if text.startswith("[") and text.endswith("]"):
            return ""
        return cls.GENDER_MAP.get(text.lower(), text.upper())

    @staticmethod
    def parse_iso_date(raw_date: Any) -> str:
        """Parse varied date formats to YYYY-MM-DD."""
        if not raw_date:
            return ""
        text = str(raw_date).strip()
        if not text or text.startswith("[") or len(text) < 4:
            return text
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            return text
        try:
            is_year_first = bool(re.match(r"^\d{4}[-/]", text))
            dt = parser.parse(text, dayfirst=not is_year_first)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, OverflowError, parser.ParserError):
            return text

    def standardize_demographics(
        self,
        basic_info: Dict[str, Any],
        field_map: Optional[Dict[str, list[str]]] = None,
    ) -> StandardizedDemographics:
        """Extract and normalize patient demographic fields from a basic_info block using adapter field mappings."""
        fmap = field_map or {}

        def get_field(field_name: str, fallback_keys: list[str]) -> Any:
            return resolve_field_value(basic_info, fmap.get(field_name) or fallback_keys)

        raw_age = get_field("age", ["age", "patient_age"])
        age_norm, age_years, age_text = self.parse_age(raw_age)

        raw_gender = get_field("gender", ["gender", "sex"])
        gender_norm = self.normalize_gender(raw_gender)

        bill_date = self.parse_iso_date(
            get_field("bill_date", ["bill_date", "billDate", "date"])
        )
        reports_date = self.parse_iso_date(
            get_field("reports_date", ["reports_date", "reportDate", "report_date"])
        )

        return StandardizedDemographics(
            patient_name=str(
                get_field(
                    "patient_name", ["patient_name", "patientName", "name", "pt_name"]
                )
            ).strip(),
            age=age_norm,
            age_years=age_years,
            age_text=age_text,
            gender=gender_norm,
            uhid=str(get_field("uhid", ["uhid", "mrn", "patient_id"])).strip(),
            hospital_name=str(
                get_field(
                    "hospital_name",
                    [
                        "lab_or_hospital_name",
                        "hospital_name",
                        "hospitalName",
                        "facility",
                    ],
                )
            ).strip(),
            doctor_name=str(
                get_field("doctor_name", ["doctor_name", "doctorName", "consultant"])
            ).strip(),
            bill_date=bill_date,
            reports_date=reports_date,
        )

    def standardize_medication(self, raw_med: Dict[str, Any]) -> StandardizedMedication:
        """Standardize medication name to generic molecule and extract dose/formulation."""
        medicine_raw = str(raw_med.get("medicine", "")).strip()
        dose = str(raw_med.get("dose", "")).strip()
        frequency = str(raw_med.get("frequency", "")).strip()
        med_type = str(raw_med.get("type", "") or "").strip()

        # Clean prefix forms like 'Tab.', 'Inj.', 'Cap.', 'Syp.'
        cleaned = re.sub(
            r"^(?:tab\.?|inj\.?|cap\.?|syp\.?|powder)\s+",
            "",
            medicine_raw,
            flags=re.IGNORECASE,
        ).strip()
        key_raw = normalize_lookup_key(medicine_raw)
        key_cleaned = normalize_lookup_key(cleaned)

        # 1. Exact match on raw or cleaned
        generic = self.config.medicines.get(key_raw) or self.config.medicines.get(
            key_cleaned
        )

        # 2. Sub-token matching ( 'Pantocid 40 m g'-> 'pantocid')
        if not generic:
            for k in (key_cleaned, key_raw):
                tokens = k.split()
                for i in range(len(tokens), 0, -1):
                    sub = " ".join(tokens[:i])
                    if sub in self.config.medicines:
                        generic = self.config.medicines[sub]
                        break
                if generic:
                    break

        canonical_medicine = generic if generic else medicine_raw

        # Extract formulation type if not specified
        if not med_type:
            lowered = medicine_raw.lower()
            if "tab" in lowered:
                med_type = "TABLET"
            elif "inj" in lowered:
                med_type = "INJECTION"
            elif "cap" in lowered:
                med_type = "CAPSULE"
            elif "syp" in lowered:
                med_type = "SYRUP"
            elif "powder" in lowered:
                med_type = "POWDER"

        return StandardizedMedication(
            medicine=canonical_medicine,
            medicine_original=medicine_raw,
            dose=dose,
            frequency=frequency,
            medicine_type=med_type,
        )
