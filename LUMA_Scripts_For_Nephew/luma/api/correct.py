"""
LUMA Script 6 — Correction Endpoint
Staff submits corrections → written to DB → flagged for nightly retrain.
This is the LEARNING HALF of the loop. Without this, LUMA never improves.

Mount on the main app in predict.py:
    from luma.api.correct import router as corrections_router
    app.include_router(corrections_router)
"""

import os
import psycopg2
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

router = APIRouter()


class CorrectionRequest(BaseModel):
    case_id:              str
    field_name:           str
    predicted_value:      Any
    corrected_value:      Any
    predicted_confidence: float


@router.post("/correct")
def submit_correction(
    req: CorrectionRequest,
    token: dict = Depends(lambda: None),  # Replace with verify_token from predict.py
):
    """
    Staff submits a correction after reviewing a prediction.
    Writes to corrections table and updates training_cases with the correct value.
    The nightly retrain (Script 7) picks up all unprocessed corrections.
    """
    # NOTE: In production, inject verify_token from predict.py here.
    # from luma.api.predict import verify_token
    # token: dict = Depends(verify_token)
    customer_id = "demo"  # Replace with: token["customer_id"]

    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    try:
        # Write correction to corrections table
        cur.execute("""
            INSERT INTO corrections (
                case_id, customer_id, field_name,
                predicted_value, corrected_value,
                predicted_confidence, corrected_at, retrained
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            req.case_id, customer_id, req.field_name,
            str(req.predicted_value), str(req.corrected_value),
            req.predicted_confidence, datetime.utcnow(), False
        ))

        # Also update training_cases so future training uses the correct value
        allowed_fields = [
            "service_type", "is_veteran", "burial_location",
            "age_at_death", "veteran_branch"
        ]
        if req.field_name in allowed_fields:
            cur.execute(f"""
                UPDATE training_cases
                SET {req.field_name} = %s,
                    last_corrected_at = %s
                WHERE case_id = %s AND customer_id = %s
            """, (req.corrected_value, datetime.utcnow(), req.case_id, customer_id))

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    return {
        "status":       "correction recorded",
        "case_id":      req.case_id,
        "field":        req.field_name,
        "will_retrain": True,
        "message":      "Nightly retrain will process this correction automatically.",
    }


@router.get("/corrections/stats")
def correction_stats():
    """How many unprocessed corrections are pending the next retrain."""
    customer_id = "demo"  # Replace with token["customer_id"] in production
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()
    cur.execute("""
        SELECT field_name, COUNT(*) as count
        FROM corrections
        WHERE customer_id = %s AND retrained = FALSE
        GROUP BY field_name
        ORDER BY count DESC
    """, (customer_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"pending_corrections": [{"field": r[0], "count": r[1]} for r in rows]}
