from pathlib import Path
import argparse
import json
import shutil

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import (
    roc_curve,
    precision_recall_curve,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    ConfusionMatrixDisplay,
)


PROJECT_ROOT = Path(__file__).resolve().parent

OUTPUT_DIR = PROJECT_ROOT / "reports" / "figures" / "lgbm_diagnostics"
PRESENTATION_ASSET_DIR = PROJECT_ROOT / "presentation_ml_final" / "assets" / "lgbm_diagnostics"

DEFAULT_THRESHOLD = 0.10

PREDICTION_FILE_CANDIDATES = [
    PROJECT_ROOT / "gold_outputs" / "model_predictions.csv",
    PROJECT_ROOT / "gold_outputs" / "predictions.csv",
    PROJECT_ROOT / "gold_outputs" / "test_predictions.csv",
    PROJECT_ROOT / "gold_outputs" / "model_predictions.parquet",
    PROJECT_ROOT / "gold_outputs" / "predictions.parquet",
    PROJECT_ROOT / "gold_outputs" / "test_predictions.parquet",
    PROJECT_ROOT / "data" / "processed" / "model_predictions.parquet",
    PROJECT_ROOT / "data" / "processed" / "predictions.parquet",
    PROJECT_ROOT / "reports" / "model_predictions.parquet",
    PROJECT_ROOT / "reports" / "predictions.parquet",
    PROJECT_ROOT / "presentation_ml_final" / "model_predictions.csv",
]


def debug(message):
    print(f"[LGBM DIAGNOSTICS] {message}")


def read_table(path):
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path)

    if suffix == ".parquet":
        return pd.read_parquet(path)

    raise ValueError(f"Unsupported file type: {path}")


def find_prediction_file(user_path=None):
    if user_path is not None:
        path = Path(user_path)

        if not path.is_absolute():
            path = PROJECT_ROOT / path

        if not path.exists():
            raise FileNotFoundError(f"Provided prediction file does not exist: {path}")

        return path

    for path in PREDICTION_FILE_CANDIDATES:
        if path.exists():
            return path

    raise FileNotFoundError(
        "No prediction file was found automatically.\n\n"
        "Run this script again with:\n"
        "py -3 make_lgbm_diagnostics.py --predictions path/to/predictions.csv\n\n"
        "Checked these paths:\n"
        + "\n".join(str(p) for p in PREDICTION_FILE_CANDIDATES)
    )


def find_column(df, exact_names, contains_tokens=None):
    lower_map = {col.lower(): col for col in df.columns}

    for name in exact_names:
        if name.lower() in lower_map:
            return lower_map[name.lower()]

    if contains_tokens is not None:
        for col in df.columns:
            col_lower = col.lower()
            for token in contains_tokens:
                if token in col_lower:
                    return col

    raise KeyError(
        "Could not find required column.\n"
        f"Tried exact names: {exact_names}\n"
        f"Tried contains tokens: {contains_tokens}\n"
        f"Available columns: {list(df.columns)}"
    )


def optional_column(df, exact_names, contains_tokens=None):
    try:
        return find_column(df, exact_names, contains_tokens)
    except KeyError:
        return None


def normalize_split(value):
    text = str(value).strip().lower()

    if text in ["valid", "validation", "val"]:
        return "validation"

    if text in ["test", "testing", "heldout", "held_out", "holdout"]:
        return "test"

    if text in ["train", "training"]:
        return "train"

    return text


def compute_metrics(y_true, y_score, threshold):
    y_true = y_true.astype(int)
    y_score = y_score.astype(float)

    y_pred = (y_score >= threshold).astype(int)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    false_negative_rate = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "threshold": float(threshold),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
        "precision": float(precision),
        "recall": float(recall),
        "specificity": float(specificity),
        "false_positive_rate": float(false_positive_rate),
        "false_negative_rate": float(false_negative_rate),
        "f1": float(f1),
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "pr_auc": float(average_precision_score(y_true, y_score)),
        "positive_rate": float(y_true.mean()),
        "n_rows": int(len(y_true)),
        "n_positive": int(y_true.sum()),
        "n_negative": int((1 - y_true).sum()),
    }


def plot_roc_curve(y_true, y_score, split_name, metrics):
    fpr, tpr, _ = roc_curve(y_true, y_score)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(fpr, tpr, label=f"LightGBM ROC-AUC = {metrics['roc_auc']:.3f}")
    ax.plot([0, 1], [0, 1], linestyle="--", label="Random")
    ax.set_title(f"LightGBM ROC Curve ({split_name.title()} Split)")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate / Recall")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    out_path = OUTPUT_DIR / f"lgbm_roc_{split_name}.png"
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return out_path


def plot_pr_curve(y_true, y_score, split_name, metrics):
    precision, recall, _ = precision_recall_curve(y_true, y_score)
    base_rate = y_true.mean()

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(recall, precision, label=f"LightGBM PR-AUC = {metrics['pr_auc']:.5f}")
    ax.axhline(base_rate, linestyle="--", label=f"Random baseline = {base_rate:.6f}")
    ax.set_title(f"LightGBM Precision-Recall Curve ({split_name.title()} Split)")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    out_path = OUTPUT_DIR / f"lgbm_pr_{split_name}.png"
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return out_path


