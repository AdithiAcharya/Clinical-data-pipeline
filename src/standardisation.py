

import json
import re
import os
import difflib
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ----- Load config files -----

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")

def load_config(filename):
    path = os.path.join(CONFIG_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# These are loaded once when the module is imported
TEST_NAME_MAPPING = load_config("test_name_mapping.json")
UNIT_MAPPING = load_config("unit_mapping.json")
MEDICINE_MAPPING = load_config("medicine_mapping.json")

# Build a reverse lookup:
_REVERSE_NAME_MAP = {}
for canonical, variants in TEST_NAME_MAPPING.items():
    for v in variants:
        _REVERSE_NAME_MAP[v.lower().strip()] = canonical


# ----- Normalization -----

def normalize_test_name(raw_name, confidence_threshold=0.7):
    if not raw_name:
        return raw_name, "none", 0.0

    clean = raw_name.strip()
    lower = clean.lower()

    # Step 1: exact match in our lookup table
    if lower in _REVERSE_NAME_MAP:
        return _REVERSE_NAME_MAP[lower], "exact", 1.0

    # Step 2: fuzzy match using difflib
    all_variants = list(_REVERSE_NAME_MAP.keys())
    matches = difflib.get_close_matches(lower, all_variants, n=1, cutoff=confidence_threshold)

    if matches:
        best_match = matches[0]
        # get the score
        ratio = difflib.SequenceMatcher(None, lower, best_match).ratio()
        canonical = _REVERSE_NAME_MAP[best_match]
        return canonical, "fuzzy", round(ratio, 2)

    # No match found - return original
    return clean, "none", 0.0


# ----- Numeric Conversion -----

def extract_numeric(value_str):
    if value_str is None or value_str == "":
        return None, str(value_str)

    text = str(value_str).strip()

    # Handle special text values
    non_numeric_words = ["negative", "positive", "not detected", "absent", "n/a", "normal", "abnormal"]
    if text.lower() in non_numeric_words:
        return None, text

    # Remove common prefixes like < > H L
    clean = text
    clean = re.sub(r'^[HhLl]\s+', '', clean)  # remove H/L prefix (high/low markers)
    clean = re.sub(r'^[<>]\s*', '', clean)      # remove < >

    # Remove commas in numbers like 4,290
    clean = clean.replace(",", "")

    # Extract first number we find
    match = re.search(r'[-+]?\d+\.?\d*', clean)
    if match:
        try:
            return float(match.group()), text
        except ValueError:
            pass

    return None, text


# ---Unit Harmonization -----

def normalize_unit(test_canonical, raw_unit):
    if test_canonical in UNIT_MAPPING:
        canonical_unit = UNIT_MAPPING[test_canonical]["canonical_unit"]
        return canonical_unit
        
    # If not in config, just return the raw unit cleaned up
    return raw_unit.strip() if raw_unit else ""


# ----- FR-2.5: Demographic Normalization -----

def normalize_gender(raw_gender):
    if not raw_gender:
        return None

    g = raw_gender.strip().upper()
    if g in ["M", "MALE"]:
        return "Male"
    elif g in ["F", "FEMALE"]:
        return "Female"
    elif "[GENDER REDACTED]" in raw_gender:
        return None  # redacted - keep as null
    return raw_gender


def normalize_date(raw_date):
    if not raw_date or raw_date in ["DD/MM/YYYY", "", None]:
        return None

    formats = [
        "%d-%m-%Y",
        "%d-%b-%Y",
        "%d/%b/%Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(raw_date.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # couldn't parse - return original
    return raw_date


def normalize_age(raw_age):
    if not raw_age or "[AGE REDACTED]" in str(raw_age):
        return None

    # Try to find years from formats like 33Y11M or 33Y
    match = re.search(r'(\d+)\s*[Yy]', str(raw_age))
    if match:
        years = int(match.group(1))
        # also check months for decimal
        month_match = re.search(r'(\d+)\s*[Mm]', str(raw_age))
        if month_match:
            months = int(month_match.group(1))
            return round(years + months / 12, 1)
        return float(years)

    # Try plain number
    try:
        return float(str(raw_age).strip())
    except ValueError:
        return None


# -----  Medicine Name Mapping -----

def normalize_medicine(raw_medicine):

    if not raw_medicine:
        return raw_medicine, raw_medicine

    # Direct lookup first
    if raw_medicine in MEDICINE_MAPPING:
        return raw_medicine, MEDICINE_MAPPING[raw_medicine]

    # Try case-insensitive lookup
    for brand, generic in MEDICINE_MAPPING.items():
        if brand.lower() == raw_medicine.lower():
            return raw_medicine, generic

    # Try partial match - if the brand name appears in the raw string
    for brand, generic in MEDICINE_MAPPING.items():
        if brand.lower() in raw_medicine.lower():
            return raw_medicine, generic

    # No match
    return raw_medicine, raw_medicine


# ----- Main Standardization Function -----

def standardize_lab_report(lab_data, trace_id, document_id, meta):

    rows = []

    basic_info = lab_data.get("basic_info", {})
    report_details = lab_data.get("report_details", [])

    # normalize demographics
    patient_name = basic_info.get("patient_name", "")
    age_raw = basic_info.get("age", "")
    gender_raw = basic_info.get("gender", "")
    uhid = basic_info.get("uhid", "")
    lab_name = basic_info.get("lab_or_hospital_name", "")
    bill_date_raw = basic_info.get("bill_date", "")
    report_date_raw = basic_info.get("reports_date", "")

    age_years = normalize_age(age_raw)
    gender = normalize_gender(gender_raw)
    bill_date = normalize_date(bill_date_raw)
    report_date = normalize_date(report_date_raw)

    for test in report_details:
        raw_test_name = test.get("test_name", "")
        raw_result = test.get("result", "")
        raw_unit = test.get("unit", "")
        raw_range = test.get("range", "")
        raw_analytics = test.get("test_analytics", "")
        page_no = test.get("page_no", 0)

        # FR-2.1: Normalize test name
        canonical_name, norm_method, norm_confidence = normalize_test_name(raw_test_name)

        # FR-2.3: Convert result to numeric
        result_numeric, result_text = extract_numeric(raw_result)

        # FR-2.4: Normalize unit
        unit_canonical = normalize_unit(canonical_name, raw_unit)

        # Parse range
        range_low, range_high = parse_range(raw_range)

        row = {
            "trace_id": trace_id,
            "document_id": document_id,
            "record_type": "lab_report",
            "source_system": meta.get("source_system", ""),
            "claim_no": meta.get("claim_no", ""),
            "nt_code": meta.get("nt_code", ""),
            "consumer_client_id": meta.get("consumer_client_id", ""),
            "destination_identifier": meta.get("destination_identifier", ""),
            "patient_name": patient_name,
            "age": age_raw,
            "age_years": age_years,
            "gender": gender,
            "uhid": uhid,
            "hospital_name": lab_name,
            "bill_date": bill_date,
            "reports_date": report_date,
            "test_name_canonical": canonical_name,
            "test_name_original": raw_test_name,
            "result_value": result_numeric,
            "result_text": result_text,
            "unit_canonical": unit_canonical,
            "unit_original": raw_unit,
            "range_low": range_low,
            "range_high": range_high,
            "range_text": raw_range,
            "test_analytics": raw_analytics,
            "normalization_method": norm_method,
            "normalization_confidence": norm_confidence,
            "page_no": page_no,
        }
        rows.append(row)

    return rows


def standardize_discharge_summary(ds_data, trace_id, document_id, meta):
    rows = []

    patient_name = ds_data.get("patientName", "")
    age_raw = ds_data.get("age", "")
    gender_raw = ds_data.get("gender", "")
    doctor_name = ds_data.get("doctorName", "")
    hospital_name = ds_data.get("hospitalName", "")
    hospital_address = ds_data.get("hospitalAddress", "")
    ward = ds_data.get("ward", "")
    admission_raw = ds_data.get("admissionDate", "")
    discharge_raw = ds_data.get("dischargeDate", "")
    diagnosis = ds_data.get("diagnosis", "")
    brief_history = ds_data.get("briefHistory", "")
    general_exam = ds_data.get("generalExaminations", "")
    recommendations = ds_data.get("recommendations", "")
    post_discharge = ds_data.get("postDischargeAdvice", "")
    medications = ds_data.get("dischargeMedications", [])

    # normalize demographics
    age_years = normalize_age(age_raw)
    gender = normalize_gender(gender_raw)
    admission_date = normalize_date(admission_raw)
    discharge_date = normalize_date(discharge_raw)

    if not medications:
        # still create one row with the summary info
        medications = [{}]

    for med in medications:
        raw_medicine = med.get("medicine", "")
        dose = med.get("dose", "")
        frequency = med.get("frequency", "")
        med_type = med.get("type", "")

        # FR-2.6: Map medicine to generic
        brand_name, generic_name = normalize_medicine(raw_medicine)

        row = {
            "trace_id": trace_id,
            "document_id": document_id,
            "record_type": "discharge_summary",
            "source_system": meta.get("source_system", ""),
            "claim_no": meta.get("claim_no", ""),
            "nt_code": meta.get("nt_code", ""),
            "consumer_client_id": meta.get("consumer_client_id", ""),
            "destination_identifier": meta.get("destination_identifier", ""),
            "patient_name": patient_name,
            "age": age_raw,
            "age_years": age_years,
            "gender": gender,
            "doctor_name": doctor_name,
            "hospital_name": hospital_name,
            "hospital_address": hospital_address,
            "ward": ward,
            "admission_date": admission_date,
            "discharge_date": discharge_date,
            "diagnosis": diagnosis,
            "brief_history": brief_history,
            "general_examinations": general_exam,
            "recommendations": recommendations,
            "post_discharge_advice": post_discharge,
            "medicine": generic_name,
            "medicine_original": brand_name,
            "dose": dose,
            "frequency": frequency,
            "medicine_type": med_type,
        }
        rows.append(row)

    return rows


def parse_range(range_str):
    """
    Try to extract low and high from a range string like '4000-10000' or '< 50'.
    Returns (low, high) as floats or None if not parseable.
    """
    if not range_str:
        return None, None

    s = str(range_str).strip()

    # handle < X format (no lower bound, upper = X)
    match_lt = re.match(r'^[<≤]\s*(\d+\.?\d*)', s)
    if match_lt:
        return None, float(match_lt.group(1))

    # handle > X format (lower = X, no upper)
    match_gt = re.match(r'^[>≥]\s*(\d+\.?\d*)', s)
    if match_gt:
        return float(match_gt.group(1)), None

    # handle X-Y format
    match_range = re.match(r'^(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)', s)
    if match_range:
        return float(match_range.group(1)), float(match_range.group(2))

    # handle X - Y with spaces in different format
    parts = s.split("-")
    if len(parts) == 2:
        try:
            low = float(parts[0].strip().replace(",", ""))
            high = float(parts[1].strip().replace(",", ""))
            return low, high
        except ValueError:
            pass

    return None, None


def standardize_record(raw_record):
    all_rows = []

    trace_id = raw_record.get("traceId", "")
    data_block = raw_record.get("data", {})
    document_id = data_block.get("documentId", "")
    correlation_id = data_block.get("correlationId", "")

    # Extract metadata from metaDetails list
    meta = {}
    for item in data_block.get("metaDetails", []):
        key = item.get("key", "")
        value = item.get("value", "")
        # normalize key to something clean
        if key == "source_system":
            meta["source_system"] = value
        elif key == "claim_no":
            meta["claim_no"] = value
        elif key == "nt_code":
            meta["nt_code"] = value
        elif key == "ConsumerClientId":
            meta["consumer_client_id"] = value
        elif key == "DestinationIdentifier":
            meta["destination_identifier"] = value

    response_details = data_block.get("responseDetails", [])

    for section in response_details:
        classifier = section.get("classifier", "")
        section_data = section.get("data", {})
        section_status = section.get("status", "")

        if section_status != "success":
            logger.warning(f"Skipping section with status: {section_status}")
            continue

        if classifier == "lab_report":
            rows = standardize_lab_report(section_data, trace_id, document_id, meta)
            all_rows.extend(rows)
        elif classifier == "discharge_summary":
            rows = standardize_discharge_summary(section_data, trace_id, document_id, meta)
            all_rows.extend(rows)
        else:
            logger.info(f"Unknown classifier: {classifier}, skipping")

    return all_rows
