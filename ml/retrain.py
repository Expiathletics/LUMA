"""
LUMA Script 7 — Nightly Retrain
Runs as a cron job at 2 AM. Pulls corrections since last run,
retrains affected models, swaps artifacts, logs accuracy change.

This script CLOSES THE LOOP — without it, LUMA is a one-shot system.

Cron setup (add to crontab -e):
    0 2 * * * cd /path/to/project && .venv/bin/python -m luma.ml.retrain >> logs/retrain.log 2>&1

Run manually: python -m luma.ml.retrain
"""

import os
import pickle
import json
import psycopg2
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Import from train_model — reuse all training logic
from luma.ml.train_model import (
    load_training_data,
    engineer_features,
    train_one_field,
    SEED_FEATURES,
    STAGE_2_FEATURES,
    STAGE_1_TARGETS,
)

load_dotenv()
DB_URL    = os.getenv("DATABASE_URL")
MODEL_DIR = "./luma/models"
LOG_DIR   = "./luma/models/retrain_logs"
os.makedirs(LOG_DIR, exist_ok=True)


def get_fields_with_new_corrections() -> list:
    """Which fields have unprocessed corrections since last retrain?"""
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT field_name
        FROM corrections
        WHERE retrained = FALSE
    """)
    fields = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return fields


def mark_corrections_retrained(fields: list):
    """Mark corrections as processed so they aren't re-picked up."""
    if not fields:
        return
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()
    cur.execute("""
        UPDATE corrections
        SET retrained = TRUE, retrained_at = %s
        WHERE field_name = ANY(%s) AND retrained = FALSE
    """, (datetime.utcnow(), fields))
    conn.commit()
    cur.close()
    conn.close()


def backup_model(field: str):
    """Keep previous model version before overwriting (enables rollback)."""
    registry_path = f"{MODEL_DIR}/model_registry.json"
    if not os.path.exists(registry_path):
        return
    with open(registry_path) as f:
        registry = json.load(f)
    current_path = registry.get(field, {}).get("active_path")
    if current_path and os.path.exists(current_path):
        backup_path = current_path.replace(".pkl", "_prev.pkl")
        os.replace(current_path, backup_path)
        print(f"  Backup: {backup_path}")


def run_retrain():
    print(f"\n{'='*60}")
    print(f"LUMA NIGHTLY RETRAIN — {datetime.utcnow().isoformat()}")
    print(f"{'='*60}")

    fields_to_retrain = get_fields_with_new_corrections()

    if not fields_to_retrain:
        print("✅ No new corrections — nothing to retrain.")
        return

    print(f"Fields with new corrections: {fields_to_retrain}")

    # Load full training data (includes corrected rows)
    df = load_training_data()
    df, _ = engineer_features(df)

    registry_path = f"{MODEL_DIR}/model_registry.json"
    existing_registry = {}
    if os.path.exists(registry_path):
        with open(registry_path) as f:
            existing_registry = json.load(f)

    retrain_log = {
        "timestamp":        datetime.utcnow().isoformat(),
        "fields_retrained": [],
        "results":          {},
    }

    for field in fields_to_retrain:
        print(f"\n--- Retraining: {field} ---")
        is_binary  = (df[field].nunique() <= 2) if field in df.columns else False
        stage      = 1 if field in STAGE_1_TARGETS else 2
        features   = SEED_FEATURES if stage == 1 else STAGE_2_FEATURES

        result = train_one_field(df, field, features, stage=stage)
        if result is None:
            print(f"  Skipped — insufficient data")
            continue

        old_accuracy = existing_registry.get(field, {}).get("cv_mean")

        # Backup then save new model
        backup_model(field)
        from luma.ml.train_model import save_models
        # Save just this one field
        partial = {field: result}
        partial_registry = save_models(partial)

        delta = (result["cv_mean"] - old_accuracy) if old_accuracy else None
        delta_str = f"Δ {delta:+.1%}" if delta is not None else "first train"
        print(f"  ✅ {field}: {result['cv_mean']:.1%} ({delta_str})")

        retrain_log["fields_retrained"].append(field)
        retrain_log["results"][field] = {
            "new_accuracy": result["cv_mean"],
            "old_accuracy": old_accuracy,
            "delta":        delta,
        }

    # Mark corrections as processed
    mark_corrections_retrained(fields_to_retrain)

    # Write retrain log
    log_path = f"{LOG_DIR}/retrain_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.json"
    with open(log_path, "w") as f:
        json.dump(retrain_log, f, indent=2)

    print(f"\n✅ Retrain complete: {len(retrain_log['fields_retrained'])} models updated")
    print(f"Log saved: {log_path}")


if __name__ == "__main__":
    run_retrain()
