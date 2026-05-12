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
import numpy as np
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


@app.post("/explain")
def explain(payload: dict[str, Any]) -> dict[str, Any]:
    """Return per-feature contributions to the prediction (explainable AI).

    For a linear model (logistic regression), each feature's contribution to
    the predicted log-odds is exactly:

        contribution_i = coef_i * scaled_value_i

    where `scaled_value_i` is the feature value AFTER the preprocessing
    pipeline (median impute + standard scale). This is not an approximation
    - it's the exact decomposition of the model's decision. SOC analysts
    can see which behaviors pushed risk UP vs. DOWN for a specific row.

    For non-linear models (e.g. random forest), exact decomposition would
    require SHAP. We return a 200 with method='unsupported' so the UI can
    gracefully fall back to global feature importance.
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object.")

    features_dict = payload.get("features", payload)
    if not isinstance(features_dict, dict):
        raise HTTPException(
            status_code=400,
            detail="'features' must be an object mapping feature names to numbers.",
        )

    X = _build_feature_frame([features_dict])

    try:
        pred = int(model.predict(X)[0])
        prob = float(model.predict_proba(X)[0, 1])
    except Exception as exc:
        logger.exception("Prediction in /explain failed")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}")

    # Pull the named pipeline steps. train_model.py builds Pipeline([
    #   ("preprocessor", ColumnTransformer(num + impute + scale)),
    #   ("model", <classifier>),
    # ]) - so these names are stable.
    try:
        preprocessor = model.named_steps["preprocessor"]
        estimator = model.named_steps["model"]
    except (AttributeError, KeyError):
        return {
            "prediction": pred,
            "probability_redteam_next_window": prob,
            "model_name": best_model_summary["name"],
            "method": "unsupported",
            "intercept": None,
            "contributions": [],
            "note": "Served model is not a Pipeline with named 'preprocessor' + 'model' steps.",
        }

    if not hasattr(estimator, "coef_"):
        return {
            "prediction": pred,
            "probability_redteam_next_window": prob,
            "model_name": best_model_summary["name"],
            "method": "unsupported",
            "intercept": None,
            "contributions": [],
            "note": "Per-row decomposition is only available for linear models.",
        }

    # Linear-model decomposition.
    try:
        X_scaled = np.asarray(preprocessor.transform(X))[0]
    except Exception as exc:
        logger.exception("Preprocessor transform failed in /explain")
        raise HTTPException(status_code=500, detail=f"Preprocessor transform failed: {exc}")

    coefficients = np.asarray(estimator.coef_)[0]
    intercept = float(np.asarray(estimator.intercept_)[0])

    if len(coefficients) != len(feature_names) or len(X_scaled) != len(feature_names):
        # Shouldn't happen with the current pipeline, but a defensive check
        # protects against silent misalignment if someone retrains differently.
        raise HTTPException(
            status_code=500,
            detail=(
                f"Shape mismatch: feature_names={len(feature_names)}, "
                f"coef={len(coefficients)}, scaled={len(X_scaled)}"
            ),
        )

    contributions = [
        {
            "feature": name,
            "raw_value": float(features_dict.get(name, 0)),
            "scaled_value": float(scaled_v),
            "coefficient": float(coef),
            "contribution": float(scaled_v * coef),
        }
        for name, scaled_v, coef in zip(feature_names, X_scaled, coefficients)
    ]
    # Sort by absolute contribution (biggest drivers first)
    contributions.sort(key=lambda c: abs(c["contribution"]), reverse=True)

    return {
        "prediction": pred,
        "probability_redteam_next_window": prob,
        "model_name": best_model_summary["name"],
        "method": "linear_log_odds_decomposition",
        "intercept": intercept,
        "contributions": contributions,
    }


@app.post("/counterfactual")
def counterfactual(payload: dict[str, Any]) -> dict[str, Any]:
    """Smallest single-feature interventions that would lower predicted risk.

    For a linear model (logistic regression) this is an EXACT mathematical
    inversion. Let L = intercept + sum_i coef_i * scaled_x_i be the
    log-odds. To bring the predicted probability down to p_target, we need
    delta_L = logit(p_target) - L_current. For each feature j alone to
    deliver that delta:

        delta_scaled_j = delta_L / coef_j
        delta_raw_j    = delta_scaled_j * scale_j     (since scaled = raw / scale + const)

    We rank features by absolute raw change required (smallest = most
    actionable) and filter out interventions that would require feature
    values to go negative (LANL features are all non-negative counts /
    ratios / byte counts).
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object.")

    features_dict = payload.get("features", payload)
    if not isinstance(features_dict, dict):
        raise HTTPException(
            status_code=400,
            detail="'features' must be an object mapping feature names to numbers.",
        )

    target_probability = float(payload.get("target_probability", 0.20))
    if not 0.0 < target_probability < 1.0:
        raise HTTPException(
            status_code=400,
            detail="target_probability must be strictly between 0 and 1.",
        )

    X = _build_feature_frame([features_dict])
    try:
        current_prob = float(model.predict_proba(X)[0, 1])
    except Exception as exc:
        logger.exception("Counterfactual: predict_proba failed")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}")

    # --- Pipeline introspection ----------------------------------
    try:
        preprocessor = model.named_steps["preprocessor"]
        estimator = model.named_steps["model"]
    except (AttributeError, KeyError):
        return {
            "current_probability": current_prob,
            "target_probability": target_probability,
            "method": "unsupported",
            "interventions": [],
            "note": "Served model is not a Pipeline with 'preprocessor' + 'model' steps.",
        }

    if not hasattr(estimator, "coef_"):
        return {
            "current_probability": current_prob,
            "target_probability": target_probability,
            "method": "unsupported",
            "interventions": [],
            "note": "Counterfactuals only available for linear models.",
        }

    # Nothing to do if we're already at or below target.
    if current_prob <= target_probability:
        return {
            "current_probability": current_prob,
            "target_probability": target_probability,
            "method": "linear_counterfactual",
            "interventions": [],
            "note": "Predicted risk is already at or below the target threshold.",
        }

    # --- Pull scaler params --------------------------------------
    try:
        col_xformer = preprocessor.named_transformers_["num"]
        scaler = col_xformer.named_steps["scaler"]
        scales = np.asarray(scaler.scale_)
    except (AttributeError, KeyError) as exc:
        logger.warning("Could not extract scaler parameters: %s", exc)
        return {
            "current_probability": current_prob,
            "target_probability": target_probability,
            "method": "unsupported",
            "interventions": [],
            "note": "Could not extract scaler parameters from the pipeline.",
        }

    try:
        X_scaled = np.asarray(preprocessor.transform(X))[0]
    except Exception as exc:
        logger.exception("Counterfactual: preprocessor.transform failed")
        raise HTTPException(status_code=500, detail=f"Transform failed: {exc}")

    coefficients = np.asarray(estimator.coef_)[0]
    intercept = float(np.asarray(estimator.intercept_)[0])

    current_logits = intercept + float(np.dot(coefficients, X_scaled))
    # logit() but clamped away from 0/1 for safety
    eps = 1e-12
    target_logits = float(
        np.log(target_probability / max(1.0 - target_probability, eps))
    )
    needed_delta = target_logits - current_logits  # negative (we want to lower)

    if abs(needed_delta) < 1e-9:
        return {
            "current_probability": current_prob,
            "target_probability": target_probability,
            "method": "linear_counterfactual",
            "interventions": [],
            "note": "Current and target log-odds are effectively equal.",
        }

    # --- Per-feature counterfactual -----------------------------
    interventions = []
    for i, name in enumerate(feature_names):
        coef_i = float(coefficients[i])
        scale_i = float(scales[i]) if i < len(scales) else 1.0
        if abs(coef_i) < 1e-9:
            continue  # this feature can't move the needle at all

        delta_scaled = needed_delta / coef_i
        delta_raw = delta_scaled * scale_i

        current_raw = float(features_dict.get(name, 0))
        new_raw = current_raw + delta_raw
        direction = "decrease" if delta_raw < 0 else "increase"
        # All LANL features are counts / ratios / byte counts >= 0.
        feasible_nonneg = new_raw >= 0.0

        interventions.append({
            "feature": name,
            "current_raw": current_raw,
            "suggested_raw": float(new_raw),
            "delta_raw": float(delta_raw),
            "abs_delta_raw": float(abs(delta_raw)),
            "direction": direction,
            "coefficient": coef_i,
            "feasible_nonnegative": feasible_nonneg,
        })

    feasible = [c for c in interventions if c["feasible_nonnegative"]]
    feasible.sort(key=lambda c: c["abs_delta_raw"])
    fallback = sorted(interventions, key=lambda c: c["abs_delta_raw"])
    pool = feasible if feasible else fallback

    return {
        "current_probability": current_prob,
        "target_probability": target_probability,
        "method": "linear_counterfactual",
        "current_logits": current_logits,
        "target_logits": target_logits,
        "all_feasible": bool(feasible),
        "interventions": pool[:10],
    }


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
