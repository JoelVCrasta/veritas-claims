from __future__ import annotations

import logging
from enum import Enum
from typing import Tuple

from src.config import PipelineConfig
from src.standardisation import StandardizedLabTest

logger = logging.getLogger("veritas.validation")


class ClinicalAnalyticsFlag(str, Enum):
    WITHIN_RANGE = "WITHIN_RANGE"
    ABOVE_RANGE = "ABOVE_RANGE"
    BELOW_RANGE = "BELOW_RANGE"
    OUTLIER = "OUTLIER"
    INVALID = "INVALID"
    UNVALIDATED = "UNVALIDATED"


class ValidationEngine:
    """Validates standardized lab values against clinical bounds and outlier thresholds."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def validate_lab_test(
        self, test: StandardizedLabTest
    ) -> Tuple[ClinicalAnalyticsFlag, str]:
        """Evaluate a lab test result."""
        # Corrupted or missing result
        if test.result_value is None:
            if not test.result_text or test.result_text.lower() in (
                "result",
                "invalid",
                "error",
            ):
                return (
                    ClinicalAnalyticsFlag.INVALID,
                    "Result is missing or contains invalid header text",
                )
            # Qualitative results ('NEGATIVE', 'NIL')
            return (
                ClinicalAnalyticsFlag.UNVALIDATED,
                f"Qualitative text result: '{test.result_text}'",
            )

        val = test.result_value
        canonical_name = test.test_name_canonical
        cfg_range = self.config.ranges.get(canonical_name)

        # Determine effective range bounds
        r_low = (
            test.range_low
            if test.range_low is not None
            else (cfg_range.range_low if cfg_range else None)
        )
        r_high = (
            test.range_high
            if test.range_high is not None
            else (cfg_range.range_high if cfg_range else None)
        )

        outlier_low = cfg_range.outlier_low if cfg_range else None
        outlier_high = cfg_range.outlier_high if cfg_range else None

        # Outlier check
        if outlier_low is not None and val < outlier_low:
            return (
                ClinicalAnalyticsFlag.OUTLIER,
                f"Value {val} {test.unit_canonical} is below physiological lower bound ({outlier_low})",
            )
        if outlier_high is not None and val > outlier_high:
            return (
                ClinicalAnalyticsFlag.OUTLIER,
                f"Value {val} {test.unit_canonical} exceeds physiological upper bound ({outlier_high})",
            )

        # Reference range bounds check
        if r_high is not None and val > r_high:
            return (
                ClinicalAnalyticsFlag.ABOVE_RANGE,
                f"Value {val} exceeds upper reference limit of {r_high} {test.unit_canonical}",
            )
        if r_low is not None and val < r_low:
            return (
                ClinicalAnalyticsFlag.BELOW_RANGE,
                f"Value {val} is below lower reference limit of {r_low} {test.unit_canonical}",
            )

        if r_low is not None or r_high is not None:
            return (
                ClinicalAnalyticsFlag.WITHIN_RANGE,
                "Value is within biological reference interval",
            )

        # Fallback to existing clinic annotation if available
        existing_analytics = test.test_analytics.strip().lower()
        if existing_analytics in ("normal", "within range"):
            return (
                ClinicalAnalyticsFlag.WITHIN_RANGE,
                "Reported normal by source facility",
            )
        if existing_analytics in ("high", "above range"):
            return ClinicalAnalyticsFlag.ABOVE_RANGE, "Reported high by source facility"
        if existing_analytics in ("low", "below range"):
            return ClinicalAnalyticsFlag.BELOW_RANGE, "Reported low by source facility"

        return (
            ClinicalAnalyticsFlag.UNVALIDATED,
            "No reference range available for validation",
        )

    def enrich_test(self, test: StandardizedLabTest) -> StandardizedLabTest:
        """Evaluate validation rules and populate test.test_analytics."""
        flag, message = self.validate_lab_test(test)
        test.test_analytics = flag.value
        return test
