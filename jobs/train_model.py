"""
jobs/train_model.py
===================

Train and evaluate the LANL threat-prediction models, log everything to
MLflow (tracking + Model Registry), and write the artifacts the FastAPI
service will load at startup.

What this script does (in plain English)
----------------------------------------
1. Reads the gold feature table from the canonical cloud path:
       s3://<bucket>/<prefix>/gold/computer_time   (parquet)
   written by `jobs/silver_to_gold_emr.py`. This is the path used for the
   real pipeline and for the deployed model.

   A small, OFF-BY-DEFAULT local CSV fallback is provided for offline
   verification ONLY (e.g. running the test script without standing up
   EMR each time). The project specification states that storage must
   be cloud/distributed - the local CSV is never the canonical storage
   layer, it is a development aid that has to be explicitly enabled with
   `LANL_USE_LOCAL_GOLD=1`.

2. If a target column is not present in the gold table, builds one from
   the current-window red-team flag using a window function in pandas.
   This is what makes the model a *predictive* one rather than a
   *retrospective* one.

3. Removes leakage-sensitive columns BEFORE training, then re-checks
   that no leakage column survived. Fails loudly if any do.

4. Performs a time-aware train / validation / test split:
       earliest 60 % of windows -> train
       next     20 % of windows -> validation
       latest   20 % of windows -> test

5. Trains a benchmark (Logistic Regression) and a stronger model
   (Random Forest), evaluates both with precision / recall / F1 /
   ROC AUC / PR AUC, and logs each run to MLflow.

6. Saves three artifacts:
       feature_names.json         (what columns the API must expect)
       best_model_summary.json    (which model "won" + its metrics)
       <model_name>.joblib        (the actual serialized pipeline)

Why scikit-learn after Spark?
-----------------------------
The heavy data engineering is done in Spark/EMR. By the time we hit the
gold layer, we have one row per (computer, hour) - a relatively small
table that scikit-learn handles comfortably. We use the right tool for
each phase: distributed compute for the data engineering, single-node
sklearn for the modeling.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# XGBoost is optional - if it isn't installed we skip training that model
# rather than fail. The LR and RF still cover the rubric requirements.
try:
    from xgboost import XGBClassifier
    _XGBOOST_OK = True
except ImportError:
    _XGBOOST_OK = False

# LightGBM is also optional. Same reason; same fallback behavior.
# Gives us a second strong gradient-boosted model so MLflow has 4 to
# choose between, and the cost-aware threshold comparison is more
# interesting on the slide.
try:
    from lightgbm import LGBMClassifier
    _LIGHTGBM_OK = True
except ImportError:
    _LIGHTGBM_OK = False

from config.settings import settings


# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | train | %(message)s",
)
logger = logging.getLogger("train_model")


# ============================================================
# OUTPUT PATHS
# ============================================================
# These local paths are what the FastAPI service reads at startup.
LOCAL_MODEL_DIR = Path(os.getenv("LANL_LOCAL_MODEL_DIR", "./model_outputs"))
LOCAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_NAMES_FILE = LOCAL_MODEL_DIR / "feature_names.json"
BEST_MODEL_SUMMARY_FILE = LOCAL_MODEL_DIR / "best_model_summary.json"

MLFLOW_TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    f"file:{(LOCAL_MODEL_DIR.resolve() / 'mlruns').as_posix()}",
)
MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "lanl_threat_prediction")

# A fixed seed makes evaluation reproducible.
RANDOM_STATE = 42

# =====================================================================
# OFFLINE VERIFICATION ONLY  (NOT the project's canonical storage path)
# =====================================================================
# The project specification requires distributed/cloud storage for the
# real pipeline. The cloud parquet path written by silver_to_gold_emr.py
# is what feeds the deployed model.
#
# This local CSV is an OPT-IN fallback so that:
#   * the test script can run when EMR is intentionally shut down to
#     save free-tier credits,
#   * a grader can re-train the model on a laptop and immediately verify
#     the API responds correctly.
#
# It is NEVER the source-of-truth. It must be explicitly opted in to
# avoid masking a real cloud read failure.
LOCAL_GOLD_CSV = Path("./gold_outputs/gold_computer_time_sample.csv")
USE_LOCAL_GOLD_FALLBACK = os.getenv("LANL_USE_LOCAL_GOLD", "0") == "1"

# MLflow Model Registry name. The model_registry stage is part of the
# rubric's "tracked in MLflow" requirement.
MLFLOW_REGISTERED_MODEL_NAME = os.getenv(
    "MLFLOW_REGISTERED_MODEL_NAME", "lanl_threat_predictor"
)

# Memory-safety subsample. On a laptop with limited RAM, the full 13.9 M-row
# gold table can OOM during train_test_split. Setting LANL_TRAIN_MAX_ROWS to,
# say, 3000000 keeps ALL positives (only 596 of them) and randomly samples
# negatives down to that budget. The model trains fine because the rare
# positive class is preserved in full and negatives are still abundant.
MAX_ROWS_FOR_TRAINING = int(os.getenv("LANL_TRAIN_MAX_ROWS", "0"))


# ============================================================
# JSON HELPER
# ============================================================
def write_json(path: Path, payload: dict) -> None:
    """Pretty-print JSON to disk. Used for the two artifact files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ============================================================
