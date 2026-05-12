"""
scripts/find_demo_presets.py
============================

Scan the gold sample table, score every row with the currently-deployed
model, and pick three representative rows at LOW / MEDIUM / HIGH predicted
risk. Prints them as Python dict literals ready to paste into
`app/streamlit_app.py`'s PRESETS dictionary.

The point of this script:
    The "Suspicious - failed-logon storm" / "lateral movement" presets in
    the app were calibrated when LR was serving and don't fire on the
    LightGBM model. LightGBM learned specific attack fingerprints from
    real positives; synthetic guesses don't match them. This script
    sources presets from REAL rows the model rates at the desired level,
    so the demo can show meaningful probability changes.

Run:
    py scripts/find_demo_presets.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO_ROOT / "model_outputs"
GOLD_CSV  = REPO_ROOT / "gold_outputs" / "gold_computer_time_sample.csv"


def _format_preset(name: str, prob: float, raw_row: pd.Series,
                   feature_names: list[str]) -> str:
    """Return a Python-source string for one PRESETS entry."""
    # Only include features that are non-zero — keeps the dict readable
    nonzero = {
        col: float(raw_row[col])
        for col in feature_names
        if col in raw_row.index and raw_row[col] != 0
    }
    pairs = ",\n        ".join(
        f'"{col}": {val:g}' for col, val in nonzero.items()
    )
    return (
        f'    "{name}  (P={prob:.3f})": {{\n'
        f'        {pairs},\n'
        f'    }},'
    )


def main() -> int:
    if not GOLD_CSV.exists():
        print(f"ERROR: gold sample not found at {GOLD_CSV}", file=sys.stderr)
        return 1

    # ---- Load model + feature contract -----------------------------
    summary = json.loads(
        (MODEL_DIR / "best_model_summary.json").read_text(encoding="utf-8")
    )
    model_name = summary["name"]
    feature_names = json.loads(
        (MODEL_DIR / "feature_names.json").read_text(encoding="utf-8")
    )["feature_names"]
    model_path = MODEL_DIR / model_name / f"{model_name}.joblib"
    print(f"Loading model: {model_name}")
    model = joblib.load(model_path)

    # ---- Load data ---------------------------------------------------
    df = pd.read_csv(GOLD_CSV)
    print(f"Gold sample shape: {df.shape}")

    # Build feature frame in the model's expected column order; missing
    # columns default to 0 (matches the API's contract).
    X = pd.DataFrame(
        {col: df[col] if col in df.columns else 0.0 for col in feature_names}
    )

    # ---- Score every row --------------------------------------------
    print("Scoring all rows...")
    try:
        probs = model.predict_proba(X)[:, 1]
    except Exception as e:
        print(f"ERROR: predict_proba failed: {e}", file=sys.stderr)
        return 1
    df["__p"] = probs

    p_min, p_mean, p_max = float(probs.min()), float(probs.mean()), float(probs.max())
    print(f"Probability distribution: min={p_min:.6f} mean={p_mean:.6f} max={p_max:.6f}")
    print(f"Quantiles: 50%={np.quantile(probs, 0.5):.6f}  "
          f"90%={np.quantile(probs, 0.9):.6f}  "
          f"99%={np.quantile(probs, 0.99):.6f}  "
          f"99.9%={np.quantile(probs, 0.999):.6f}")

    # ---- Pick the three representative rows -------------------------
    # HIGH: top-ranked row by probability
    high_idx = df["__p"].idxmax()

    # MEDIUM: the row whose probability is closest to the 99th percentile.
    # (The 50th percentile is usually ~0 with this much imbalance; the
    # 99th gives us a row the model is genuinely uncertain about.)
    target_med = float(np.quantile(probs, 0.99))
    med_idx = (df["__p"] - target_med).abs().idxmin()

    # LOW: a row well below threshold but with some non-zero features
    # (not all-zeros - all-zero rows look like a placeholder, not a host).
    nonzero_per_row = (X > 0).sum(axis=1)
    low_mask = (df["__p"] < float(np.quantile(probs, 0.30))) & (nonzero_per_row >= 5)
    low_idx = df[low_mask]["__p"].idxmin() if low_mask.any() else df["__p"].idxmin()

    print("\n=" * 30)
    print("Paste these into PRESETS in app/streamlit_app.py:")
    print("=" * 60)

    blocks = [
        _format_preset(
            "Demo HIGH risk (real row)",
            float(df.loc[high_idx, "__p"]),
            df.loc[high_idx], feature_names,
        ),
        _format_preset(
            "Demo MEDIUM risk (real row)",
            float(df.loc[med_idx, "__p"]),
            df.loc[med_idx], feature_names,
        ),
        _format_preset(
            "Demo LOW risk (real row)",
            float(df.loc[low_idx, "__p"]),
            df.loc[low_idx], feature_names,
        ),
    ]
    print("PRESETS_REAL: dict[str, dict[str, float]] = {")
    print("\n".join(blocks))
    print("}")

    print("\n=" * 30)
    print(f"  HIGH row idx={high_idx}  P={df.loc[high_idx, '__p']:.4f}")
    print(f"  MED  row idx={med_idx}   P={df.loc[med_idx, '__p']:.4f}")
    print(f"  LOW  row idx={low_idx}   P={df.loc[low_idx, '__p']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
