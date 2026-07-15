

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from src.standardisation import (
    normalize_test_name,
    extract_numeric,
    normalize_unit,
    normalize_gender,
    normalize_date,
    normalize_age,
    normalize_medicine,
    parse_range,
)


class TestTestNameNormalization(unittest.TestCase):
    """Tests for FR-2.1: Test name normalization"""

    def test_exact_match_variant(self):
        """aemoglobin should map to Hemoglobin"""
        canonical, method, confidence = normalize_test_name("aemoglobin")
        self.assertEqual(canonical, "Hemoglobin")
        self.assertEqual(method, "exact")

    def test_haemoglobin_maps_to_hemoglobin(self):
        canonical, method, confidence = normalize_test_name("HAEMOGLOBIN")
        self.assertEqual(canonical, "Hemoglobin")

    def test_platelet_count_variant(self):
        canonical, method, confidence = normalize_test_name("atelet Count")
        self.assertEqual(canonical, "Platelet Count")

    def test_unknown_test_returns_original(self):
        """Unknown test names should come back unchanged"""
        canonical, method, confidence = normalize_test_name("SomeRandomTest123")
        self.assertEqual(method, "none")

    def test_empty_test_name(self):
        canonical, method, confidence = normalize_test_name("")
        self.assertEqual(canonical, "")

    def test_tlc_variant(self):
        canonical, method, confidence = normalize_test_name("Total Leucocyte Count (TLC)")
        self.assertEqual(canonical, "WBC Count")

    def test_alt_variant(self):
        canonical, method, confidence = normalize_test_name("ALANINE AMINOTRANSFERASE")
        self.assertEqual(canonical, "ALT (SGPT)")


class TestNumericExtraction(unittest.TestCase):
    """Tests for FR-2.3: Numeric conversion"""

    def test_plain_number(self):
        value, text = extract_numeric("12.5")
        self.assertEqual(value, 12.5)

    def test_number_with_unit(self):
        value, text = extract_numeric("12.0 g/dL")
        self.assertEqual(value, 12.0)

    def test_number_with_comma(self):
        """4,290 should become 4290"""
        value, text = extract_numeric("4,290 cells/cu.mm")
        self.assertEqual(value, 4290.0)

    def test_none_input(self):
        value, text = extract_numeric(None)
        self.assertIsNone(value)

    def test_empty_string(self):
        value, text = extract_numeric("")
        self.assertIsNone(value)

    def test_negative_text(self):
        """NEGATIVE is not numeric"""
        value, text = extract_numeric("NEGATIVE")
        self.assertIsNone(value)

    def test_less_than_prefix(self):
        """< 50 should extract 50"""
        value, text = extract_numeric("< 50")
        self.assertEqual(value, 50.0)

    def test_hl_prefix(self):
        """H 0.7 % should extract 0.7"""
        value, text = extract_numeric("H 0.7 %")
        self.assertEqual(value, 0.7)


class TestGenderNormalization(unittest.TestCase):
    """Tests for FR-2.5: Gender normalization"""

    def test_m_to_male(self):
        self.assertEqual(normalize_gender("M"), "Male")

    def test_male_to_male(self):
        self.assertEqual(normalize_gender("Male"), "Male")

    def test_f_to_female(self):
        self.assertEqual(normalize_gender("F"), "Female")

    def test_female_to_female(self):
        self.assertEqual(normalize_gender("FEMALE"), "Female")

    def test_redacted_returns_none(self):
        self.assertIsNone(normalize_gender("[GENDER REDACTED]"))

    def test_none_input(self):
        self.assertIsNone(normalize_gender(None))


class TestDateNormalization(unittest.TestCase):
    """Tests for FR-2.5: Date normalization"""

    def test_dd_mm_yyyy(self):
        result = normalize_date("09-10-2025")
        self.assertEqual(result, "2025-10-09")

    def test_dd_mon_yyyy(self):
        result = normalize_date("07-Oct-2025")
        self.assertEqual(result, "2025-10-07")

    def test_dd_slash_mon_slash_yyyy(self):
        result = normalize_date("10/Oct/2025")
        self.assertEqual(result, "2025-10-10")

    def test_placeholder_returns_none(self):
        result = normalize_date("DD/MM/YYYY")
        self.assertIsNone(result)

    def test_empty_returns_none(self):
        result = normalize_date("")
        self.assertIsNone(result)


class TestAgeNormalization(unittest.TestCase):
    """Tests for FR-2.5: Age normalization"""

    def test_redacted_returns_none(self):
        self.assertIsNone(normalize_age("[AGE REDACTED]"))

    def test_year_format(self):
        age = normalize_age("33Y11M")
        self.assertAlmostEqual(age, 33.9, places=0)

    def test_plain_number(self):
        age = normalize_age("45")
        self.assertEqual(age, 45.0)


class TestMedicineMappig(unittest.TestCase):
    """Tests for FR-2.6: Medicine name mapping"""

    def test_known_brand_mapped(self):
        brand, generic = normalize_medicine("Tab. miso")
        self.assertEqual(generic, "Misoprostol")

    def test_unknown_medicine_returns_original(self):
        brand, generic = normalize_medicine("Some Unknown Medicine")
        self.assertEqual(generic, "Some Unknown Medicine")

    def test_none_returns_none(self):
        brand, generic = normalize_medicine(None)
        self.assertIsNone(brand)


class TestParseRange(unittest.TestCase):
    """Tests for range parsing"""

    def test_simple_range(self):
        low, high = parse_range("4000-10000")
        self.assertEqual(low, 4000.0)
        self.assertEqual(high, 10000.0)

    def test_less_than(self):
        low, high = parse_range("<50")
        self.assertIsNone(low)
        self.assertEqual(high, 50.0)

    def test_empty_range(self):
        low, high = parse_range("")
        self.assertIsNone(low)
        self.assertIsNone(high)

    def test_decimal_range(self):
        low, high = parse_range("3.5-5.0")
        self.assertEqual(low, 3.5)
        self.assertEqual(high, 5.0)


if __name__ == "__main__":
    unittest.main()
