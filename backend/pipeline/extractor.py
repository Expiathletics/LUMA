# -*- coding: utf-8 -*-
"""
LUMA — Field Extractor
=======================
Takes raw text from OCR and classifies it into funeral home field types.
Uses pattern matching + spaCy NER to identify:
    - Person names (deceased, next of kin, parents)
    - Dates (DOB, DOD, service date)
    - Addresses
    - SSN (last 4 only — never store full SSN)
    - Disposition method
    - Military service indicators

This is Step 3 of the pipeline:
Upload → Ingest → OCR → [EXTRACT] → Normalize → Store
"""

import re
from typing import Optional


# ─────────────────────────────────────────────
# FUNERAL HOME FIELD DEFINITIONS
# Maps raw text patterns to our schema fields
# ─────────────────────────────────────────────

FIELD_PATTERNS = {
    # Deceased person fields
    "deceased_name": [
        r"(?i)(?:decedent|deceased|name of deceased)[:\s]+([A-Z][a-z]+ (?:[A-Z][a-z]+ )?[A-Z][a-z]+)",
        r"(?i)(?:last name|surname)[:\s]+([A-Z][a-z]+)",
    ],
    "date_of_birth": [
        r"(?i)(?:date of birth|dob|born)[:\s]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(?i)(?:date of birth|dob)[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
    ],
    "date_of_death": [
        r"(?i)(?:date of death|dod|died|death date)[:\s]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(?i)(?:date of death|dod)[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
    ],
    "ssn_last4": [
        r"(?i)(?:ssn|social security)[:\s#]*\d{3}[-\s]\d{2}[-\s](\d{4})",
        r"(?i)(?:last 4|last four)[:\s]+(\d{4})",
    ],
    "gender": [
        r"(?i)(?:sex|gender)[:\s]+(male|female|M|F)\b",
    ],
    "marital_status": [
        r"(?i)(?:marital status|marital)[:\s]+(single|married|widowed|divorced|separated)",
    ],
    "address": [
        r"(?i)(?:address|residence|home address)[:\s]+(\d+[^,\n]+(?:street|st|avenue|ave|road|rd|drive|dr|blvd|lane|ln|way|place|pl)[^,\n]*)",
    ],
    "city": [
        r"(?i)(?:city)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)",
    ],
    "state": [
        r"(?i)(?:state)[:\s]+([A-Z]{2}|California|CA)",
    ],
    "zip": [
        r"(?i)(?:zip|postal)[:\s]+(\d{5}(?:-\d{4})?)",
    ],
    "place_of_death": [
        r"(?i)(?:place of death|location of death|died at)[:\s]+([^\n,]+)",
    ],
    "next_of_kin_name": [
        r"(?i)(?:next of kin|informant|contact person|spouse)[:\s]+([A-Z][a-z]+ (?:[A-Z][a-z]+ )?[A-Z][a-z]+)",
    ],
    "next_of_kin_relationship": [
        r"(?i)(?:relationship|relation)[:\s]+(spouse|son|daughter|brother|sister|parent|mother|father|child|sibling|friend|other)",
    ],
    "disposition_method": [
        r"(?i)(?:disposition|method of disposition|type of service)[:\s]+(burial|cremation|entombment|donation|green burial)",
    ],
    "veteran_status": [
        r"(?i)(veteran|military|armed forces|army|navy|marines|air force|coast guard)",
    ],
    "military_branch": [
        r"(?i)(army|navy|marines|marine corps|air force|coast guard|national guard)",
    ],
    "religion": [
        r"(?i)(?:religion|faith|church)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
    ],
    "occupation": [
        r"(?i)(?:occupation|profession|employment)[:\s]+([^\n,]+)",
    ],
}


