from pathlib import Path
import json
import sys

import joblib
import pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score

from jobs.train_model import (
    load_gold,
    ensure_target,
    split_for_strategy,
    settings,
    MAX_ROWS_FOR_TRAINING,
    RANDOM_STATE,
)


PROJECT_ROOT = Path(__file__).resolve().parent

MODEL_PATH = PROJECT_ROOT / "model_outputs" / "lightgbm_model" / "lightgbm_model.joblib"
FEATURE_NAMES_PATH = PROJECT_ROOT / "model_outputs" / "feature_names.json"
OUTPUT_PATH = PROJECT_ROOT / "model_outputs" / "lightgbm_model" / "validation_test_predictions.csv"


def debug(message):
    print(f"[EXPORT LGBM PREDICTIONS] {message}")


def apply_training_subsample_if_needed(df):
    """
    Match the optional subsampling logic used in jobs/train_model.py.

    This only activates if LANL_TRAIN_MAX_ROWS was set when this script starts.
    If your original model was trained on full data, leave LANL_TRAIN_MAX_ROWS unset.
    """
    if MAX_ROWS_FOR_TRAINING <= 0 or len(df) <= MAX_ROWS_FOR_TRAINING:
        debug("No LANL_TRAIN_MAX_ROWS subsample applied.")
        return df

    target_col = settings.target_column

    pos_df = df[df[target_col] == 1]
    neg_df = df[df[target_col] == 0]

    n_neg_keep = max(MAX_ROWS_FOR_TRAINING - len(pos_df), 1000)
    n_neg_keep = min(n_neg_keep, len(neg_df))

    neg_sampled = neg_df.sample(n=n_neg_keep, random_state=RANDOM_STATE)

    out = (
        pd.concat([pos_df, neg_sampled])
        .sample(frac=1.0, random_state=RANDOM_STATE)
        .reset_index(drop=True)
    )

    debug(
        f"LANL_TRAIN_MAX_ROWS={MAX_ROWS_FOR_TRAINING} -> "
        f"subsampled to {len(out):,} rows "
        f"({len(pos_df):,} positives kept, {len(neg_sampled):,} negatives sampled)"
    )

    return out


def load_feature_names():
    if not FEATURE_NAMES_PATH.exists():
        raise FileNotFoundError(f"Missing feature names file: {FEATURE_NAMES_PATH}")

    payload = json.loads(FEATURE_NAMES_PATH.read_text(encoding="utf-8"))

    if isinstance(payload, dict) and "feature_names" in payload:
        return payload["feature_names"]

    if isinstance(payload, list):
        return payload

    raise ValueError(
        f"Unexpected feature_names.json format. Expected dict with feature_names or list. Got: {type(payload)}"
    )


def safe_prob(model, X):
    proba = model.predict_proba(X)

    if proba.shape[1] == 1:
        return [0.0] * len(X)

    return proba[:, 1]


def make_prediction_frame(model, split_name, df, feature_cols):
    target_col = settings.target_column

    X = df[feature_cols]
    y = df[target_col].astype(int)

    y_score = safe_prob(model, X)

    out = pd.DataFrame(
        {
            "model": "LightGBM",
            "split": split_name,
            "y_true": y.values,
            "y_score": y_score,
        }
    )

    roc_auc = roc_auc_score(out["y_true"], out["y_score"])
    pr_auc = average_precision_score(out["y_true"], out["y_score"])

    debug(
        f"{split_name}: rows={len(out):,}, "
        f"positives={int(out['y_true'].sum()):,}, "
        f"ROC-AUC={roc_auc:.6f}, PR-AUC={pr_auc:.6f}"
    )

    return out


def main():
    debug("Starting LightGBM prediction export.")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Missing LightGBM model: {MODEL_PATH}")

    feature_cols = load_feature_names()
    debug(f"Loaded {len(feature_cols)} feature names.")

    debug("Loading gold data using jobs.train_model.load_gold().")
    df = load_gold()
    debug(f"Loaded gold data: {df.shape}")

    df = ensure_target(df)
    df = apply_training_subsample_if_needed(df)

    missing_features = [c for c in feature_cols if c not in df.columns]
    if missing_features:
        raise ValueError(
            "Gold data is missing feature columns required by the saved model:\n"
            + "\n".join(missing_features[:50])
        )

    debug("Recreating train/validation/test split.")
    train_df, valid_df, test_df = split_for_strategy(df)

    debug(f"Train shape: {train_df.shape}")
    debug(f"Validation shape: {valid_df.shape}")
    debug(f"Test shape: {test_df.shape}")

    for name, split_df in [
        ("train", train_df),
        ("validation", valid_df),
        ("test", test_df),
    ]:
        positives = int(split_df[settings.target_column].sum())
        debug(f"{name} positives: {positives:,}")

    debug(f"Loading model: {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)

    valid_pred = make_prediction_frame(model, "validation", valid_df, feature_cols)
    test_pred = make_prediction_frame(model, "test", test_df, feature_cols)

    all_pred = pd.concat([valid_pred, test_pred], ignore_index=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_pred.to_csv(OUTPUT_PATH, index=False)

    debug(f"Saved row-level LightGBM predictions to: {OUTPUT_PATH}")
    debug(f"Total rows saved: {len(all_pred):,}")
    debug("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\n[EXPORT LGBM PREDICTIONS] ERROR")
        print(exc)
        sys.exit(1)