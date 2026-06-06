"""
LUMA Script 4 — Train Model
Pulls training data from PostgreSQL, engineers features, trains calibrated
XGBoost models using a two-stage prediction chain (no circular features),
evaluates with 5-fold cross-validation, saves model artifacts.

Run: python -m luma.ml.train_model
"""

import os
import json
import pickle
import hashlib
import numpy as np
import pandas as pd
import psycopg2
from datetime import datetime
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
from dotenv import load_dotenv

load_dotenv()
DB_URL     = os.getenv("DATABASE_URL")
MODEL_DIR  = "./luma/models"
os.makedirs(MODEL_DIR, exist_ok=True)

# ── STAGE DEFINITIONS ─────────────────────────────────────────────────────────
# Stage 1: predict using SEED FEATURES ONLY (no circular references)
# Stage 2: predict using seed features + Stage 1 predictions as input

SEED_FEATURES = [
    "dod_month",      # Engineered from date_of_death
    "dod_year",
    "dod_dow",        # Day of week
    "zip_region",     # First 3 digits of zip_code
    "age_at_death",
]

STAGE_1_TARGETS = [
    "service_type",   # Predict from seeds only
    "is_veteran",     # Predict from seeds only
]

STAGE_2_FEATURES = SEED_FEATURES + [
    "service_type_encoded",   # Output from Stage 1
    "is_veteran_int",          # Output from Stage 1
]

STAGE_2_TARGETS = [
    "burial_location_bucket",  # Predict using seed + Stage 1 outputs
]


# ── DATA LOADING ──────────────────────────────────────────────────────────────

def load_training_data() -> pd.DataFrame:
    conn = psycopg2.connect(DB_URL)
    df = pd.read_sql("""
        SELECT *
        FROM training_cases
        WHERE is_training_data = TRUE
          AND extraction_confidence >= 0.60
          AND needs_review = FALSE
    """, conn)
    conn.close()
    print(f"Loaded {len(df)} training cases")
    return df


def engineer_features(df: pd.DataFrame):
    """Create derived features. Returns (df, label_encoder_for_service_type)."""
    df = df.copy()
    df["date_of_death"] = pd.to_datetime(df["date_of_death"], errors="coerce")
    df["dod_month"] = df["date_of_death"].dt.month.fillna(-1).astype(int)
    df["dod_year"]  = df["date_of_death"].dt.year.fillna(-1).astype(int)
    df["dod_dow"]   = df["date_of_death"].dt.dayofweek.fillna(-1).astype(int)
    df["zip_region"] = df["zip_code"].str[:3].apply(
        lambda x: int(x) if pd.notna(x) and str(x).isdigit() else -1
    )
    df["age_at_death"] = df["age_at_death"].fillna(-1).astype(int)
    df["is_veteran_int"] = df["is_veteran"].fillna(False).astype(int)

    # Pre-encode service_type so Stage 2 can use it as a numeric feature
    le = LabelEncoder()
    df["service_type_encoded"] = le.fit_transform(
        df["service_type"].fillna("Unknown")
    )
    return df, le


# ── MODEL TRAINING ────────────────────────────────────────────────────────────

def train_one_field(df: pd.DataFrame, target: str, features: list, stage: int) -> dict:
    """
    Train a calibrated XGBoost model for one target field.
    Uses 5-fold stratified CV — no single misleading split.
    Applies Platt scaling so confidence scores are real probabilities.
    """
    df_clean = df.dropna(subset=[target])
    n = len(df_clean)

    if n < 50:
        print(f"  ⚠️  {target}: only {n} samples (need ≥50) — skipping")
        return None

    X = df_clean[features].fillna(-1)
    y = df_clean[target]

    le_target = None
    if y.dtype == object or y.dtype.name == "category":
        le_target = LabelEncoder()
        y = le_target.fit_transform(y.fillna("Unknown"))
    else:
        y = y.astype(int)

    # Handle class imbalance (e.g. is_veteran ~10% positive)
    scale_pos_weight = 1.0
    n_classes = len(np.unique(y))
    if n_classes == 2:
        n_neg = (y == 0).sum()
        n_pos = (y == 1).sum()
        scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0
        print(f"  Class balance: {n_pos} pos / {n_neg} neg → scale_pos_weight={scale_pos_weight:.1f}")

    base_model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
    )

    # Calibrate so predict_proba() returns real probabilities, not raw scores
    calibrated = CalibratedClassifierCV(base_model, method="sigmoid", cv=3)

    # 5-fold CV — much more reliable than a single split on small datasets
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(calibrated, X, y, cv=cv, scoring="accuracy")
    print(f"  {target} (Stage {stage}): CV accuracy = {scores.mean():.2%} ± {scores.std():.2%} (n={n})")

    # Train final model on all data
    calibrated.fit(X, y)

    return {
        "model":         calibrated,
        "label_encoder": le_target,
        "cv_mean":       float(scores.mean()),
        "cv_std":        float(scores.std()),
        "sample_count":  n,
        "features":      features,
        "stage":         stage,
        "trained_at":    datetime.utcnow().isoformat(),
    }


def train_all(df: pd.DataFrame) -> dict:
    trained = {}

    print("\n=== STAGE 1 MODELS (seed features only — no circular refs) ===")
    for target in STAGE_1_TARGETS:
        result = train_one_field(df, target, SEED_FEATURES, stage=1)
        trained[target] = result

    print("\n=== STAGE 2 MODELS (seed + Stage 1 predictions as features) ===")
    for target in STAGE_2_TARGETS:
        result = train_one_field(df, target, STAGE_2_FEATURES, stage=2)
        trained[target] = result

    return trained


# ── SAVING ────────────────────────────────────────────────────────────────────

def save_models(trained: dict) -> dict:
    registry = {}
    # Load existing registry to preserve previous_path
    registry_path = f"{MODEL_DIR}/model_registry.json"
    existing = {}
    if os.path.exists(registry_path):
        with open(registry_path) as f:
            existing = json.load(f)

    for field, data in trained.items():
        if data is None:
            continue

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = f"{MODEL_DIR}/{field}_model_{timestamp}.pkl"

        with open(path, "wb") as f:
            pickle.dump(data, f)

        # Hash for integrity verification
        with open(path, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:8]

        registry[field] = {
            "active_path":   path,
            "previous_path": existing.get(field, {}).get("active_path"),
            "timestamp":     timestamp,
            "hash":          file_hash,
            "cv_mean":       data["cv_mean"],
            "cv_std":        data["cv_std"],
            "sample_count":  data["sample_count"],
            "stage":         data["stage"],
        }
        print(f"  Saved: {path} (hash: {file_hash})")

    with open(registry_path, "w") as f:
        json.dump(registry, f, indent=2)

    print(f"\nRegistry saved: {registry_path}")
    return registry


# ── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df = load_training_data()
    df, _ = engineer_features(df)
    trained = train_all(df)
    registry = save_models(trained)

    print("\n=== FINAL ACCURACY SUMMARY ===")
    for field, info in registry.items():
        print(f"  {field:<35} {info['cv_mean']:.0%} ± {info['cv_std']:.0%}  "
              f"(n={info['sample_count']}, stage={info['stage']})")