def extract_fields(raw_text: str, key_value_pairs: dict = None) -> dict:
    """
    Extract funeral home fields from raw text using pattern matching.
    
    Args:
        raw_text: Full text from OCR
        key_value_pairs: Pre-extracted key-value pairs from OCR (optional)
    
    Returns:
        dict of field_name → extracted_value
    """
    extracted = {}
    
    # Step 1: Try to match known key-value pairs first (highest confidence)
    if key_value_pairs:
        extracted.update(_match_from_kv_pairs(key_value_pairs))
    
    # Step 2: Pattern match against raw text for remaining fields
    for field_name, patterns in FIELD_PATTERNS.items():
        if field_name in extracted:
            continue  # Already found from KV pairs
        
        for pattern in patterns:
            match = re.search(pattern, raw_text)
            if match:
                value = match.group(1).strip()
                if value:
                    extracted[field_name] = value
                    break
    
    # Step 3: Try spaCy NER for person names and dates (if available)
    extracted.update(_spacy_extraction(raw_text, extracted))
    
    # Step 4: Handle veteran status (boolean)
    if "veteran_status" in extracted:
        extracted["veteran_status"] = True
    
    print(f"[EXTRACT] Found {len(extracted)} fields from document")
    return extracted


def _match_from_kv_pairs(kv_pairs: dict) -> dict:
    """
    Map extracted key-value pairs to our schema field names.
    Handles common label variations.
    """
    field_map = {
        # Direct matches
        "deceased_name": ["deceased_name", "name_of_deceased", "decedent_name", "name"],
        "date_of_birth": ["date_of_birth", "dob", "birth_date", "born"],
        "date_of_death": ["date_of_death", "dod", "death_date", "died"],
        "ssn_last4": ["ssn", "social_security", "ssn_last4"],
        "gender": ["sex", "gender"],
        "marital_status": ["marital_status", "marital"],
        "address": ["address", "home_address", "residence", "street_address"],
        "city": ["city", "city_of_residence"],
        "state": ["state"],
        "zip": ["zip", "zip_code", "postal_code"],
        "place_of_death": ["place_of_death", "location_of_death", "died_at"],
        "next_of_kin_name": ["next_of_kin", "informant", "spouse", "contact"],
        "next_of_kin_relationship": ["relationship", "relation"],
        "disposition_method": ["disposition", "type_of_service", "method"],
        "religion": ["religion", "faith", "church"],
        "occupation": ["occupation", "profession", "employer"],
        "cemetery_name": ["cemetery", "cemetery_name", "burial_location"],
        "military_branch": ["military_branch", "branch_of_service", "branch"],
    }
    
    extracted = {}
    normalized_kv = {k.lower().replace(" ", "_").replace("-", "_"): v 
                     for k, v in kv_pairs.items()}
    
    for our_field, possible_keys in field_map.items():
        for key in possible_keys:
            if key in normalized_kv:
                extracted[our_field] = normalized_kv[key]
                break
    
    return extracted


def _spacy_extraction(raw_text: str, existing: dict) -> dict:
    """
    Use spaCy Named Entity Recognition for additional field extraction.
    Fills in gaps that pattern matching missed.
    """
    additional = {}
    
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        doc = nlp(raw_text[:5000])  # Process first 5000 chars only
        
        persons_found = []
        dates_found = []
        places_found = []
        
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                persons_found.append(ent.text)
            elif ent.label_ == "DATE":
                dates_found.append(ent.text)
            elif ent.label_ in ["GPE", "LOC", "FAC"]:
                places_found.append(ent.text)
        
        # Fill in missing person fields
        if persons_found and "deceased_name" not in existing:
            additional["deceased_name"] = persons_found[0]
        if len(persons_found) > 1 and "next_of_kin_name" not in existing:
            additional["next_of_kin_name"] = persons_found[1]
        
        # Fill in missing date fields
        if dates_found and "date_of_death" not in existing:
            additional["date_of_death"] = dates_found[0]
        if len(dates_found) > 1 and "date_of_birth" not in existing:
            additional["date_of_birth"] = dates_found[1]
        
        # Fill in missing place
        if places_found and "place_of_death" not in existing:
            additional["place_of_death"] = places_found[0]
    
    except (ImportError, OSError):
        # spaCy not installed or model not downloaded
        pass
    
    return additional
