# -*- coding: utf-8 -*-
"""
LUMA — FastAPI Routes
======================
REST API endpoints for the LUMA platform.

Endpoints:
    POST /api/ingest      — Upload a document, run pipeline, return case
    GET  /api/cases       — List all cases (optionally filter by customer)
    GET  /api/cases/{id}  — Get a single case with all fields
    GET  /api/stats       — Dashboard stats (total cases, field accuracy, etc.)
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
import sys
import os

# Add parent to path so we can import pipeline
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.pipeline import process_document
from pipeline.storage import get_case, get_all_cases, get_training_data

router = APIRouter(prefix="/api", tags=["LUMA"])


@router.post("/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    customer_id: str = Query(..., description="Funeral home customer ID")
):
    """
    Upload a document and run it through the full LUMA pipeline.
    
    - Accepts: PDF, PNG, JPG, TIFF, CSV
    - Runs: Ingest → OCR → Extract → Normalize → Store
    - Returns: case_id + all extracted fields
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Read file bytes
    file_bytes = await file.read()
    
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    
    if len(file_bytes) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")
    
    # Run pipeline
    result = process_document(file_bytes, file.filename, customer_id)
    
    if result["status"] == "error":
        raise HTTPException(status_code=422, detail=result.get("error", "Processing failed"))
    
    return JSONResponse(content=result, status_code=201)


@router.get("/cases")
async def list_cases(
    customer_id: Optional[str] = Query(None, description="Filter by funeral home")
):
    """
    List all processed cases.
    Returns summary info including field count and status.
    """
    cases = get_all_cases(customer_id)
    
    return {
        "total": len(cases),
        "customer_id": customer_id,
        "cases": cases
    }


@router.get("/cases/{case_id}")
async def get_single_case(case_id: str):
    """
    Get a single case with all extracted fields.
    This is what you'd use to populate a form.
    """
    case = get_case(case_id)
    
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    
    return case


@router.get("/stats")
async def get_stats(
    customer_id: Optional[str] = Query(None)
):
    """
    Dashboard statistics.
    """
    cases = get_all_cases(customer_id)
    
    if not cases:
        return {
            "total_cases": 0,
            "avg_fields_per_case": 0,
            "training_records": 0
        }
    
    total_fields = sum(c["field_count"] for c in cases)
    avg_fields = total_fields / len(cases) if cases else 0
    
    # Count training records
    training = get_training_data(customer_id or "all") if customer_id else []
    
    return {
        "total_cases": len(cases),
        "avg_fields_per_case": round(avg_fields, 1),
        "training_records": len(training),
        "customer_id": customer_id
    }


@router.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "LUMA API", "version": "0.1.0"}
