# -*- coding: utf-8 -*-
"""
LUMA — LangGraph Agent
=======================
This is Jensen's loop built as a LangGraph state machine.

State machine nodes:
    OBSERVE  → Read the case (seed fields entered by staff)
    REASON   → Query the prediction model for each missing field
    ACT      → Return predictions with confidence scores

LangGraph is the production version of LangChain's agent framework.
It's an explicit state machine — nodes are functions, edges define transitions.
Easier to debug, easier to deploy, correct shape for LUMA.

Why LangGraph over LangChain vanilla?
  - Explicit state (not hidden in chain context)
  - Debuggable step-by-step (each node is a function you can test)
  - Production-grade (used at scale by enterprise teams)
  - Apache 2.0 license (free for commercial use)
"""

from typing import TypedDict, Optional
import json


# ─────────────────────────────────────────────
# GRAPH STATE
# The data that flows between nodes
# ─────────────────────────────────────────────

class LUMAState(TypedDict):
    # Input: what staff entered
    seed_fields: dict

    # Output: LUMA's predictions
    predictions: dict

    # Metadata
    customer_id: str
    case_id: Optional[str]
    error: Optional[str]


# ─────────────────────────────────────────────
# NODES (each is a step in Jensen's loop)
# ─────────────────────────────────────────────

def observe(state: LUMAState) -> LUMAState:
    """
    OBSERVE: Read what we know.
    Takes the seed fields staff entered and validates them.
    """
    seed = state.get("seed_fields", {})

    required = ["deceased_name"]
    missing = [f for f in required if not seed.get(f)]

    if missing:
        state["error"] = f"Missing required fields: {missing}"
        return state

    print(f"[LUMA/OBSERVE] Processing case for: {seed.get('deceased_name')}")
    print(f"[LUMA/OBSERVE] Known fields: {list(seed.keys())}")

    return state


def reason(state: LUMAState) -> LUMAState:
    """
    REASON: Predict missing fields from seed data.
    Queries the trained XGBoost models for each field we need to fill.
    If models aren't trained yet, uses rule-based heuristics as fallback.
    """
    if state.get("error"):
        return state

    seed = state["seed_fields"]
    predictions = {}

    # Fields we need to predict (everything not in seed)
    seed_fields = set(seed.keys())
    all_fields = {
        "gender", "marital_status", "race", "occupation", "education",
        "birth_city", "birth_state", "birth_country",
        "father_name", "mother_maiden_name",
        "veteran_status", "military_branch",
        "religion", "cemetery_name", "cemetery_address",
        "funeral_director", "service_date", "service_location",
        "next_of_kin_phone", "next_of_kin_address",
    }
    fields_to_predict = all_fields - seed_fields

    # Try ML model first
    ml_predictions = _query_ml_model(seed, fields_to_predict, state["customer_id"])
    predictions.update(ml_predictions)

    # Fill remaining gaps with rule-based heuristics
    heuristic_predictions = _apply_heuristics(seed, fields_to_predict - set(ml_predictions.keys()))
    predictions.update(heuristic_predictions)

    state["predictions"] = predictions
    print(f"[LUMA/REASON] Generated {len(predictions)} predictions")

    return state


def act(state: LUMAState) -> LUMAState:
    """
    ACT: Format predictions with confidence scores.
    Returns structured output ready for the UI.
    Color coding: green (>90%), yellow (70-90%), red (<70%)
    """
    if state.get("error"):
        return state

    predictions = state.get("predictions", {})

    # Add confidence scores and color coding
    structured = {}
    for field, value in predictions.items():
        confidence = value.get("confidence", 0.5) if isinstance(value, dict) else 0.5
        actual_value = value.get("value", value) if isinstance(value, dict) else value

        if confidence >= 0.90:
            status = "green"
        elif confidence >= 0.70:
            status = "yellow"
        else:
            status = "red"

        structured[field] = {
            "value": actual_value,
            "confidence": confidence,
            "status": status,
        }

    state["predictions"] = structured
    print(f"[LUMA/ACT] Returning {len(structured)} predictions with confidence scores")

    return state


# ─────────────────────────────────────────────
# GRAPH BUILDER
# ─────────────────────────────────────────────

def build_luma_graph():
    """
    Build the LangGraph state machine.
    Returns a compiled graph ready to invoke.
    """
    try:
        from langgraph.graph import StateGraph, END

        graph = StateGraph(LUMAState)

        # Add nodes
        graph.add_node("observe", observe)
        graph.add_node("reason", reason)
        graph.add_node("act", act)

        # Define edges (flow: observe → reason → act → END)
        graph.set_entry_point("observe")
        graph.add_edge("observe", "reason")
        graph.add_edge("reason", "act")
        graph.add_edge("act", END)

        return graph.compile()

    except ImportError:
        print("[LUMA/GRAPH] LangGraph not installed. Using sequential fallback.")
        return None


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────

def predict_fields(seed_fields: dict, customer_id: str) -> dict:
    """
    Main function: given seed fields, return predictions for all other fields.
    This is what the API calls.
    """
    initial_state: LUMAState = {
        "seed_fields": seed_fields,
        "predictions": {},
        "customer_id": customer_id,
        "case_id": None,
        "error": None,
    }

    # Try LangGraph first
    graph = build_luma_graph()
    if graph:
        result = graph.invoke(initial_state)
    else:
        # Fallback: run nodes sequentially without LangGraph
        result = observe(initial_state)
        result = reason(result)
        result = act(result)

    if result.get("error"):
        return {"error": result["error"], "predictions": {}}

    return {
        "seed_fields": seed_fields,
        "predictions": result.get("predictions", {}),
        "customer_id": customer_id,
    }


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _query_ml_model(seed: dict, fields_to_predict: set, customer_id: str) -> dict:
    """
    Query trained XGBoost models for field predictions.
    Returns empty dict if models aren't trained yet (Phase 2).
    """
    try:
        import pickle
        from pathlib import Path

        models_dir = Path(f"./data/models/{customer_id}")
        if not models_dir.exists():
            return {}

        predictions = {}
        seed_values = list(seed.values())

        for field_name in fields_to_predict:
            model_path = models_dir / f"{field_name}.pkl"
            if model_path.exists():
                with open(model_path, "rb") as f:
                    saved = pickle.load(f)
                model = saved["model"]
                encoder = saved["encoder"]

                try:
                    proba = model.predict_proba([seed_values])[0]
                    confidence = float(max(proba))
                    predicted_idx = proba.argmax()
                    predicted_value = encoder.inverse_transform([predicted_idx])[0]

                    predictions[field_name] = {
                        "value": predicted_value,
                        "confidence": confidence,
                    }
                except Exception:
                    pass

        return predictions

    except Exception:
        return {}


def _apply_heuristics(seed: dict, fields: set) -> dict:
    """
    Rule-based fallback when ML model isn't available yet.
    Low confidence — always yellow or red.
    These are educated guesses based on common patterns.
    """
    predictions = {}

    for field in fields:
        if field == "state" and "state" not in seed:
            predictions[field] = {"value": "CA", "confidence": 0.75}

        elif field == "birth_country":
            predictions[field] = {"value": "United States", "confidence": 0.70}

        elif field == "veteran_status":
            predictions[field] = {"value": "No", "confidence": 0.65}

        elif field == "disposition_method" and "disposition_method" not in seed:
            predictions[field] = {"value": "burial", "confidence": 0.55}

    return predictions
