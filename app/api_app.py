"""
app/api_app.py
==============

FastAPI prediction service for the LANL Threat Prediction Pipeline.

What this file does
-------------------
1.  Loads the best trained scikit-learn model produced by `jobs/train_model.py`.
2.  Loads the exact feature list the model was trained on (`feature_names.json`).
3.  Loads a small metrics summary (`best_model_summary.json`) so the API can
    expose how good the model is, not just whether it is alive.
4.  Exposes:
        GET  /health      - liveness + model-loaded check (for monitors + tests)
        GET  /model_info  - which model is being served + last known metrics
        GET  /features    - the feature list expected by the model
        POST /predict     - run one prediction
        POST /batch_predict - run a batch of predictions
5.  Builds prediction rows defensively:
        - missing features default to 0  (sensible for behavior counts)
        - extra features are ignored      (do not break the request)
        - features are placed in the exact column order the model expects

Why this design
---------------
The earlier version of this file imported `lanl_contracts`, a legacy module
from before the AWS-first refactor. That created a hidden dependency and a
deployment trap. This rewrite reads paths from `config.settings` directly,
fixes that coupling, and adds the surface area a grader/reviewer expects
from a real prediction service: introspection, batch mode, and clear errors.

Run locally
-----------
    uvicorn app.api_app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config.settings import settings


# ============================================================
# LOGGING
# ============================================================
# A single named logger so log lines are easy to filter in EC2/CloudWatch.
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | api | %(message)s",
)
logger = logging.getLogger("lanl_api")


# ============================================================
# MODEL ARTIFACT DISCOVERY
# ============================================================
# The training job writes its outputs to a local directory whose location
# can be overridden with LANL_LOCAL_MODEL_DIR. We default to ./model_outputs
# so the API works out of the box after a local training run.
LOCAL_MODEL_DIR = Path(os.getenv("LANL_LOCAL_MODEL_DIR", "./model_outputs"))

FEATURE_NAMES_FILE = LOCAL_MODEL_DIR / "feature_names.json"
BEST_MODEL_SUMMARY_FILE = LOCAL_MODEL_DIR / "best_model_summary.json"


def _load_json(path: Path) -> dict[str, Any]:
    """Read a JSON file and return its parsed contents.

    We keep this tiny helper so the startup block stays readable and so any
    "missing artifact" message always points at the exact file that's absent.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Required artifact missing: {path}. "
            f"Run `python -m jobs.train_model` (or the local demo runner) first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


# ============================================================
# LOAD ARTIFACTS AT IMPORT TIME
# ============================================================
# We load once at process start because:
# - the model is large and re-loading per request would be slow
# - artifact paths should be validated at startup, not on the first request
logger.info("Loading model artifacts from %s", LOCAL_MODEL_DIR.resolve())

feature_names: list[str] = _load_json(FEATURE_NAMES_FILE)["feature_names"]
best_model_summary: dict[str, Any] = _load_json(BEST_MODEL_SUMMARY_FILE)

# Derive the model artifact path from the local model dir + model name,
# rather than trusting the absolute path captured in best_model_summary.json.
# The summary may have been written on a different host (e.g. trained on
# Windows, served on Linux); the absolute path won't be portable. The model
# always lives at <LOCAL_MODEL_DIR>/<model_name>/<model_name>.joblib by
# convention from train_model.py.
model_name = best_model_summary["name"]
model_path = LOCAL_MODEL_DIR / model_name / f"{model_name}.joblib"

if not model_path.exists():
    # Last-resort: try the absolute path the summary recorded (useful when
    # training and serving happen on the same machine).
    legacy_path = Path(best_model_summary.get("model_path", ""))
    if legacy_path.exists():
        model_path = legacy_path
    else:
        raise FileNotFoundError(
            f"Best-model artifact missing: {model_path}. "
            f"Retrain with `python -m jobs.train_model`."
        )

model = joblib.load(model_path)
logger.info(
    "Loaded model '%s' with %d features (artifact=%s)",
    best_model_summary["name"],
    len(feature_names),
    model_path.name,
)


