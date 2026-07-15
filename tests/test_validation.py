
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from src.validation import classify_result, validate_row


class TestClassifyResult(unittest.TestCase):
    """Tests for FR-3.3: Analytics classification"""

    def test_within_range(self):
        classification, is_outlier, is_flagged = classify_result(
            "Hemoglobin", 14.0, "14.0", 12.0, 17.0
        )
        self.assertEqual(classification, "Within Range")
        self.assertFalse(is_outlier)

    def test_above_range(self):
        classification, is_outlier, is_flagged = classify_result(
            "Hemoglobin", 20.0, "20.0", 12.0, 17.0
        )
        self.assertEqual(classification, "Above Range")
        self.assertFalse(is_outlier)
        self.assertTrue(is_flagged)

    def test_below_range(self):
        classification, is_outlier, is_flagged = classify_result(
            "Hemoglobin", 8.0, "8.0", 12.0, 17.0
        )
        self.assertEqual(classification, "Below Range")
        self.assertFalse(is_outlier)
        self.assertTrue(is_flagged)

    def test_outlier_too_low(self):
        """Hemoglobin of 0.1 is physiologically implausible"""
        classification, is_outlier, is_flagged = classify_result(
            "Hemoglobin", 0.1, "0.1", 12.0, 17.0
        )
        self.assertEqual(classification, "Outlier")
        self.assertTrue(is_outlier)

    def test_outlier_too_high(self):
        """Hemoglobin of 999 is physiologically implausible"""
        classification, is_outlier, is_flagged = classify_result(
            "Hemoglobin", 999, "999", 12.0, 17.0
        )
        self.assertEqual(classification, "Outlier")
        self.assertTrue(is_outlier)

    def test_none_result(self):
        """None result with non-text value should be Invalid"""
        classification, is_outlier, is_flagged = classify_result(
            "Hemoglobin", None, "some_text", None, None
        )
        self.assertEqual(classification, "Invalid")

    def test_valid_text_result(self):
        """NEGATIVE is a valid result"""
        classification, is_outlier, is_flagged = classify_result(
            "Widal Test", None, "NEGATIVE", None, None
        )
        self.assertEqual(classification, "Valid Text Result")

    def test_no_range_info(self):
        """Unknown test with no range should be Not Evaluated"""
        classification, is_outlier, is_flagged = classify_result(
            "SomeUnknownTest", 5.0, "5.0", None, None
        )
        self.assertEqual(classification, "Not Evaluated")

    def test_platelet_outlier(self):
        """Platelet count of 2000 is way below the outlier threshold"""
        classification, is_outlier, is_flagged = classify_result(
            "Platelet Count", 100, "100", 150000, 410000
        )
        self.assertEqual(classification, "Outlier")
        self.assertTrue(is_outlier)


class TestValidateRow(unittest.TestCase):
    """Tests for the validate_row function"""

    def test_lab_report_row_gets_classification(self):
        """A lab report row should get analytics_classification set"""
        row = {
            "record_type": "lab_report",
            "test_name_canonical": "Hemoglobin",
            "result_value": 15.0,
            "result_text": "15.0 g/dL",
            "range_low": 12.0,
            "range_high": 17.5,
        }
        validated = validate_row(row)
        self.assertIsNotNone(validated["analytics_classification"])
        self.assertEqual(validated["analytics_classification"], "Within Range")

    def test_discharge_summary_row_skipped(self):
        """Discharge summary rows should not get a classification"""
        row = {
            "record_type": "discharge_summary",
            "medicine": "Misoprostol",
            "result_value": None,
        }
        validated = validate_row(row)
        self.assertIsNone(validated["analytics_classification"])
        self.assertFalse(validated["is_flagged"])

    def test_outlier_gets_flagged(self):
        """Outlier values should be flagged"""
        row = {
            "record_type": "lab_report",
            "test_name_canonical": "Hemoglobin",
            "result_value": 0.1,  # way too low
            "result_text": "0.1",
            "range_low": 12.0,
            "range_high": 17.5,
        }
        validated = validate_row(row)
        self.assertTrue(validated["is_outlier"])
        self.assertTrue(validated["is_flagged"])
        self.assertIsNotNone(validated["flag_reason"])


if __name__ == "__main__":
    unittest.main()
