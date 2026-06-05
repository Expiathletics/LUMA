# -*- coding: utf-8 -*-
"""
LUMA — Field Normalizer
========================
Standardizes extracted field values into consistent formats.
This is critical for training — "March 15" and "03/15" must become
the same value so the model can learn from both.

This is Step 4 of the pipeline:
Upload → Ingest → OCR → Extract → [NORMALIZE] → Store
"""

import re
from datetime import datetime
from typing import Optional


# ─────────────────────────────────────────────
# DATE NORMALIZATION
# All dates → YYYY-MM-DD
# ─────────────────────────────────────────────

DATE_FORMATS = [
    "%m/%d/%Y",   # 03/15/1942
    "%m-%d-%Y",   # 03-15-1942
    "%m/%d/%y",   # 03/15/42
    "%B %d, %Y",  # March 15, 1942
    "%B %d %Y",   # March 15 1942
    "%b %d, %Y",  # Mar 15, 1942
    "%b %d %Y",   # Mar 15 1942
    "%d %B %Y",   # 15 March 1942
    "%Y-%m-%d",   # 1942-03-15 (already normalized)
]


def normalize_date(raw_date: str) -> Optional[str]:
    """Convert any date format to YYYY-MM-DD."""
    if not raw_date:
        return None
    
    raw_date = raw_date.strip()
    
    # Remove extra whitespace
    raw_date = " ".join(raw_date.split())
    
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(raw_date, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If nothing worked, return as-is (will be flagged as low confidence)
    return raw_date


def normalize_name(raw_name: str) -> Optional[str]:
    """
    Standardize names to Title Case.
    JOHN SMITH → John Smith
    smith, john → John Smith
    """
    if not raw_name:
        return None
    
    raw_name = raw_name.strip()
    
    # Handle "Last, First" format
    if "," in raw_name:
        parts = raw_name.split(",", 1)
        raw_name = f"{parts[1].strip()} {parts[0].strip()}"
    
    # Remove extra whitespace
    raw_name = " ".join(raw_name.split())
    
    # Convert to title case
    # Handle special cases like "McDonald", "O'Brien"
    words = raw_name.split()
    normalized = []
    for word in words:
        if word.upper() == word or word.lower() == word:
            normalized.append(word.title())
        else:
            normalized.append(word)  # Keep mixed case as-is (like McDonald)
    
    return " ".join(normalized)


def normalize_phone(raw_phone: str) -> Optional[str]:
    """Standardize phone numbers to (XXX) XXX-XXXX."""
    if not raw_phone:
        return None
    
    # Extract digits only
    digits = re.sub(r"\D", "", raw_phone)
    
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == "1":
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    
    return raw_phone  # Return as-is if can't parse


def normalize_zip(raw_zip: str) -> Optional[str]:
    """Standardize ZIP codes."""
    if not raw_zip:
        return None
    
    digits = re.sub(r"\D", "", raw_zip)
    
    if len(digits) == 5:
        return digits
    elif len(digits) == 9:
        return f"{digits[:5]}-{digits[5:]}"
    
    return raw_zip


def normalize_state(raw_state: str) -> Optional[str]:
    """Convert full state names to 2-letter abbreviations."""
    if not raw_state:
        return None
    
    state_map = {
        "california": "CA", "texas": "TX", "florida": "FL",
        "new york": "NY", "arizona": "AZ", "nevada": "NV",
        "oregon": "OR", "washington": "WA", "colorado": "CO",
    }
    
    cleaned = raw_state.strip().lower()
    return state_map.get(cleaned, raw_state.strip().upper()[:2])


def normalize_disposition(raw: str) -> Optional[str]:
    """Standardize disposition method."""
    if not raw:
        return None
    
    cleaned = raw.strip().lower()
    
    if any(w in cleaned for w in ["burial", "buried", "interment"]):
        return "burial"
    elif any(w in cleaned for w in ["cremation", "cremated", "cremate"]):
        return "cremation"
    elif any(w in cleaned for w in ["entombment", "entombed", "mausoleum"]):
        return "entombment"
    elif any(w in cleaned for w in ["donation", "donate", "anatomical"]):
        return "donation"
    
    return cleaned


def normalize_ssn_last4(raw: str) -> Optional[str]:
    """Extract just the last 4 digits of an SSN."""
    if not raw:
        return None
    
    digits = re.sub(r"\D", "", raw)
    
    if len(digits) >= 4:
        return digits[-4:]
    
    return None


# ─────────────────────────────────────────────
# MASTER NORMALIZER
# ─────────────────────────────────────────────

FIELD_NORMALIZERS = {
    "date_of_birth": normalize_date,
    "date_of_death": normalize_date,
    "service_date": normalize_date,
    "deceased_name": normalize_name,
    "next_of_kin_name": normalize_name,
    "father_name": normalize_name,
    "mother_maiden_name": normalize_name,
    "next_of_kin_phone": normalize_phone,
    "zip": normalize_zip,
    "state": normalize_state,
    "disposition_method": normalize_disposition,
    "ssn_last4": normalize_ssn_last4,
}


def normalize_all_fields(extracted: dict) -> dict:
    """
    Apply appropriate normalization to every extracted field.
    Fields without a specific normalizer pass through as-is (stripped).
    """
    normalized = {}
    
    for field, value in extracted.items():
        if value is None:
            continue
        
        normalizer = FIELD_NORMALIZERS.get(field)
        
        if normalizer:
            normalized_value = normalizer(str(value))
        else:
            # Default: strip whitespace
            normalized_value = str(value).strip() if value else None
        
        if normalized_value:
            normalized[field] = normalized_value
    
    print(f"[NORMALIZE] Normalized {len(normalized)} fields")
    return normalized
