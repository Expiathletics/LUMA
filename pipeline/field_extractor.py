"""
LUMA Script 2 — Field Extractor
Reads OCR output and pulls structured fields using regex + spaCy NER.
SSNs are masked to last-4 immediately. Full SSN is NEVER stored.

Run: python -m luma.pipeline.field_extractor
"""

import re
import json
import os
import spacy
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Load spaCy model (run once: python -m spacy download en_core_web_sm)
nlp = spacy.load("en_core_web_sm")

# ── REGEX PATTERNS ────────────────────────────────────────────────────────────

DATE_PATTERN = (
    r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|'
    r'(?:January|February|March|April|May|June|July|August|September|'
    r'October|November|December)\s+\d{1,2},?\s+\d{4})\b'
)
SSN_PATTERN       = r'\b\d{3}-\d{2}-\d{4}\b'
PHONE_PATTERN     = r'\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}'
ZIP_PATTERN       = r'\b\d{5}(?:-\d{4})?\b'
SERVICE_PATTERN   = (r'\b(burial|cremation|direct cremation|graveside|'
                     r'memorial service|celebration of life|immediate burial)\b')
VETERAN_PATTERN   = r'\b(veteran|usmc|usaf|usn|usa|uscg|v\.a\.)\b'

# Keyword lists for context-aware extraction
DOD_KEYWORDS      = ["date of death", "died", "dod", "passed away", "death date", "date passed"]
DOB_KEYWORDS      = ["date of birth", "dob", "born", "birth date", "birthdate"]
SERVICE_DATE_KEYS = ["service date", "date of service", "funeral date", "memorial service date"]
BURIAL_KEYWORDS   = ["cemetery", "burial ground", "interment", "memorial park", "mausoleum"]


def mask_ssn(ssn: str) -> Optional[str]:
    """Mask SSN to last-4 IMMEDIATELY after extraction. NEVER store full SSN."""
    if not ssn:
        return None
    digits = re.sub(r'\D', '', ssn)
    if len(digits) == 9:
        return f"XXX-XX-{digits[-4:]}"
    return None


def find_near_keyword(text: str, keywords: list, pattern: str, window: int = 80) -> Optional[str]:
    """Find a keyword in text, then look for pattern within window chars after it."""
    text_lower = text.lower()
    for kw in keywords:
        idx = text_lower.find(kw)
        if idx != -1:
            zone = text[idx: idx + window + len(kw)]
            m = re.search(pattern, zone, re.IGNORECASE)
            if m:
                return m.group(0).strip()
    return None


def normalize_date(raw: str) -> Optional[str]:
    """Convert any common date format to ISO 8601 (YYYY-MM-DD)."""
    if not raw:
        return None
    for fmt in [
        "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y",
        "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y",
    ]:
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw  # Return as-is if unparseable


def extract_all_fields(raw_text: str) -> dict:
    """
    Master extraction function.
    Input:  raw OCR text string
    Output: structured dict with all extracted fields
    """
    result = {}

    # ── DATES ──────────────────────────────────────────────────────────────
    result["date_of_death"] = normalize_date(
        find_near_keyword(raw_text, DOD_KEYWORDS, DATE_PATTERN)
    )
    result["date_of_birth"] = normalize_date(
        find_near_keyword(raw_text, DOB_KEYWORDS, DATE_PATTERN)
    )
    result["service_date"] = normalize_date(
        find_near_keyword(raw_text, SERVICE_DATE_KEYS, DATE_PATTERN)
    )

    # ── COMPUTED FIELDS ──────────────────────────────────────────────────────
    if result["date_of_death"] and result["date_of_birth"]:
        try:
            dod = datetime.strptime(result["date_of_death"], "%Y-%m-%d")
            dob = datetime.strptime(result["date_of_birth"], "%Y-%m-%d")
            result["age_at_death"] = (dod - dob).days // 365
        except Exception:
            result["age_at_death"] = None
    else:
        result["age_at_death"] = None

    # ── SSN — EXTRACT AND IMMEDIATELY MASK ──────────────────────────────────
    # Full SSN NEVER written to disk or database. Last-4 only.
    ssn_match = re.search(SSN_PATTERN, raw_text)
    result["ssn_last4"] = mask_ssn(ssn_match.group(0) if ssn_match else None)

    # ── SERVICE TYPE ─────────────────────────────────────────────────────────
    svc_match = re.search(SERVICE_PATTERN, raw_text, re.IGNORECASE)
    result["service_type"] = svc_match.group(0).title() if svc_match else None

    # ── VETERAN ──────────────────────────────────────────────────────────────
    vet_match = re.search(VETERAN_PATTERN, raw_text, re.IGNORECASE)
    result["is_veteran"] = bool(vet_match)
    result["veteran_branch"] = vet_match.group(0).upper() if vet_match else None

    # ── NAMES + LOCATIONS via spaCy NER ─────────────────────────────────────
    doc = nlp(raw_text[:5000])  # Limit for speed
    persons   = [e.text for e in doc.ents if e.label_ == "PERSON"]
    locations = [e.text for e in doc.ents if e.label_ in ("LOC", "GPE", "FAC")]

    result["deceased_name"]    = persons[0] if persons else None
    result["next_of_kin_name"] = persons[1] if len(persons) > 1 else None
    result["place_of_death"]   = locations[0] if locations else None

    # ── BURIAL LOCATION ──────────────────────────────────────────────────────
    result["burial_location"] = find_near_keyword(
        raw_text, BURIAL_KEYWORDS, r'[A-Z][a-z]+(?: [A-Z][a-z]+)*'
    )

    # ── PHONES ───────────────────────────────────────────────────────────────
    phones = re.findall(PHONE_PATTERN, raw_text)
    result["primary_phone"]   = phones[0] if phones else None
    result["secondary_phone"] = phones[1] if len(phones) > 1 else None

    # ── ZIP ──────────────────────────────────────────────────────────────────
    zip_match = re.search(ZIP_PATTERN, raw_text)
    result["zip_code"] = zip_match.group(0) if zip_match else None

    # ── CONFIDENCE SCORE ─────────────────────────────────────────────────────
    critical = ["deceased_name", "date_of_death", "date_of_birth", "service_type", "ssn_last4"]
    optional = ["burial_location", "next_of_kin_name", "primary_phone", "service_date", "place_of_death"]
    c_score  = sum(1 for f in critical if result.get(f)) / len(critical)
    o_score  = sum(1 for f in optional if result.get(f)) / len(optional)
    result["_confidence"]     = round(c_score * 0.7 + o_score * 0.3, 3)
    result["_raw_preview"]    = raw_text[:300]
    result["_needs_review"]   = result["_confidence"] < 0.60

    return result


if __name__ == "__main__":
    with open("./luma/data/ocr_output.json") as f:
        ocr_results = json.load(f)

    structured = []
    needs_review = []

    for case in ocr_results:
        if "error" in case:
            continue
        fields = extract_all_fields(case["raw_text"])
        fields["case_id"] = case["case_id"]
        fields["s3_key"]  = case["s3_key"]
        structured.append(fields)
        if fields["_needs_review"]:
            needs_review.append(case["case_id"])

    output_path = "./luma/data/structured_cases.json"
    with open(output_path, "w") as f:
        json.dump(structured, f, indent=2)

    print(f"\n✅ Extraction complete: {len(structured)} cases")
    print(f"⚠️  Needs manual review (confidence < 0.60): {len(needs_review)} cases")
    if needs_review:
        print(f"   Cases: {needs_review}")
    print(f"Saved to: {output_path}")
