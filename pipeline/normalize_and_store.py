"""
LUMA Script 3 — Normalize and Store
Cleans extracted data and bulk-inserts into PostgreSQL via Supabase.
Uses Alembic migrations — do NOT create tables here.

Run: python -m luma.pipeline.normalize_and_store
"""

import json
import re
import os
import time
import psycopg2
from psycopg2.extras import execute_values
from psycopg2 import pool, OperationalError
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

# Connection pool for reliability
connection_pool = None

def get_connection_pool():
    global connection_pool
    if connection_pool is None:
        connection_pool = pool.SimpleConnectionPool(1, 10, DB_URL)
    return connection_pool

def get_connection():
    for attempt in range(3):
        try:
            return get_connection_pool().getconn()
        except OperationalError:
            time.sleep(1)
    raise RuntimeError("Cannot connect to database after 3 attempts")

def release_connection(conn):
    get_connection_pool().putconn(conn)


# ── NORMALIZATION FUNCTIONS ───────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    if not name:
        return None
    return name.title().strip() if name.isupper() else name.strip()

def normalize_phone(phone: str) -> str:
    if not phone:
        return None
    d = re.sub(r'\D', '', phone)
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else phone

SERVICE_MAP = {
    "burial":           "Burial",
    "graveside":        "Burial",
    "immediate burial": "Burial",
    "cremation":        "Cremation",
    "direct cremation": "Direct Cremation",
    "memorial service": "Memorial Service",
    "celebration of life": "Celebration of Life",
}

def normalize_service_type(svc: str) -> str:
    if not svc:
        return None
    for k, v in SERVICE_MAP.items():
        if k in svc.lower():
            return v
    return svc.title()

def normalize_case(raw: dict, customer_id: str) -> dict:
    """Apply all normalizations to a single extracted case."""
    return {
        "case_id":               raw.get("case_id"),
        "customer_id":           customer_id,
        "s3_key":                raw.get("s3_key"),
        "deceased_name":         normalize_name(raw.get("deceased_name")),
        "date_of_death":         raw.get("date_of_death"),
        "date_of_birth":         raw.get("date_of_birth"),
        "age_at_death":          raw.get("age_at_death"),
        "ssn_last4":             raw.get("ssn_last4"),     # Last-4 only — NEVER full SSN
        "service_type":          normalize_service_type(raw.get("service_type")),
        "is_veteran":            bool(raw.get("is_veteran", False)),
        "veteran_branch":        raw.get("veteran_branch"),
        "next_of_kin_name":      normalize_name(raw.get("next_of_kin_name")),
        "primary_phone":         normalize_phone(raw.get("primary_phone")),
        "secondary_phone":       normalize_phone(raw.get("secondary_phone")),
        "place_of_death":        raw.get("place_of_death"),
        "burial_location":       raw.get("burial_location"),
        "service_date":          raw.get("service_date"),
        "zip_code":              raw.get("zip_code"),
        "extraction_confidence": raw.get("_confidence", 0.0),
        "needs_review":          raw.get("_needs_review", False),
        "is_training_data":      True,
        "created_at":            datetime.utcnow().isoformat(),
    }


# ── DATABASE ──────────────────────────────────────────────────────────────────

def upload_to_db(cases: list):
    """
    Bulk insert normalized cases into PostgreSQL.
    Uses ON CONFLICT (case_id) to be idempotent — safe to re-run.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cols = list(cases[0].keys())
        rows = [tuple(c.get(col) for col in cols) for c in cases]

        execute_values(
            cur,
            f"""
            INSERT INTO training_cases ({', '.join(cols)})
            VALUES %s
            ON CONFLICT (case_id) DO UPDATE SET
                extraction_confidence = EXCLUDED.extraction_confidence,
                needs_review          = EXCLUDED.needs_review,
                service_type          = EXCLUDED.service_type
            """,
            rows,
        )
        conn.commit()
        cur.close()
        print(f"✅ Inserted/updated {len(rows)} cases in training_cases")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        release_connection(conn)


def print_quality_report(cases: list):
    n = len(cases)
    if n == 0:
        print("No cases to report.")
        return
    def pct(field):
        return sum(1 for c in cases if c.get(field)) / n * 100
    avg_conf = sum(c.get("extraction_confidence", 0) for c in cases) / n
    print(f"""
╔══════════════════════════════════════╗
║       DATA QUALITY REPORT           ║
╠══════════════════════════════════════╣
║  Total cases:          {n:>4}          ║
║  Has deceased name:    {pct('deceased_name'):>5.1f}%        ║
║  Has date of death:    {pct('date_of_death'):>5.1f}%        ║
║  Has date of birth:    {pct('date_of_birth'):>5.1f}%        ║
║  Has service type:     {pct('service_type'):>5.1f}%        ║
║  Needs manual review:  {sum(1 for c in cases if c.get('needs_review')):>4}          ║
║  Avg confidence score: {avg_conf:.3f}          ║
╚══════════════════════════════════════╝
""")


if __name__ == "__main__":
    customer_id = "funeral_home_001"

    with open("./luma/data/structured_cases.json") as f:
        raw_cases = json.load(f)

    normalized = [normalize_case(c, customer_id) for c in raw_cases]

    print_quality_report(normalized)
    upload_to_db(normalized)

    # Save local backup
    backup_path = "./luma/data/normalized_cases.json"
    with open(backup_path, "w") as f:
        json.dump(normalized, f, indent=2, default=str)
    print(f"Local backup saved: {backup_path}")
