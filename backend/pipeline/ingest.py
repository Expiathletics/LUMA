# -*- coding: utf-8 -*-
"""
LUMA — Data Ingestion
=====================
Accepts uploaded documents (PDFs, scanned forms, CSV exports from CRMs)
and saves them locally for processing.

This is Step 1 of the pipeline:
Upload → [INGEST] → OCR → Extract → Normalize → Store
"""

import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_FORMATS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".csv", ".xlsx"}


def ingest_document(file_bytes: bytes, filename: str, customer_id: str) -> dict:
    """
    Save an uploaded document to the uploads directory.
    Returns metadata about the saved file.
    
    Args:
        file_bytes: Raw file content
        filename: Original filename from upload
        customer_id: Which funeral home this belongs to
    
    Returns:
        dict with doc_id, file_path, file_type, status
    """
    extension = Path(filename).suffix.lower()
    
    if extension not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported file type: {extension}. Supported: {SUPPORTED_FORMATS}")
    
    # Generate unique document ID
    doc_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create customer directory
    customer_dir = UPLOAD_DIR / customer_id
    customer_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file
    safe_filename = f"{timestamp}_{doc_id}{extension}"
    file_path = customer_dir / safe_filename
    
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    
    file_size = len(file_bytes)
    
    print(f"[INGEST] Saved {filename} → {file_path} ({file_size:,} bytes)")
    
    return {
        "doc_id": doc_id,
        "file_path": str(file_path),
        "original_filename": filename,
        "file_type": extension,
        "file_size": file_size,
        "customer_id": customer_id,
        "status": "ingested",
        "timestamp": timestamp
    }


def ingest_from_path(source_path: str, customer_id: str) -> dict:
    """
    Ingest a document that already exists on disk (e.g. bulk historical import).
    Copies it into the LUMA upload directory and returns metadata.
    """
    source = Path(source_path)
    
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    
    with open(source, "rb") as f:
        file_bytes = f.read()
    
    return ingest_document(file_bytes, source.name, customer_id)


def list_ingested(customer_id: str) -> list:
    """List all documents ingested for a customer."""
    customer_dir = UPLOAD_DIR / customer_id
    if not customer_dir.exists():
        return []
    
    files = []
    for f in customer_dir.iterdir():
        if f.suffix.lower() in SUPPORTED_FORMATS:
            files.append({
                "filename": f.name,
                "file_path": str(f),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
    
    return sorted(files, key=lambda x: x["modified"], reverse=True)