def plot_confusion_matrix(y_true, y_score, split_name, metrics):
    y_pred = (y_score >= metrics["threshold"]).astype(int)

    cm = confusion_matrix(y_true.astype(int), y_pred, labels=[0, 1])

    fig, ax = plt.subplots(figsize=(6, 5))
    disp = ConfusionMatrixDisplay(
        confusion_matrix=cm,
        display_labels=["No Attack", "Attack"],
    )
    disp.plot(ax=ax, values_format="d", colorbar=False)
    ax.set_title(
        f"LightGBM Confusion Matrix ({split_name.title()} Split)\n"
        f"Threshold = {metrics['threshold']:.3f}"
    )
    fig.tight_layout()

    out_path = OUTPUT_DIR / f"lgbm_confusion_matrix_{split_name}.png"
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return out_path


def copy_pngs_to_presentation_assets(paths):
    PRESENTATION_ASSET_DIR.mkdir(parents=True, exist_ok=True)

    for path in paths:
        if path.suffix.lower() == ".png":
            shutil.copy2(path, PRESENTATION_ASSET_DIR / path.name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--predictions",
        default=None,
        help="Path to row-level LightGBM prediction file. CSV or Parquet.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="Classification threshold for confusion matrices.",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    prediction_path = find_prediction_file(args.predictions)

    debug(f"Reading prediction file: {prediction_path}")
    df = read_table(prediction_path)

    debug(f"Rows loaded: {len(df):,}")
    debug(f"Columns: {list(df.columns)}")

    model_col = optional_column(
        df,
        ["model", "model_name", "estimator", "algorithm"],
        contains_tokens=["model"],
    )

    split_col = find_column(
        df,
        ["split", "dataset", "sample", "fold"],
        contains_tokens=["split"],
    )

    y_true_col = find_column(
        df,
        ["y_true", "target", "label", "actual", "target_redteam_next_window"],
        contains_tokens=["target", "label", "actual"],
    )

    score_col = find_column(
        df,
        [
            "y_score",
            "score",
            "probability",
            "pred_proba",
            "y_pred_proba",
            "prediction_probability",
            "attack_probability",
            "risk_score",
        ],
        contains_tokens=["proba", "prob", "score", "risk"],
    )

    work = df.copy()

    if model_col is not None:
        work = work[
            work[model_col].astype(str).str.lower().str.contains("lightgbm", na=False)
        ].copy()

        debug(f"Rows after LightGBM filter: {len(work):,}")

    if work.empty:
        raise ValueError(
            "No LightGBM rows found. Check your model column or prediction file."
        )

    work["_split_norm"] = work[split_col].map(normalize_split)

    generated_paths = []
    summary_rows = []

    for split_name in ["validation", "test"]:
        split_df = work[work["_split_norm"] == split_name].copy()

        if split_df.empty:
            debug(f"WARNING: No rows found for split={split_name}. Skipping.")
            continue

        y_true = split_df[y_true_col].astype(int)
        y_score = split_df[score_col].astype(float)

        if y_true.nunique() < 2:
            debug(
                f"WARNING: split={split_name} has only one class. "
                "ROC/PR curves are undefined. Skipping."
            )
            continue

        metrics = compute_metrics(y_true, y_score, args.threshold)
        metrics["model"] = "LightGBM"
        metrics["split"] = split_name
        metrics["prediction_file"] = str(prediction_path)

        debug(
            f"{split_name}: "
            f"ROC-AUC={metrics['roc_auc']:.4f}, "
            f"PR-AUC={metrics['pr_auc']:.6f}, "
            f"TP={metrics['true_positive']}, "
            f"FP={metrics['false_positive']}, "
            f"FN={metrics['false_negative']}, "
            f"TN={metrics['true_negative']}"
        )

        roc_path = plot_roc_curve(y_true, y_score, split_name, metrics)
        pr_path = plot_pr_curve(y_true, y_score, split_name, metrics)
        cm_path = plot_confusion_matrix(y_true, y_score, split_name, metrics)

        generated_paths.extend([roc_path, pr_path, cm_path])
        summary_rows.append(metrics)

        with open(
            OUTPUT_DIR / f"lgbm_metrics_{split_name}.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(metrics, f, indent=2)

    if not summary_rows:
        raise RuntimeError(
            "No diagnostics were generated. Check split labels and model filters."
        )

    summary_df = pd.DataFrame(summary_rows)

    summary_csv = OUTPUT_DIR / "lgbm_diagnostics_summary.csv"
    summary_json = OUTPUT_DIR / "lgbm_diagnostics_summary.json"

    summary_df.to_csv(summary_csv, index=False)

    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary_rows, f, indent=2)

    generated_paths.extend([summary_csv, summary_json])

    copy_pngs_to_presentation_assets(generated_paths)

    debug("Saved files:")
    for path in generated_paths:
        debug(str(path))

    debug(f"Copied PNG files to: {PRESENTATION_ASSET_DIR}")
    debug("Done.")


if __name__ == "__main__":
    main()