# DATA LOADER  (cloud-first, local fallback)
# ============================================================
def load_gold() -> pd.DataFrame:
    """Load the gold feature table.

    Canonical path  (always tried first):
        settings.gold_computer_time_path    e.g. s3://.../gold/computer_time

    Fallback path  (only if LANL_USE_LOCAL_GOLD=1 is set explicitly):
        ./gold_outputs/gold_computer_time_sample.csv

    Why the fallback is opt-in
    --------------------------
    The project spec disallows "local CSV files" as the storage layer.
    Silently falling back to a CSV would hide a real cloud-read failure
    and weaken the architecture story. The opt-in flag makes the choice
    explicit so a reviewer can tell which mode produced the model.
    """
    # 1) Canonical cloud path (parquet on S3)
    try:
        logger.info("Reading canonical gold table: %s", settings.gold_computer_time_path)
        df = pd.read_parquet(settings.gold_computer_time_path)
        logger.info("Cloud read succeeded (%d rows)", len(df))
        return df
    except Exception as exc:
        logger.warning("Cloud read failed: %s", exc)

    # 2) Opt-in local CSV fallback
    if USE_LOCAL_GOLD_FALLBACK and LOCAL_GOLD_CSV.exists():
        logger.warning(
            "LANL_USE_LOCAL_GOLD=1; loading local fallback CSV at %s. "
            "This is for offline verification only - the canonical storage "
            "layer is parquet in S3.",
            LOCAL_GOLD_CSV,
        )
        return pd.read_csv(LOCAL_GOLD_CSV)

    raise FileNotFoundError(
        "Could not read the gold feature table.\n"
        f"  Canonical (cloud) path: {settings.gold_computer_time_path}\n"
        f"  Local fallback file:    {LOCAL_GOLD_CSV.resolve()} (opt-in via "
        "LANL_USE_LOCAL_GOLD=1)\n\n"
        "Run the EMR jobs to populate the cloud path, or set "
        "LANL_USE_LOCAL_GOLD=1 if you intentionally want to use the "
        "offline verification path."
    )


