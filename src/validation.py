

import json
import os
import logging

logger = logging.getLogger(__name__)

# Load reference ranges config
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")

with open(os.path.join(CONFIG_DIR, "reference_ranges.json"), "r") as f:
    REFERENCE_RANGES = json.load(f)


def classify_result(test_canonical, result_value, result_text, range_low, range_high):
    """
    FR-3.3: Classify a test result as one of:
    - Within Range
    - Above Range
    - Below Range
    - Outlier
    - Invalid
    - Not Evaluated (if no range info available)

    Also checks for outliers (FR-3.2) using our config file ranges.
    """
    # If result is not numeric but should be
    if result_value is None:
        if result_text and result_text.upper() in ["POSITIVE", "NEGATIVE", "NOT DETECTED", "ABSENT"]:
            # these are valid non-numeric results
            return "Valid Text Result", False, False
        return "Invalid", False, False

    # Check for physiologically implausible outliers (FR-3.2)
    if test_canonical in REFERENCE_RANGES:
        ref = REFERENCE_RANGES[test_canonical]
        outlier_low = ref.get("outlier_low")
        outlier_high = ref.get("outlier_high")

        if outlier_low is not None and result_value < outlier_low:
            return "Outlier", True, False
        if outlier_high is not None and result_value > outlier_high:
            return "Outlier", True, False

        # FR-3.1: Range validation using our reference ranges
        ref_low = ref.get("low")
        ref_high = ref.get("high")

        if ref_low is not None and result_value < ref_low:
            return "Below Range", False, True
        if ref_high is not None and result_value > ref_high:
            return "Above Range", False, True

        return "Within Range", False, False

    # If we have range from the record itself, use that
    if range_low is not None and range_high is not None:
        if result_value < range_low:
            return "Below Range", False, True
        elif result_value > range_high:
            return "Above Range", False, True
        else:
            return "Within Range", False, False

    if range_high is not None:
        if result_value > range_high:
            return "Above Range", False, True
        return "Within Range", False, False

    if range_low is not None:
        if result_value < range_low:
            return "Below Range", False, True
        return "Within Range", False, False

    # No range info available
    return "Not Evaluated", False, False


def validate_row(row):
    """
    Run all validations on a single standardized row.
    Adds:
    - analytics_classification
    - is_outlier
    - is_flagged
    - flag_reason
    """
    test_canonical = row.get("test_name_canonical", "")
    result_value = row.get("result_value")
    result_text = row.get("result_text", "")
    range_low = row.get("range_low")
    range_high = row.get("range_high")
    record_type = row.get("record_type", "")

    # Only validate lab report rows that have test results
    if record_type != "lab_report":
        row["analytics_classification"] = None
        row["is_outlier"] = False
        row["is_flagged"] = False
        row["flag_reason"] = None
        return row

    # FR-3.4: Flag if result_text has mixed/contradictory data
    flag_reason = None
    is_flagged_for_data_issue = False

    if result_text and "," in str(result_text) and result_value is None:
        # combined multi-value string and we couldn't parse it
        flag_reason = "Multi-value result string, could not parse numeric"
        is_flagged_for_data_issue = True

    # FR-3.3: Classify the result
    analytics_class, is_outlier, is_range_flag = classify_result(
        test_canonical, result_value, result_text, range_low, range_high
    )

    is_flagged = is_outlier or is_range_flag or is_flagged_for_data_issue

    if is_outlier and not flag_reason:
        flag_reason = f"Physiologically implausible value: {result_value}"
    elif is_range_flag and not flag_reason:
        flag_reason = f"Result outside reference range"

    row["analytics_classification"] = analytics_class
    row["is_outlier"] = is_outlier
    row["is_flagged"] = is_flagged
    row["flag_reason"] = flag_reason

    return row


def validate_records(rows):
    """
    Run validation on all rows.
    Returns validated rows and a list of flagged rows.
    """
    validated = []
    flagged = []

    for row in rows:
        validated_row = validate_row(row)
        validated.append(validated_row)

        if validated_row.get("is_flagged"):
            flagged.append(validated_row)

    logger.info(f"Validation done: {len(validated)} total, {len(flagged)} flagged")
    return validated, flagged