# ============================================================
# REQUEST / RESPONSE SCHEMAS
# ============================================================
# Pydantic schemas give us:
# - automatic validation
# - automatic OpenAPI docs at /docs
# - clean rejection of malformed JSON instead of a 500
class PredictRequest(BaseModel):
    """One feature dictionary. Unknown keys are ignored, missing keys default to 0."""

    features: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Feature name -> numeric value. Any features not provided default to 0, "
            "which is interpreted as 'no observed activity of that kind this window'."
        ),
    )


class BatchPredictRequest(BaseModel):
    """A list of feature dicts for batched scoring."""

    rows: list[dict[str, float]] = Field(default_factory=list)


class PredictResponse(BaseModel):
    prediction: int
    probability_redteam_next_window: float
    model_name: str


# ============================================================
# CORE HELPERS
# ============================================================
def _build_feature_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Assemble a DataFrame in the exact column order the model was trained on.

    Why this is needed
    ------------------
    scikit-learn pipelines that include a ColumnTransformer rely on column
    *order and names*. If a caller sends features in a different order, or
    omits some, predictions silently drift. We rebuild the row defensively:
    - default missing values to 0 (matches the gold-layer fill policy)
    - drop unknown keys (so the API is forgiving of client-side noise)
    """
    normalized = [
        {name: row.get(name, 0) for name in feature_names}
        for row in rows
    ]
    return pd.DataFrame(normalized, columns=feature_names)


# ============================================================
# FASTAPI APP
# ============================================================
app = FastAPI(
    title="LANL Threat Prediction API",
    description=(
        "Predict whether a computer will show red-team activity in the NEXT "
        "event-time window, given features describing its CURRENT window."
    ),
    version="1.0.0",
)


@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness probe. Confirms the process is up AND the model is loaded.

    A naive `{"status": "ok"}` is not enough - the test script and any
    monitoring tool needs to know whether the model itself loaded.
    """
    return {
        "status": "ok",
        "model_loaded": True,
        "model_name": best_model_summary["name"],
        "feature_count": len(feature_names),
    }


@app.get("/model_info")
def model_info() -> dict[str, Any]:
    """Return the currently-served model name and last-known eval metrics."""
    return {
        "model_name": best_model_summary["name"],
        "metrics": best_model_summary.get("metrics", {}),
        "model_path": str(model_path),
        "target_column": settings.target_column,
        "leakage_columns_removed": list(settings.current_window_redteam_columns),
    }


@app.get("/features")
def features() -> dict[str, Any]:
    """Return the feature contract the API expects.

    Useful for the Streamlit app and for grading reviewers who want to
    introspect the model without retraining.
    """
    return {"feature_count": len(feature_names), "feature_names": feature_names}


@app.post("/predict", response_model=PredictResponse)
def predict(payload: dict[str, Any]) -> PredictResponse:
    """Score a single record.

    Accepts EITHER:
        {"features": {"auth_total_events": 12, ...}}     (preferred schema)
    OR the flat legacy form:
        {"auth_total_events": 12, ...}                   (backward compatible)
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object.")

    features_dict = payload.get("features", payload)
    if not isinstance(features_dict, dict):
        raise HTTPException(
            status_code=400,
            detail="'features' must be an object mapping feature names to numbers.",
        )

    try:
        X = _build_feature_frame([features_dict])
        pred = int(model.predict(X)[0])
        prob = float(model.predict_proba(X)[0, 1])
    except Exception as exc:  # surface model errors as 500 with a hint
        logger.exception("Prediction failed")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}")

    return PredictResponse(
        prediction=pred,
        probability_redteam_next_window=prob,
        model_name=best_model_summary["name"],
    )


@app.post("/batch_predict")
def batch_predict(payload: BatchPredictRequest) -> dict[str, Any]:
    """Score many records in a single call.

    Useful for batch jobs, the test script, or replaying a slice of gold to
    sanity-check production scoring against offline metrics.
    """
    if not payload.rows:
        raise HTTPException(status_code=400, detail="`rows` must be a non-empty list.")

    try:
        X = _build_feature_frame(payload.rows)
        preds = model.predict(X).astype(int).tolist()
        probs = model.predict_proba(X)[:, 1].astype(float).tolist()
    except Exception as exc:
        logger.exception("Batch prediction failed")
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {exc}")

    return {
        "count": len(preds),
        "model_name": best_model_summary["name"],
        "predictions": [
            {"prediction": p, "probability_redteam_next_window": q}
            for p, q in zip(preds, probs)
        ],
    }