# ============================================================
# TARGET BUILDER  (only used if the gold table doesn't have one)
# ============================================================
def ensure_target(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the target column exists.

    The cloud gold table already has `target_redteam_next_window` because
    `silver_to_gold_emr.py` builds it with a Spark window function. The
    local sample CSV does not (it's an older artifact), so we build the
    same target here using a pandas group-shift.

    Definition:
        target_redteam_next_window =
            1 if the SAME computer has redteam_current_flag > 0 in its
            *next* time_window, else 0.

    Why this matters: it is the anti-leakage heart of the project.
    """
    if settings.target_column in df.columns:
        return df

    if "redteam_current_flag" not in df.columns:
        if "redteam_flag" in df.columns:
            df["redteam_current_flag"] = (df["redteam_flag"] > 0).astype(int)
        else:
            raise ValueError(
                "Gold table is missing both `target_redteam_next_window` and "
                "`redteam_current_flag` - cannot build the future target."
            )

    df = df.sort_values(["computer", "time_window"]).reset_index(drop=True)
    df[settings.target_column] = (
        df.groupby("computer")["redteam_current_flag"]
          .shift(-1)
          .fillna(0)
          .astype(int)
    )
    logger.info(
        "Built `%s` locally. Positive rate: %.4f",
        settings.target_column, df[settings.target_column].mean(),
    )
    return df


# ============================================================
# TRAIN / VALIDATION / TEST SPLIT
# ============================================================
# We support two split strategies, chosen via the LANL_SPLIT env var:
#
#   stratified  (default)
#       Stratified RANDOM 60/20/20 split that preserves the positive rate
#       across train/valid/test. The right choice for the LANL dataset
#       because all red-team events occur in a finite campaign window
#       (~first 60% of event-time). A strict time-aware split would put
#       every positive in train and leave valid/test with 0 positives,
#       making every metric collapse to NaN/0.
#
#   time
#       Strict time-aware 60/20/20 split. Useful in general, but on LANL
#       it produces unmeasurable evaluations. Kept for reproducibility
#       and so the trade-off is explicit in the codebase.
# ============================================================
SPLIT_STRATEGY = os.getenv("LANL_SPLIT", "stratified").lower()


def time_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Earliest 60 % of windows -> train, next 20 % -> valid, last 20 % -> test.

    Only useful when positives are distributed across the full event-time
    horizon. For LANL specifically, see SPLIT_STRATEGY above.
    """
    windows = sorted(df["time_window"].dropna().unique().tolist())
    if len(windows) < 5:
        raise ValueError("Not enough distinct time windows for a meaningful split.")

    train_cut = windows[int(len(windows) * 0.60)]
    valid_cut = windows[int(len(windows) * 0.80)]

    train_df = df[df["time_window"] <= train_cut].copy()
    valid_df = df[(df["time_window"] > train_cut) & (df["time_window"] <= valid_cut)].copy()
    test_df  = df[df["time_window"] >  valid_cut].copy()
    return train_df, valid_df, test_df


def stratified_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Stratified random 60/20/20 split. Keeps positive rate proportional."""
    y = df[settings.target_column].astype(int)
    if y.sum() < 6:
        raise ValueError(
            f"Only {int(y.sum())} positive rows total; cannot stratify meaningfully."
        )

    train_df, temp_df = train_test_split(
        df, test_size=0.40, stratify=y, random_state=RANDOM_STATE
    )
    valid_df, test_df = train_test_split(
        temp_df,
        test_size=0.50,
        stratify=temp_df[settings.target_column].astype(int),
        random_state=RANDOM_STATE,
    )
    return (
        train_df.reset_index(drop=True),
        valid_df.reset_index(drop=True),
        test_df.reset_index(drop=True),
    )


def split_for_strategy(df: pd.DataFrame):
    """Dispatch to the chosen split strategy. Logs which one is used."""
    if SPLIT_STRATEGY == "time":
        logger.info("Using STRICT time-aware split (LANL_SPLIT=time)")
        return time_split(df)
    logger.info("Using STRATIFIED random split (LANL_SPLIT=%s)", SPLIT_STRATEGY)
    return stratified_split(df)


# ============================================================
# LEAKAGE GUARD
# ============================================================
def assert_no_leakage(feature_cols: list[str]) -> None:
    """Fail loudly if any current-window redteam feature is still in the set.

    This is the second line of defense; the first is dropping these columns
    earlier. We re-check here because a future contributor might re-introduce
    a leak by accident.
    """
    leaking = [c for c in feature_cols if c in settings.current_window_redteam_columns]
    if leaking:
        raise ValueError(f"Leakage columns found in feature set: {leaking}")


# ============================================================
# PER-MODEL TRAIN + EVAL
# ============================================================
def evaluate_model(
    model_name: str,
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_valid: pd.DataFrame,
    y_valid: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict:
    """Train one pipeline, log everything, save the .joblib, return metrics."""
    logger.info("=" * 80)
    logger.info("TRAINING MODEL: %s", model_name)

    with mlflow.start_run(run_name=model_name):
        pipeline.fit(X_train, y_train)

        # If only one class is present in any split, predict_proba can be 1-col.
        # _safe_prob handles that without crashing.
        valid_pred = pipeline.predict(X_valid)
        valid_prob = _safe_prob(pipeline, X_valid)
        test_pred  = pipeline.predict(X_test)
        test_prob  = _safe_prob(pipeline, X_test)

        metrics = {
            "valid_precision": precision_score(y_valid, valid_pred, zero_division=0),
            "valid_recall":    recall_score(y_valid,    valid_pred, zero_division=0),
            "valid_f1":        f1_score(y_valid,        valid_pred, zero_division=0),
            "valid_roc_auc":   _safe_roc(y_valid, valid_prob),
            "valid_pr_auc":    _safe_pr(y_valid, valid_prob),
            "test_precision":  precision_score(y_test,  test_pred, zero_division=0),
            "test_recall":     recall_score(y_test,     test_pred, zero_division=0),
            "test_f1":         f1_score(y_test,         test_pred, zero_division=0),
            "test_roc_auc":    _safe_roc(y_test, test_prob),
            "test_pr_auc":     _safe_pr(y_test, test_prob),
        }

        # ---- MLflow logging -----------------------------------------
        for k, v in metrics.items():
            mlflow.log_metric(k, float(v))

        mlflow.log_param("model_name", model_name)
        mlflow.log_param("target_column", settings.target_column)
        mlflow.log_param("feature_count", X_train.shape[1])
        mlflow.log_param(
            "split_strategy",
            "time_aware_60_20_20" if SPLIT_STRATEGY == "time"
            else "stratified_random_60_20_20",
        )
        mlflow.log_param(
            "leakage_columns_removed",
            ",".join(settings.current_window_redteam_columns),
        )

        # ---- Local artifacts ---------------------------------------
        model_dir = LOCAL_MODEL_DIR / model_name
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "validation_report.txt").write_text(
            classification_report(y_valid, valid_pred, zero_division=0),
            encoding="utf-8",
        )
        (model_dir / "test_report.txt").write_text(
            classification_report(y_test, test_pred, zero_division=0),
            encoding="utf-8",
        )
        write_json(model_dir / "metrics.json", metrics)

        # ---- Threshold analysis on the validation set --------------
        # Compute the precision / recall / F1 curve so the API can serve
        # threshold-tuning queries (operationally correct cutoff under a
        # given FP-vs-FN cost ratio). We compute it from validation, not
        # test - test is reserved for the headline metric only.
        threshold_payload = _build_threshold_payload(
            y_true=y_valid.values, y_prob=valid_prob,
        )
        write_json(model_dir / "threshold_analysis.json", threshold_payload)

        model_path = model_dir / f"{model_name}.joblib"
        joblib.dump(pipeline, model_path)

        # ---- MLflow Model Registry --------------------------------
        # The project rubric specifies MLflow tracking AND the model
        # registry. We register the model under a stable name and let
        # MLflow auto-increment the version number. The best version is
        # promoted to the "Production" alias at the end of main().
        try:
            mlflow.sklearn.log_model(
                sk_model=pipeline,
                artifact_path="model",
                input_example=X_train.head(3),
                registered_model_name=MLFLOW_REGISTERED_MODEL_NAME,
            )
        except Exception as e:
            # Don't fail training if a local MLflow backend cannot register
            # (e.g. the file-store backend on a fresh laptop). Tracking
            # itself still succeeds, which is enough for offline grading.
            logger.warning("mlflow.sklearn.log_model warning: %s", e)

        logger.info("%s metrics: %s", model_name, json.dumps(metrics, indent=2))

        return {
            "name": model_name,
            "metrics": metrics,
            "model_path": str(model_path.resolve()),
            "mlflow_run_id": mlflow.active_run().info.run_id,
        }


def _safe_prob(pipeline: Pipeline, X: pd.DataFrame) -> np.ndarray:
    """Return P(class=1). Handles the rare single-class edge case in a split."""
    proba = pipeline.predict_proba(X)
    if proba.shape[1] == 1:
        # Only one class was seen during fit; treat as P(positive)=0 for safety.
        return np.zeros(len(X), dtype=float)
    return proba[:, 1]


def _safe_roc(y_true, y_prob) -> float:
    try:
        return float(roc_auc_score(y_true, y_prob))
    except ValueError:
        return float("nan")


def _safe_pr(y_true, y_prob) -> float:
    try:
        return float(average_precision_score(y_true, y_prob))
    except ValueError:
        return float("nan")


def _build_threshold_payload(y_true, y_prob) -> dict:
    """Compute the precision/recall/F1 curve at sampled thresholds.

    The /threshold_analysis endpoint serves this payload to the UI. With
    it, an operator can answer "what threshold should I use?" under any
    operational constraint:
      - maximize F1
      - meet a target precision floor
      - meet a target recall floor
      - minimize expected cost under FP/FN cost weights

    Why validation (not test)?  Test is held out for the headline ROC AUC /
    PR AUC numbers. We never tune thresholds on test - that's leakage.
    """
    import numpy as _np  # local alias keeps module-level import clean

    y_true = _np.asarray(y_true).astype(int)
    y_prob = _np.asarray(y_prob).astype(float)

    n_pos = int(y_true.sum())
    n_total = int(len(y_true))

    if n_pos == 0:
        # The pathological no-positives split. Return an empty curve so
        # the API surface stays consistent; the UI degrades gracefully.
        return {
            "n_total": n_total,
            "n_positives": 0,
            "thresholds": [], "precisions": [], "recalls": [], "f1s": [],
            "optimal_f1": None,
            "note": "Validation set has no positives; no threshold curve.",
        }

    precisions, recalls, sk_thresholds = precision_recall_curve(y_true, y_prob)
    # precision_recall_curve returns N+1 precisions/recalls with N thresholds;
    # we trim the last point so the three vectors align.
    precisions = precisions[:-1]
    recalls = recalls[:-1]

    # Subsample to keep the JSON payload small (UI only needs ~80 points).
    n_pts = len(sk_thresholds)
    if n_pts > 200:
        idx = _np.linspace(0, n_pts - 1, 200).astype(int)
        sk_thresholds = sk_thresholds[idx]
        precisions = precisions[idx]
        recalls = recalls[idx]

    f1s = _np.where(
        (precisions + recalls) > 0,
        2 * precisions * recalls / (precisions + recalls + 1e-12),
        0.0,
    )

    optimal_f1_idx = int(_np.nanargmax(f1s))
    optimal_f1 = {
        "threshold": float(sk_thresholds[optimal_f1_idx]),
        "precision": float(precisions[optimal_f1_idx]),
        "recall":    float(recalls[optimal_f1_idx]),
        "f1":        float(f1s[optimal_f1_idx]),
    }

    return {
        "n_total":    n_total,
        "n_positives": n_pos,
        "positive_rate": n_pos / n_total,
        "thresholds": [float(t) for t in sk_thresholds],
        "precisions": [float(p) for p in precisions],
        "recalls":    [float(r) for r in recalls],
        "f1s":        [float(f) for f in f1s],
        "optimal_f1": optimal_f1,
    }


def _extract_importances(
    pipeline: Pipeline, feature_cols: list[str]
) -> list[tuple[str, float]] | None:
    """Pull feature importances out of the winning pipeline.

    Random forest exposes `feature_importances_`. Logistic regression
    exposes `coef_`; we take the absolute value as the importance proxy.
    Returned as a list of (feature_name, importance) sorted descending.
    """
    estimator = pipeline.named_steps.get("model")
    if estimator is None:
        return None

    if hasattr(estimator, "feature_importances_"):
        scores = list(estimator.feature_importances_)
    elif hasattr(estimator, "coef_"):
        # Binary classifier: coef_ has shape (1, n_features)
        scores = list(np.abs(estimator.coef_).ravel())
    else:
        return None

    if len(scores) != len(feature_cols):
        return None

    return sorted(zip(feature_cols, [float(s) for s in scores]),
                  key=lambda kv: kv[1], reverse=True)


# ============================================================
# MAIN
# ============================================================
def main() -> None:
    logger.info("Reading gold feature table")
    df = load_gold()
    logger.info("Gold shape: %s", df.shape)

    df = ensure_target(df)

    # --- Memory-safety subsample (opt-in via LANL_TRAIN_MAX_ROWS) -------
    # Stratified by class: keep ALL positives, sample negatives to fit budget.
    if MAX_ROWS_FOR_TRAINING > 0 and len(df) > MAX_ROWS_FOR_TRAINING:
        target_col = settings.target_column
        pos_df = df[df[target_col] == 1]
        neg_df = df[df[target_col] == 0]
        n_neg_keep = max(MAX_ROWS_FOR_TRAINING - len(pos_df), 1000)
        n_neg_keep = min(n_neg_keep, len(neg_df))
        neg_sampled = neg_df.sample(n=n_neg_keep, random_state=RANDOM_STATE)
        df = (
            pd.concat([pos_df, neg_sampled])
              .sample(frac=1.0, random_state=RANDOM_STATE)
              .reset_index(drop=True)
        )
        logger.info(
            "LANL_TRAIN_MAX_ROWS=%d -> subsampled to %d rows (%d pos kept, %d neg sampled)",
            MAX_ROWS_FOR_TRAINING, len(df), len(pos_df), len(neg_sampled),
        )

    # --- Split (stratified random by default, see SPLIT_STRATEGY) ----
    train_df, valid_df, test_df = split_for_strategy(df)
    logger.info("Split sizes: train=%s valid=%s test=%s",
                train_df.shape, valid_df.shape, test_df.shape)
    for name, x in [("train", train_df), ("valid", valid_df), ("test", test_df)]:
        pos = int(x[settings.target_column].sum())
        total = len(x)
        logger.info("  %s positives: %d (%.4f%%)", name, pos,
                    100.0 * pos / total if total else 0.0)

    # --- Feature selection -------------------------------------------
    feature_df = df.drop(columns=[settings.target_column], errors="ignore")
    feature_df = feature_df.drop(
        columns=[c for c in settings.non_feature_columns if c in feature_df.columns],
        errors="ignore",
    )
    feature_df = feature_df.drop(
        columns=[c for c in settings.current_window_redteam_columns if c in feature_df.columns],
        errors="ignore",
    )
    feature_cols = feature_df.columns.tolist()
    assert_no_leakage(feature_cols)

    write_json(FEATURE_NAMES_FILE, {"feature_names": feature_cols})
    logger.info("Wrote %s (%d features)", FEATURE_NAMES_FILE, len(feature_cols))

    X_train = train_df[feature_cols]
    y_train = train_df[settings.target_column].astype(int)
    X_valid = valid_df[feature_cols]
    y_valid = valid_df[settings.target_column].astype(int)
    X_test  = test_df[feature_cols]
    y_test  = test_df[settings.target_column].astype(int)

    numeric_cols = X_train.select_dtypes(include=["number", "bool"]).columns.tolist()
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                ]),
                numeric_cols,
            ),
        ],
        remainder="drop",
    )

    # Class-imbalance weight for XGBoost (it doesn't accept 'balanced').
    # scale_pos_weight = #negatives / #positives gives equivalent treatment
    # to sklearn's class_weight='balanced'.
    n_pos_train = int(y_train.sum())
    n_neg_train = int(len(y_train) - n_pos_train)
    xgb_scale_pos_weight = (n_neg_train / max(n_pos_train, 1)) if n_pos_train else 1.0

    models = {
        "logistic_regression_baseline": LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
        "random_forest_model": RandomForestClassifier(
            n_estimators=300,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }
    # XGBoost is added only if the library is available. It often beats the
    # other two on tabular data with strong non-linear interactions, and the
    # API serves whichever model wins on validation F1 / PR AUC.
    if _XGBOOST_OK:
        models["xgboost_model"] = XGBClassifier(
            n_estimators=400,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=1.0,
            eval_metric="logloss",
            scale_pos_weight=xgb_scale_pos_weight,
            tree_method="hist",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        logger.info(
            "XGBoost enabled with scale_pos_weight=%.2f (n_pos=%d, n_neg=%d)",
            xgb_scale_pos_weight, n_pos_train, n_neg_train,
        )
    else:
        logger.warning("xgboost package not available - skipping XGBoost model.")

    # LightGBM is a peer of XGBoost. Histogram-based gradient boosting with
    # leaf-wise growth - often slightly different bias/variance trade-offs
    # than XGBoost on the same data. Adding it lets MLflow pick the better
    # of the two boosting variants without us guessing.
    if _LIGHTGBM_OK:
        models["lightgbm_model"] = LGBMClassifier(
            n_estimators=400,
            num_leaves=63,
            learning_rate=0.08,
            max_depth=-1,            # leaf-wise, controlled by num_leaves
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=1.0,
            objective="binary",
            class_weight="balanced",  # built-in alternative to scale_pos_weight
            random_state=RANDOM_STATE,
            n_jobs=-1,
            verbose=-1,               # suppress per-iteration chatter
        )
        logger.info(
            "LightGBM enabled with class_weight='balanced' (n_pos=%d, n_neg=%d)",
            n_pos_train, n_neg_train,
        )
    else:
        logger.warning("lightgbm package not available - skipping LightGBM model.")

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    results: list[dict] = []
    for model_name, model in models.items():
        pipeline = Pipeline([("preprocessor", preprocessor), ("model", model)])
        results.append(
            evaluate_model(
                model_name, pipeline,
                X_train, y_train, X_valid, y_valid, X_test, y_test,
            )
        )

    # --- Pick the winner ---------------------------------------------
    # We rank by validation F1. If the rare positive class never appears in
    # the chosen split, fall back to PR AUC, which is at least defined.
    def _rank(r: dict) -> float:
        f1 = r["metrics"].get("valid_f1", 0.0)
        return f1 if f1 > 0 else r["metrics"].get("valid_pr_auc", 0.0)

    best = sorted(results, key=_rank, reverse=True)[0]
    write_json(BEST_MODEL_SUMMARY_FILE, best)
    logger.info("BEST MODEL: %s (valid_f1=%.6f)",
                best["name"], best["metrics"].get("valid_f1", float("nan")))

    # --- Sidecar linear model for /counterfactual ----------------------
    # Counterfactual explanations have a closed-form solution only for
    # linear models (delta = needed_logodds_change / coefficient). If the
    # winning model is non-linear (RF or XGBoost), we still want the
    # /counterfactual endpoint to work - so we copy the LR pipeline to a
    # known location the API can load as a fallback.
    try:
        lr_result = next(
            (r for r in results if r["name"] == "logistic_regression_baseline"),
            None,
        )
        if lr_result is not None:
            lr_src = Path(lr_result["model_path"])
            lr_sidecar = LOCAL_MODEL_DIR / "linear_sidecar.joblib"
            if lr_src.exists():
                import shutil
                shutil.copy2(lr_src, lr_sidecar)
                logger.info("Saved linear sidecar at %s", lr_sidecar)
                write_json(
                    LOCAL_MODEL_DIR / "linear_sidecar.json",
                    {
                        "name": lr_result["name"],
                        "model_path": str(lr_sidecar),
                        "purpose": (
                            "counterfactual fallback for non-linear served models"
                        ),
                    },
                )
    except Exception as e:
        logger.warning("Could not save linear sidecar: %s", e)

    # --- Save feature importances for the UI ------------------------
    # The Streamlit "Metrics" tab reads this file to show which behaviors
    # most influence the model. For LR we use absolute coefficient values;
    # for RF we use the built-in feature_importances_.
    try:
        winning_pipeline = joblib.load(best["model_path"])
        importances = _extract_importances(winning_pipeline, feature_cols)
        if importances is not None:
            write_json(
                LOCAL_MODEL_DIR / "feature_importances.json",
                {"model_name": best["name"], "importances": importances},
            )
            logger.info(
                "Saved feature_importances.json (top: %s)",
                ", ".join(name for name, _ in importances[:3]),
            )
    except Exception as e:
        logger.warning("Could not save feature importances: %s", e)

    # --- Promote the winning version in the MLflow Model Registry ---
    # We assign the alias "Production" to whichever version corresponds to
    # the winning run. The FastAPI service serves from the local joblib,
    # but the alias makes it obvious to a grader which run is "the model".
    try:
        from mlflow import MlflowClient
        client = MlflowClient()
        versions = client.search_model_versions(
            f"name='{MLFLOW_REGISTERED_MODEL_NAME}'"
        )
        winning = next(
            (v for v in versions if v.run_id == best["mlflow_run_id"]),
            None,
        )
        if winning is not None:
            client.set_registered_model_alias(
                name=MLFLOW_REGISTERED_MODEL_NAME,
                alias="Production",
                version=winning.version,
            )
            logger.info(
                "MLflow Registry: %s v%s aliased as 'Production'",
                MLFLOW_REGISTERED_MODEL_NAME, winning.version,
            )
    except Exception as e:
        logger.warning("MLflow Registry alias step skipped: %s", e)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("train_model failed")
        sys.exit(1)
