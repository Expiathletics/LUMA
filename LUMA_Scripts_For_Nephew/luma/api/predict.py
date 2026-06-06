"""
LUMA Script 5 — Prediction API
FastAPI server with JWT auth and two-stage prediction chain.
customer_id always comes from verified JWT — NEVER from request body.

Run (dev):  uvicorn luma.api.predict:app --reload --port 8000
Run (prod): gunicorn -w 4 -k uvicorn.workers.UvicornWorker luma.api.predict:app
"""

import os
import pickle
import json
import numpy as np
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
from typing import Dict, Any, Optional
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("LUMA_API_SECRET_KEY")
ALGORITHM  = "HS256"
MODEL_DIR  = "./luma/models"

app      = FastAPI(title="LUMA Prediction API", version="2.0")
security = HTTPBearer()
models   = {}  # Loaded at startup, keyed by field name


# ── AUTH ──────────────────────────────────────────────────────────────────────

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT. Returns payload — customer_id lives here, not in request body."""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if not payload.get("customer_id"):
            raise HTTPException(status_code=403, detail="Token missing customer_id")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── STARTUP ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def load_models():
    """Load all trained models into memory at startup."""
    registry_path = f"{MODEL_DIR}/model_registry.json"
    if not os.path.exists(registry_path):
        print("⚠️  No model registry found — run train_model.py first")
        return
    with open(registry_path) as f:
        registry = json.load(f)
    for field, info in registry.items():
        model_path = info["active_path"]
        if not os.path.exists(model_path):
            print(f"⚠️  Model file missing: {model_path}")
            continue
        try:
            with open(model_path, "rb") as f:
                models[field] = pickle.load(f)
            print(f"✅ Loaded: {field} ({info['cv_mean']:.0%} CV accuracy, stage {info['stage']})")
        except (pickle.UnpicklingError, EOFError):
            # Try rollback to previous version
            prev = info.get("previous_path")
            if prev and os.path.exists(prev):
                print(f"⚠️  Corrupt model, rolling back to: {prev}")
                with open(prev, "rb") as f:
                    models[field] = pickle.load(f)
            else:
                print(f"❌ Cannot load {field} — retraining required")


# ── REQUEST/RESPONSE MODELS ───────────────────────────────────────────────────

class PredictRequest(BaseModel):
    seed_fields: Dict[str, Any]

    @validator("seed_fields")
    def validate_seeds(cls, v):
        required_any = ["deceased_name", "date_of_death", "zip_code"]
        if not any(k in v for k in required_any):
            raise ValueError(f"At least one of {required_any} must be provided")
        if "date_of_death" in v:
            try:
                datetime.strptime(v["date_of_death"], "%Y-%m-%d")
            except ValueError:
                raise ValueError("date_of_death must be YYYY-MM-DD format")
        return v


# ── FEATURE PREP ──────────────────────────────────────────────────────────────

def prep_seed_features(seed: dict) -> dict:
    features = {}
    dod = seed.get("date_of_death")
    if dod:
        try:
            dt = datetime.strptime(dod, "%Y-%m-%d")
            features["dod_month"] = dt.month
            features["dod_year"]  = dt.year
            features["dod_dow"]   = dt.weekday()
        except Exception:
            features.update({"dod_month": -1, "dod_year": -1, "dod_dow": -1})
    else:
        features.update({"dod_month": -1, "dod_year": -1, "dod_dow": -1})

    zip_code = seed.get("zip_code", "")
    features["zip_region"] = int(zip_code[:3]) if str(zip_code)[:3].isdigit() else -1
    features["age_at_death"] = seed.get("age_at_death") or -1
    return features


def predict_field(model_data: dict, feature_dict: dict):
    """Returns (predicted_value, calibrated_confidence)."""
    model    = model_data["model"]
    le       = model_data.get("label_encoder")
    feat_names = model_data["features"]
    X = np.array([[feature_dict.get(f, -1) for f in feat_names]])
    pred  = model.predict(X)[0]
    proba = model.predict_proba(X)[0]
    conf  = float(max(proba))
    if le is not None:
        pred = le.inverse_transform([int(pred)])[0]
    return pred, round(conf, 3)


def get_tier(confidence: float) -> str:
    if confidence >= 0.90: return "green"   # Auto-fill
    if confidence >= 0.70: return "yellow"  # Pre-fill, verify
    return "red"                             # Manual entry required


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@app.post("/predict")
def predict(request: PredictRequest, token: dict = Depends(verify_token)):
    """
    Two-stage prediction:
    Stage 1 → predict service_type and is_veteran from seed fields only
    Stage 2 → predict burial_location using seeds + Stage 1 outputs
    customer_id comes from JWT — never from request body.
    """
    if not models:
        raise HTTPException(status_code=503, detail="Models not loaded — run train_model.py first")

    customer_id  = token["customer_id"]
    seed         = request.seed_fields
    predictions  = {}
    seed_features = prep_seed_features(seed)
    stage1_encoded = {}

    # ── Stage 1 ───────────────────────────────────────────────────────────────
    for field in ["service_type", "is_veteran"]:
        if field in models and field not in seed:
            val, conf = predict_field(models[field], seed_features)
            predictions[field] = {"value": val, "confidence": conf, "tier": get_tier(conf)}
            # Encode for Stage 2 input
            if field == "service_type":
                le = models[field].get("label_encoder")
                stage1_encoded["service_type_encoded"] = le.transform([val])[0] if le else 0
            elif field == "is_veteran":
                stage1_encoded["is_veteran_int"] = 1 if val else 0

    # ── Stage 2 ───────────────────────────────────────────────────────────────
    stage2_features = {**seed_features, **stage1_encoded}
    for field in ["burial_location_bucket"]:
        if field in models and field not in seed:
            val, conf = predict_field(models[field], stage2_features)
            predictions[field] = {"value": val, "confidence": conf, "tier": get_tier(conf)}

    overall = (
        round(sum(p["confidence"] for p in predictions.values()) / len(predictions), 3)
        if predictions else 0.0
    )

    return {
        "customer_id":       customer_id,
        "predictions":       predictions,
        "overall_confidence": overall,
    }


@app.get("/health")
def health():
    """Health check — verifies models are loaded."""
    return {
        "status":        "ok" if models else "degraded",
        "models_loaded": list(models.keys()),
        "model_count":   len(models),
    }
