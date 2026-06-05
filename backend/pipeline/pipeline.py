# -*- coding: utf-8 -*-
"""
LUMA — Master Pipeline Orchestrator
=====================================
Runs the complete flow for a single document:

    Upload → Ingest → OCR → Extract → Normalize → Store

This is the single function you call to process any document.
Everything else is a detail.
"""

from .ingest import ingest_document
from .ocr import extract_text_from_document
from .extractor import extract_fields
from .normalizer import normalize_all_fields
from .storage import save_case


def process_document(file_bytes: bytes, filename: str, customer_id: str) -> dict:
    """
    Full pipeline: raw file → structured, normalized, stored case record.
    
    Args:
        file_bytes: Raw uploaded file content
        filename: Original filename
        customer_id: Which funeral home this case belongs to
    
    Returns:
        dict with case_id, fields, field_count, status
    """
    print(f"\n[PIPELINE] Processing {filename} for customer {customer_id}")
    print("─" * 50)
    
    try:
        # STEP 1: INGEST — Save the raw file
        doc_metadata = ingest_document(file_bytes, filename, customer_id)
        file_path = doc_metadata["file_path"]
        
        # STEP 2: OCR — Extract text from the document
        ocr_result = extract_text_from_document(file_path)
        raw_text = ocr_result["raw_text"]
        key_value_pairs = ocr_result["key_value_pairs"]
        
        if not raw_text:
            return {
                "case_id": None,
                "status": "error",
                "error": "Could not extract text from document",
                "filename": filename
            }
        
        # STEP 3: EXTRACT — Identify funeral home fields
        extracted = extract_fields(raw_text, key_value_pairs)
        
        if not extracted:
            return {
                "case_id": None,
                "status": "error",
                "error": "Could not identify any fields in document",
                "filename": filename,
                "raw_text_preview": raw_text[:200]
            }
        
        # STEP 4: NORMALIZE — Standardize all field values
        normalized = normalize_all_fields(extracted)
        
        # STEP 5: STORE — Save to database and training records
        case_id = save_case(customer_id, normalized, file_path)
        
        print(f"[PIPELINE] ✅ Complete — Case {case_id} | {len(normalized)} fields extracted")
        print("─" * 50)
        
        return {
            "case_id": case_id,
            "customer_id": customer_id,
            "fields": normalized,
            "field_count": len(normalized),
            "filename": filename,
            "status": "complete"
        }
    
    except Exception as e:
        print(f"[PIPELINE] ❌ Error processing {filename}: {e}")
        return {
            "case_id": None,
            "status": "error",
            "error": str(e),
            "filename": filename
        }


def process_directory(directory_path: str, customer_id: str) -> list:
    """
    Batch process all documents in a directory.
    Used for historical case import (bulk ingestion of years of records).
    
    Returns list of results for each file.
    """
    from pathlib import Path
    
    directory = Path(directory_path)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")
    
    supported = {".pdf", ".png", ".jpg", ".jpeg", ".tiff"}
    files = [f for f in directory.iterdir() if f.suffix.lower() in supported]
    
    print(f"\n[PIPELINE] Batch processing {len(files)} files from {directory_path}")
    
    results = []
    for i, file_path in enumerate(files, 1):
        print(f"\n[PIPELINE] File {i}/{len(files)}: {file_path.name}")
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        result = process_document(file_bytes, file_path.name, customer_id)
        results.append(result)
    
    successful = sum(1 for r in results if r["status"] == "complete")
    print(f"\n[PIPELINE] Batch complete: {successful}/{len(files)} files processed successfully")
    
    return results
