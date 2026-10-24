"""Unit tests for the validation module."""

import unittest

from src.config import load_pipeline_config
from src.standardisation import StandardizedLabTest
from src.validation import ClinicalAnalyticsFlag, ValidationEngine


class TestValidationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline_config("config")
        cls.validator = ValidationEngine(cls.config)

    def test_within_range(self) -> None:
        test = StandardizedLabTest(
            test_name_canonical="HAEMOGLOBIN",
            test_name_original="Hb",
            result_value=14.5,
            result_text="14.5",
            unit_canonical="g/dL",
            unit_original="g/dL",
            range_low=12.0,
            range_high=17.5,
            range_text="12.0-17.5",
        )
        flag, msg = self.validator.validate_lab_test(test)
        self.assertEqual(flag, ClinicalAnalyticsFlag.WITHIN_RANGE)

    def test_above_range(self) -> None:
        test = StandardizedLabTest(
            test_name_canonical="HAEMOGLOBIN",
            test_name_original="Hb",
            result_value=19.2,
            result_text="19.2",
            unit_canonical="g/dL",
            unit_original="g/dL",
            range_low=12.0,
            range_high=17.5,
            range_text="12.0-17.5",
        )
        flag, msg = self.validator.validate_lab_test(test)
        self.assertEqual(flag, ClinicalAnalyticsFlag.ABOVE_RANGE)

    def test_below_range(self) -> None:
        test = StandardizedLabTest(
            test_name_canonical="HAEMOGLOBIN",
            test_name_original="Hb",
            result_value=8.5,
            result_text="8.5",
            unit_canonical="g/dL",
            unit_original="g/dL",
            range_low=12.0,
            range_high=17.5,
            range_text="12.0-17.5",
        )
        flag, msg = self.validator.validate_lab_test(test)
        self.assertEqual(flag, ClinicalAnalyticsFlag.BELOW_RANGE)

    def test_outlier_detection_extreme_high(self) -> None:
        # Hb = 9700 (leaked WBC value into hemoglobin field)
        test = StandardizedLabTest(
            test_name_canonical="HAEMOGLOBIN",
            test_name_original="aemoglobin",
            result_value=9700.0,
            result_text="9700",
            unit_canonical="g/dL",
            unit_original="cell/cu.mm",
            range_low=12.0,
            range_high=17.5,
            range_text="12.0-17.5",
        )
        flag, msg = self.validator.validate_lab_test(test)
        self.assertEqual(flag, ClinicalAnalyticsFlag.OUTLIER)
        self.assertIn("exceeds physiological upper bound", msg)

    def test_outlier_detection_extreme_low(self) -> None:
        # Potassium = 0.5 mmol/L (lethal hypokalemia / instrument failure)
        test = StandardizedLabTest(
            test_name_canonical="POTASSIUM",
            test_name_original="K+",
            result_value=0.5,
            result_text="0.5",
            unit_canonical="mmol/L",
            unit_original="mmol/L",
            range_low=3.5,
            range_high=5.1,
            range_text="3.5-5.1",
        )
        flag, msg = self.validator.validate_lab_test(test)
        self.assertEqual(flag, ClinicalAnalyticsFlag.OUTLIER)

    def test_invalid_missing_result(self) -> None:
        test = StandardizedLabTest(
            test_name_canonical="HAEMOGLOBIN",
            test_name_original="Hb",
            result_value=None,
            result_text="result",
            unit_canonical="g/dL",
            unit_original="g/dL",
            range_low=12.0,
            range_high=17.5,
            range_text="12.0-17.5",
        )
        flag, msg = self.validator.validate_lab_test(test)
        self.assertEqual(flag, ClinicalAnalyticsFlag.INVALID)

    def test_qualitative_result_unvalidated(self) -> None:
        test = StandardizedLabTest(
            test_name_canonical="URIC ACID",
            test_name_original="URIC ACID",
            result_value=None,
            result_text="NIL",
            unit_canonical="mg/dL",
            unit_original="",
            range_low=3.5,
            range_high=7.2,
            range_text="3.5-7.2",
        )
        flag, msg = self.validator.validate_lab_test(test)
        self.assertEqual(flag, ClinicalAnalyticsFlag.UNVALIDATED)


if __name__ == "__main__":
    unittest.main()
