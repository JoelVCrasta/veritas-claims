import unittest

from src.config import load_pipeline_config
from src.standardisation import StandardisationEngine


class TestStandardisationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline_config("config")
        cls.std = StandardisationEngine(cls.config)

    def test_name_exact_and_alias_normalisation(self) -> None:
        cases = [
            ("HAEMOGLOBIN", "HAEMOGLOBIN", "EXACT"),
            ("Hb", "HAEMOGLOBIN", "ALIAS_LOOKUP"),
            ("Hemoglobin", "HAEMOGLOBIN", "ALIAS_LOOKUP"),
            ("HGB", "HAEMOGLOBIN", "ALIAS_LOOKUP"),
            ("aemoglobin", "HAEMOGLOBIN", "ALIAS_LOOKUP"),
            ("TOTAL WBC COUNT", "WHITE BLOOD CELL COUNT", "ALIAS_LOOKUP"),
            ("tal WBC Count", "WHITE BLOOD CELL COUNT", "ALIAS_LOOKUP"),
            ("K+", "POTASSIUM", "ALIAS_LOOKUP"),
            ("Na+", "SODIUM", "ALIAS_LOOKUP"),
            ("CREATININE, SERUM", "SERUM CREATININE", "ALIAS_LOOKUP"),
        ]
        for raw, expected_canonical, expected_method in cases:
            canonical, method, conf = self.std.normalize_test_name(raw)
            self.assertEqual(canonical, expected_canonical, f"Failed for '{raw}'")
            self.assertEqual(method, expected_method)
            self.assertEqual(conf, 1.0)

    def test_fuzzy_matching(self) -> None:
        # Subtle typo in total leucocyte count
        raw = "Totall Leucocyte Count"
        canonical, method, conf = self.std.normalize_test_name(raw)
        self.assertEqual(canonical, "WHITE BLOOD CELL COUNT")
        self.assertEqual(method, "FUZZY_MATCH")
        self.assertGreater(conf, 0.85)

    def test_numeric_conversion(self) -> None:
        cases = [
            ("9700", 9700.0),
            ("5.45", 5.45),
            ("<50", 50.0),
            ("<= 1.15", 1.15),
            ("120000 cells/cu.mm", 120000.0),
            ("98.6 degree F", 98.6),
            ("-0.5", -0.5),
            ("NEGATIVE", None),
            ("result", None),
            (None, None),
        ]
        for raw, expected_float in cases:
            num_val, text_val = self.std.parse_numeric_result(raw)
            self.assertEqual(num_val, expected_float, f"Failed for '{raw}'")

    def test_unit_conversion(self) -> None:
        # Haemoglobin gm/dL -> g/dL (factor 1.0)
        unit, val = self.std.convert_unit("HAEMOGLOBIN", "gm/dL", 14.2)
        self.assertEqual(unit, "g/dL")
        self.assertEqual(val, 14.2)

        # Haemoglobin g/L -> g/dL (factor 0.1)
        unit, val = self.std.convert_unit("HAEMOGLOBIN", "g/L", 142.0)
        self.assertEqual(unit, "g/dL")
        self.assertEqual(val, 14.2)

    def test_demographic_age_parsing(self) -> None:
        # Compound: 33Y11M265D -> 33 + 11/12 + 265/365.25 = 34.6 years
        age_str, age_years, age_text = self.std.parse_age("33Y11M265D")
        self.assertEqual(age_str, "34.6")
        self.assertEqual(age_years, "35")
        self.assertEqual(age_text, "33Y11M265D")

        # Simple integer
        age_str, age_years, _ = self.std.parse_age("45 Y")
        self.assertEqual(age_str, "45.0")
        self.assertEqual(age_years, "45")

        # Redacted
        age_str, age_years, age_text = self.std.parse_age("[AGE REDACTED]")
        self.assertEqual(age_str, "")
        self.assertEqual(age_years, "")
        self.assertEqual(age_text, "[AGE REDACTED]")

    def test_demographic_gender_normalisation(self) -> None:
        self.assertEqual(self.std.normalize_gender("Male"), "M")
        self.assertEqual(self.std.normalize_gender("M"), "M")
        self.assertEqual(self.std.normalize_gender("female"), "F")
        self.assertEqual(self.std.normalize_gender("F"), "F")
        self.assertEqual(self.std.normalize_gender("[GENDER REDACTED]"), "")

    def test_demographic_date_normalisation(self) -> None:
        self.assertEqual(self.std.parse_iso_date("09-10-2025"), "2025-10-09")
        self.assertEqual(self.std.parse_iso_date("08/Oct/2025"), "2025-10-08")
        self.assertEqual(self.std.parse_iso_date("2025-10-09"), "2025-10-09")
        # Non-date strings are handled safely
        self.assertEqual(self.std.parse_iso_date("LAB10945"), "LAB10945")

    def test_medicine_mapping(self) -> None:
        med1 = self.std.standardize_medication({"medicine": "TAB DOLO 650", "dose": "650 mg", "frequency": "SOS"})
        self.assertEqual(med1.medicine, "Paracetamol")
        self.assertEqual(med1.medicine_type, "TABLET")

        med2 = self.std.standardize_medication({"medicine": "Inj. Pantocid 40 mg", "dose": "40 mg"})
        self.assertEqual(med2.medicine, "Pantoprazole")
        self.assertEqual(med2.medicine_type, "INJECTION")

        med3 = self.std.standardize_medication({"medicine": "TAB. CEFTAS- 400", "dose": "400"})
        self.assertEqual(med3.medicine, "Cefixime")

    def test_header_row_detection(self) -> None:
        corrupt_header = {
            "page_no": 0,
            "range": "range",
            "result": "result",
            "test_analytics": "low/normal/high",
            "test_name": "test_name",
            "unit": "unit",
        }
        self.assertTrue(self.std.is_header_row(corrupt_header))

        valid_row = {
            "page_no": 0,
            "range": "12.0-17.5",
            "result": "14.2",
            "test_name": "Haemoglobin",
            "unit": "g/dL",
        }
        self.assertFalse(self.std.is_header_row(valid_row))


if __name__ == "__main__":
    unittest.main()
