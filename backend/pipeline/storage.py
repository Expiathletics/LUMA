# -*- coding: utf-8 -*-
"""
LUMA — Storage
==============
Saves normalized case data as JSON files locally.
SQLite for MVP — Supabase for production.

This is Step 5 of the pipeline:
Upload → Ingest → OCR → Extract → Normalize → [STORE]
"""

import json
import uuid
import sqlite3
import os
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(os.getenv("DATA_DIR", "./data/cases"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path("./data/luma.db")


def init_db():
    """Initialize SQLite database with cases table."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            fields TEXT NOT NULL,
            raw_doc_path TEXT,
            processing_status TEXT DEFAULT 'complete',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS training_records (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            input_features TEXT,
            correct_value TEXT,
            source TEXT DEFAULT 'historical',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_case(customer_id: str, normalized_fields: dict, raw_doc_path: str = None) -> str:
    """
    Save a processed case to the database.
    Returns the case_id.
    """
    init_db()
    
    case_id = str(uuid.uuid4())
    
    # Save to SQLite
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        INSERT INTO cases (id, customer_id, fields, raw_doc_path, processing_status, created_at)
        VALUES (?, ?, ?, ?, 'complete', ?)
    """, (
        case_id,
        customer_id,
        json.dumps(normalized_fields),
        raw_doc_path,
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    
    # Also save as JSON file for easy inspection
    json_path = DATA_DIR / f"{case_id}.json"
    with open(json_path, "w") as f:
        json.dump({
            "case_id": case_id,
            "customer_id": customer_id,
            "fields": normalized_fields,
            "raw_doc_path": raw_doc_path,
            "created_at": datetime.now().isoformat()
        }, f, indent=2)
    
    print(f"[STORE] Saved case {case_id} with {len(normalized_fields)} fields")
    
    # Also save as training record (each historical case = training data)
    _save_as_training_records(customer_id, normalized_fields)
    
    return case_id


def get_case(case_id: str) -> dict:
    """Retrieve a single case by ID."""
    init_db()
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "case_id": row["id"],
        "customer_id": row["customer_id"],
        "fields": json.loads(row["fields"]),
        "raw_doc_path": row["raw_doc_path"],
        "status": row["processing_status"],
        "created_at": row["created_at"]
    }


def get_all_cases(customer_id: str = None) -> list:
    """Retrieve all cases, optionally filtered by customer."""
    init_db()
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    if customer_id:
        rows = conn.execute(
            "SELECT * FROM cases WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM cases ORDER BY created_at DESC"
        ).fetchall()
    
    conn.close()
    
    return [{
        "case_id": row["id"],
        "customer_id": row["customer_id"],
        "fields": json.loads(row["fields"]),
        "field_count": len(json.loads(row["fields"])),
        "status": row["processing_status"],
        "created_at": row["created_at"]
    } for row in rows]


def get_training_data(customer_id: str, field_name: str = None) -> list:
    """Get training records for model training."""
    init_db()
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    if field_name:
        rows = conn.execute(
            "SELECT * FROM training_records WHERE customer_id = ? AND field_name = ?",
            (customer_id, field_name)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM training_records WHERE customer_id = ?",
            (customer_id,)
        ).fetchall()
    
    conn.close()
    
    return [{
        "id": row["id"],
        "field_name": row["field_name"],
        "input_features": json.loads(row["input_features"]) if row["input_features"] else {},
        "correct_value": row["correct_value"],
        "source": row["source"],
        "created_at": row["created_at"]
    } for row in rows]


def _save_as_training_records(customer_id: str, fields: dict):
    """
    Every completed historical case becomes training data.
    For each field, save what we knew (seed fields) → what the answer was.
    This is how the model learns from historical cases.
    """
    # Seed fields = what staff enters first (the inputs)
    seed_fields = ["deceased_name", "date_of_birth", "date_of_death",
                   "next_of_kin_name", "next_of_kin_relationship", "disposition_method"]
    
    seed_values = {k: v for k, v in fields.items() if k in seed_fields and v}
    
    # Predicted fields = everything else (the outputs the model learns)
    predicted_fields = {k: v for k, v in fields.items() if k not in seed_fields and v}
    
    conn = sqlite3.connect(str(DB_PATH))
    
    for field_name, correct_value in predicted_fields.items():
        record_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO training_records (id, customer_id, field_name, input_features, correct_value, source)
            VALUES (?, ?, ?, ?, ?, 'historical')
        """, (
            record_id,
            customer_id,
            field_name,
            json.dumps(seed_values),
            str(correct_value)
        ))
    
    conn.commit()
    conn.close()
