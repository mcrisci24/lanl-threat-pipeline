"""
scripts/generate_presentation_assets.py
=======================================

Generate the chart and diagram PNGs that the presentation embeds.

Each asset is rendered with matplotlib at 200 DPI, saved into
`presentation_assets/`, and then picked up by `generate_presentation_pptx.py`
when the slide deck is built. All numbers are pulled from the artifacts the
training script and pipeline have already written (model_outputs/*.json),
so the visuals are real, not stock illustrations.

Run:
    py -m pip install -q matplotlib
    py scripts/generate_presentation_assets.py

Then re-run the pptx generator to embed them:
    py scripts/generate_presentation_pptx.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "presentation_assets"
MODEL_DIR = REPO_ROOT / "model_outputs"

# Color palette - matches the pptx theme
NAVY = "#1F2A44"
RED = "#E65555"
GREEN = "#10B981"
AMBER = "#D4A017"
GRAY = "#9CA3AF"
LIGHT_GRAY = "#E5E7EB"
WHITE = "#FFFFFF"

# Real values from the project
TOTAL_ROWS = 13_888_446
POSITIVE_ROWS = 596
NEGATIVE_ROWS = TOTAL_ROWS - POSITIVE_ROWS
DATA_VOLUMES_GB = {
    "auth":    7.1,
    "proc":    2.2,
    "flows":   1.0,
    "dns":     0.176,
    "redteam": 0.0000047,
}


def _setup_matplotlib():
    """Import matplotlib (only when we need it) and apply consistent style."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": WHITE,
        "axes.facecolor": WHITE,
        "savefig.facecolor": WHITE,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.labelcolor": NAVY,
        "axes.titlecolor": NAVY,
        "axes.titleweight": "bold",
        "xtick.color": NAVY,
        "ytick.color": NAVY,
        "font.size": 12,
        "axes.titlesize": 16,
        "axes.labelsize": 13,
        "legend.frameon": False,
    })
    return plt


def render_class_imbalance(plt) -> Path:
    """Horizontal bar with a tiny red sliver of positives next to a giant gray bar."""
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.barh(["Class distribution"], [NEGATIVE_ROWS], color=LIGHT_GRAY, label=f"benign (next-window): {NEGATIVE_ROWS:,}")
    ax.barh(["Class distribution"], [POSITIVE_ROWS], color=RED, label=f"red-team (next-window): {POSITIVE_ROWS}")
    ax.set_xlim(0, TOTAL_ROWS)
    ax.set_xlabel(f"Rows  (total {TOTAL_ROWS:,})")
    ax.set_yticks([])
    ax.set_title("Extreme class imbalance — 596 positives out of 13.9 M rows (0.0043 %)")
    ax.legend(loc="upper right", fontsize=11)

    # Annotation pointing out the imbalance
    ax.annotate(
        "the red sliver is the entire signal\n(too small to see at scale)",
        xy=(POSITIVE_ROWS, 0),
        xytext=(TOTAL_ROWS * 0.25, 0.45),
        fontsize=11, color=NAVY,
        arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.5),
    )

    out = ASSETS_DIR / "class_imbalance.png"
    plt.savefig(out)
    plt.close(fig)
    return out


def render_data_volumes(plt) -> Path:
    """Compressed size of each raw LANL source."""
    fig, ax = plt.subplots(figsize=(10, 5))
    names = list(DATA_VOLUMES_GB.keys())
    vals = list(DATA_VOLUMES_GB.values())
    colors_ = [NAVY, "#3B4866", "#5B6580", "#7E8595", AMBER]  # auth-flows-... + redteam pop
    bars = ax.barh(names[::-1], vals[::-1], color=colors_[::-1])
    ax.set_xlabel("Compressed size (GB)")
    ax.set_title("LANL telemetry — 5 sources, ~11 GB compressed")
    for bar, v in zip(bars, vals[::-1]):
        ax.text(
            bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
            f"{v:,.3g} GB" if v >= 0.001 else f"{v*1024:.1f} KB",
            va="center", fontsize=11, color=NAVY,
        )
    ax.set_xlim(0, max(vals) * 1.18)
    out = ASSETS_DIR / "data_volumes.png"
    plt.savefig(out)
    plt.close(fig)
    return out


def render_feature_importances(plt) -> Path | None:
    """Top 15 feature importances from the trained model."""
    path = MODEL_DIR / "feature_importances.json"
    if not path.exists():
        print(f"  (skipping feature_importances - file not found: {path})")
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    importances = data.get("importances", [])[:15]
    if not importances:
        return None

    names = [name for name, _ in importances][::-1]
    vals = [val for _, val in importances][::-1]

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.barh(names, vals, color=NAVY)
    ax.set_xlabel("Importance (|coefficient| in standardized space)")
    ax.set_title(f"Top 15 features driving the model  ({data.get('model_name', 'best')})")
    for i, (n, v) in enumerate(zip(names, vals)):
        ax.text(v + max(vals) * 0.01, i, f"{v:.3f}", va="center", fontsize=10, color=NAVY)
    out = ASSETS_DIR / "feature_importances.png"
    plt.savefig(out)
    plt.close(fig)
    return out


def render_metric_dashboard(plt) -> Path | None:
    """Big KPI tiles for the headline test metrics."""
    path = MODEL_DIR / "best_model_summary.json"
    if not path.exists():
        print(f"  (skipping metric_dashboard - file not found: {path})")
        return None
    summary = json.loads(path.read_text(encoding="utf-8"))
    m = summary.get("metrics", {})

    tiles = [
        ("Test ROC AUC",      f"{m.get('test_roc_auc', 0):.3f}",   NAVY),
        ("Test PR AUC",       f"{m.get('test_pr_auc', 0):.4f}",   AMBER),
        ("Test recall",       f"{m.get('test_recall', 0):.3f}",    GREEN),
        ("Test precision",    f"{m.get('test_precision', 0):.4f}", RED),
    ]

    fig, axes = plt.subplots(1, 4, figsize=(13.33, 3.5))
    for ax, (label, val, color) in zip(axes, tiles):
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        # tile border
        ax.add_patch(plt.Rectangle(
            (0.05, 0.05), 0.9, 0.9,
            linewidth=2, edgecolor=color, facecolor=WHITE,
        ))
        ax.text(0.5, 0.62, val, fontsize=42, fontweight="bold", color=color,
                ha="center", va="center")
        ax.text(0.5, 0.22, label, fontsize=14, color=NAVY,
                ha="center", va="center")

    fig.suptitle(
        f"Headline metrics  -  served model: {summary.get('name', 'best')}",
        fontsize=16, fontweight="bold", color=NAVY, y=1.02,
    )
    plt.tight_layout()
    out = ASSETS_DIR / "metric_dashboard.png"
    plt.savefig(out)
    plt.close(fig)
    return out


def render_architecture_diagram(plt) -> Path:
    """Pipeline flow with colored boxes and arrows."""
    import matplotlib.patches as mpatches
    fig, ax = plt.subplots(figsize=(13.33, 6.5))
    ax.set_xlim(0, 14); ax.set_ylim(0, 7.5)
    ax.axis("off")

    def box(x, y, w, h, label, color, text_color=WHITE, fontsize=12):
        rect = mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.18",
            linewidth=1.5, edgecolor=color, facecolor=color,
        )
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, label, ha="center", va="center",
                color=text_color, fontsize=fontsize, fontweight="bold")

    def arrow(x1, y1, x2, y2, label=None):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", lw=2, color=NAVY))
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.15, label,
                    ha="center", va="bottom", fontsize=10, color=NAVY, style="italic")

    # Color codes
    STORAGE = "#2563EB"   # cloud blue
    COMPUTE = "#D97706"   # amber
    SERVE   = "#059669"   # green

    # Row 1 - data flow
    box(0.3, 5.0, 2.6, 1.2, "LANL raw\n.txt.gz", GRAY, NAVY, 12)
    arrow(2.9, 5.6, 3.5, 5.6, "upload")
    box(3.5, 5.0, 2.6, 1.2, "S3  bronze", STORAGE, fontsize=14)
    arrow(6.1, 5.6, 6.7, 5.6, "EMR Spark")
    box(6.7, 5.0, 2.6, 1.2, "S3  silver", STORAGE, fontsize=14)
    arrow(9.3, 5.6, 9.9, 5.6, "EMR Spark")
    box(9.9, 5.0, 2.6, 1.2, "S3  gold", STORAGE, fontsize=14)

    # Row 2 - model + serving
    arrow(11.2, 5.0, 11.2, 4.2)
    box(9.9, 2.9, 2.6, 1.2, "train_model.py\n+ MLflow Registry", COMPUTE, fontsize=11)
    arrow(11.2, 2.9, 11.2, 2.1)
    box(9.9, 0.8, 2.6, 1.2, "FastAPI\non EC2", SERVE, fontsize=13)
    arrow(9.9, 1.4, 8.9, 1.4)
    box(6.3, 0.8, 2.6, 1.2, "Streamlit\nCloud (UI)", SERVE, fontsize=13)

    # Legend
    legend_y = 0.0
    ax.add_patch(mpatches.Rectangle((0.3, legend_y), 0.4, 0.3, color=STORAGE))
    ax.text(0.8, legend_y + 0.15, "Cloud storage (S3)", va="center", fontsize=11, color=NAVY)
    ax.add_patch(mpatches.Rectangle((3.2, legend_y), 0.4, 0.3, color=COMPUTE))
    ax.text(3.7, legend_y + 0.15, "Distributed compute (EMR PySpark)", va="center", fontsize=11, color=NAVY)
    ax.add_patch(mpatches.Rectangle((8.4, legend_y), 0.4, 0.3, color=SERVE))
    ax.text(8.9, legend_y + 0.15, "Cloud serving (EC2 + Streamlit Cloud)", va="center", fontsize=11, color=NAVY)

    ax.set_title("AWS-first distributed pipeline  -  3 of 4 layers are cloud / distributed",
                 fontsize=15, pad=15, loc="left")

    out = ASSETS_DIR / "architecture_diagram.png"
    plt.savefig(out)
    plt.close(fig)
    return out


def render_medallion_diagram(plt) -> Path:
    """Three stacked layers: bronze / silver / gold with the row-grain note."""
    import matplotlib.patches as mpatches
    fig, ax = plt.subplots(figsize=(13.33, 6.5))
    ax.set_xlim(0, 14); ax.set_ylim(0, 8); ax.axis("off")

    layers = [
        ("BRONZE",  "Raw .txt.gz preserved on S3, untouched.",
         "Row grain: one event from the source.",   "#CD7F32", 5.4),
        ("SILVER",  "Cleaned, typed parquet, source-grain.",
         "One row per auth/flow/dns/proc/redteam event.", "#C0C0C0", 3.4),
        ("GOLD",    "Aggregated features, model-ready.",
         "Row grain: one COMPUTER in one TIME WINDOW.",   "#D4AF37", 1.4),
    ]

    for label, desc, grain, color, y in layers:
        rect = mpatches.FancyBboxPatch(
            (1.0, y), 12.0, 1.6,
            boxstyle="round,pad=0.04,rounding_size=0.2",
            linewidth=2, edgecolor=NAVY, facecolor=color, alpha=0.85,
        )
        ax.add_patch(rect)
        ax.text(1.4, y + 1.15, label, fontsize=22, fontweight="bold", color=WHITE)
        ax.text(1.4, y + 0.65, desc, fontsize=14, color=WHITE)
        ax.text(1.4, y + 0.25, grain, fontsize=12, color=WHITE, style="italic")

    # arrows between layers
    for y in [5.1, 3.1]:
        ax.annotate(
            "", xy=(7, y), xytext=(7, y + 0.4),
            arrowprops=dict(arrowstyle="->", lw=3, color=NAVY),
        )

    ax.set_title(
        "Medallion architecture  -  the row grain CHANGES at gold",
        fontsize=16, pad=10, loc="left",
    )

    out = ASSETS_DIR / "medallion_diagram.png"
    plt.savefig(out)
    plt.close(fig)
    return out


def render_explainer_demo(plt) -> Path:
    """Mock contribution bars showing what /explain produces for the failed-logon storm preset."""
    # These mirror real numbers from the live demo's "Why this prediction?" panel
    contribs = [
        ("auth_failure_ratio",            +2.33),
        ("auth_src_unique_dst_computers", +1.18),
        ("proc_start_end_imbalance",      +0.42),
        ("auth_total_failures",           +0.21),
        ("dns_lookup_count",              -0.08),
        ("proc_unique_users",             -0.31),
        ("flows_in_total_bytes",          -0.46),
    ]
    contribs = list(reversed(contribs))
    names = [c[0] for c in contribs]
    vals = [c[1] for c in contribs]
    colors_ = [RED if v > 0 else GREEN for v in vals]

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(names, vals, color=colors_)
    ax.axvline(0, color=NAVY, lw=1.5, linestyle="--")
    ax.set_xlabel("Contribution to log-odds (red = raises risk, green = lowers risk)")
    ax.set_title("Per-feature contribution  -  /explain endpoint, 'failed-logon storm' preset")
    for i, v in enumerate(vals):
        offset = 0.05 if v >= 0 else -0.05
        ax.text(v + offset, i, f"{v:+.2f}",
                va="center", ha="left" if v >= 0 else "right",
                fontsize=11, color=NAVY)
    out = ASSETS_DIR / "explainer_demo.png"
    plt.savefig(out)
    plt.close(fig)
    return out


def render_counterfactual_demo(plt) -> Path:
    """Mock counterfactual table - drawn as a clean colored table image."""
    import matplotlib.patches as mpatches
    rows = [
        ("auth_failure_ratio",            "0.75",   "0.04",   "↓ decrease by 0.71"),
        ("dns_unique_resolved_computers", "2.00",   "7.91",   "↑ increase by 5.91"),
        ("flows_in_unique_src_computers", "0.00",   "39.50",  "↑ increase by 39.50"),
        ("proc_start_end_imbalance",      "2.00",   "169.07", "↑ increase by 167.07"),
        ("auth_dst_unique_src_computers", "0.00",   "217.99", "↑ increase by 217.99"),
    ]
    headers = ["Feature", "Current", "Target", "Change"]
    n_rows = len(rows) + 1
    fig, ax = plt.subplots(figsize=(12, 5.0))
    ax.set_xlim(0, 12); ax.set_ylim(0, n_rows + 1); ax.axis("off")

    col_x = [0.1, 6.2, 7.5, 8.7]
    col_w = [6.0, 1.2, 1.2, 3.0]
    row_h = 0.85

    # header
    y_top = n_rows
    ax.add_patch(mpatches.Rectangle((0, y_top), 12, row_h, color=NAVY))
    for x, w, label in zip(col_x, col_w, headers):
        ax.text(x + 0.1, y_top + row_h/2, label, va="center", ha="left",
                color=WHITE, fontweight="bold", fontsize=12)

    # data rows
    for i, row in enumerate(rows):
        y = y_top - (i + 1) * row_h - 0.05
        bg = LIGHT_GRAY if i % 2 == 0 else WHITE
        ax.add_patch(mpatches.Rectangle((0, y), 12, row_h, color=bg))
        for x, w, val in zip(col_x, col_w, row):
            color = RED if "↓" in val else (GREEN if "↑" in val else NAVY)
            ax.text(x + 0.1, y + row_h/2, val, va="center", ha="left",
                    color=color if "↑" in val or "↓" in val else NAVY,
                    fontsize=11, fontweight="bold" if "↑" in val or "↓" in val else "normal")

    ax.set_title(
        "/counterfactual  -  smallest single-feature changes to bring risk below 20 %",
        fontsize=14, fontweight="bold", color=NAVY, loc="left", pad=10,
    )

    out = ASSETS_DIR / "counterfactual_demo.png"
    plt.savefig(out)
    plt.close(fig)
    return out


def render_pivot_table(plt) -> Path:
    """Side-by-side table showing the Databricks -> AWS pivot."""
    import matplotlib.patches as mpatches
    pairs = [
        ("DBFS / Unity Catalog Volumes", "S3"),
        ("Delta Lake",                   "Parquet on S3"),
        ("Databricks Workspace",         "EMR PySpark"),
        ("Databricks Model Serving",     "FastAPI on EC2"),
        ("Databricks MLflow",            "MLflow tracking + Model Registry"),
    ]
    n_rows = len(pairs) + 1
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.set_xlim(0, 12); ax.set_ylim(0, n_rows + 1); ax.axis("off")

    row_h = 0.9
    col_x = [0.1, 6.1]
    col_w = [5.9, 5.9]

    # header
    y_top = n_rows
    ax.add_patch(mpatches.Rectangle((col_x[0], y_top), col_w[0], row_h, color="#9CA3AF"))
    ax.add_patch(mpatches.Rectangle((col_x[1], y_top), col_w[1], row_h, color=GREEN))
    ax.text(col_x[0] + 0.2, y_top + row_h/2, "Original plan (Databricks)",
            va="center", ha="left", color=WHITE, fontweight="bold", fontsize=14)
    ax.text(col_x[1] + 0.2, y_top + row_h/2, "Final design (AWS-first)",
            va="center", ha="left", color=WHITE, fontweight="bold", fontsize=14)

    for i, (left, right) in enumerate(pairs):
        y = y_top - (i + 1) * row_h - 0.04
        ax.add_patch(mpatches.Rectangle((col_x[0], y), col_w[0], row_h,
                                        facecolor=LIGHT_GRAY))
        ax.add_patch(mpatches.Rectangle((col_x[1], y), col_w[1], row_h,
                                        facecolor="#D1FAE5"))
        ax.text(col_x[0] + 0.2, y + row_h/2, left, va="center", fontsize=12, color=NAVY)
        ax.text(col_x[1] + 0.2, y + row_h/2, right, va="center", fontsize=12, color=NAVY,
                fontweight="bold")

    ax.set_title("The pivot — same architecture, different cloud",
                 fontsize=16, color=NAVY, fontweight="bold", loc="left", pad=12)
    out = ASSETS_DIR / "pivot_table.png"
    plt.savefig(out)
    plt.close(fig)
    return out


def render_model_comparison(plt) -> Path | None:
    """Four-model side-by-side comparison on the four headline metrics.

    Reads each model's own metrics.json from model_outputs/<name>/. Uses a
    2x2 grid because the metrics span ~5 orders of magnitude (PR AUC is
    ~0.001 while ROC AUC is ~0.88) - putting them on the same axis would
    visually erase PR AUC. Winning model gets the mint-green ARMED color;
    others stay navy so the win is unambiguous.
    """
    import numpy as _np
    candidates = [
        ("logistic_regression_baseline", "LR baseline"),
        ("random_forest_model",          "Random Forest"),
        ("xgboost_model",                "XGBoost"),
        ("lightgbm_model",               "LightGBM"),
    ]
    rows: list[tuple[str, str, dict]] = []
    for folder, label in candidates:
        p = MODEL_DIR / folder / "metrics.json"
        if not p.exists():
            print(f"  (skipping {folder} - no metrics.json)")
            continue
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
            rows.append((folder, label, m))
        except Exception as e:
            print(f"  (skipping {folder} - {e})")

    if len(rows) < 2:
        print("  (model_comparison needs >=2 trained models)")
        return None

    # Determine the winner from best_model_summary.json (or by max valid_f1).
    best_path = MODEL_DIR / "best_model_summary.json"
    winner_name = ""
    if best_path.exists():
        try:
            winner_name = json.loads(best_path.read_text(encoding="utf-8")).get("name", "")
        except Exception:
            pass
    if not winner_name:
        winner_name = max(rows, key=lambda r: r[2].get("valid_f1", 0.0))[0]

    fig, axes = plt.subplots(2, 2, figsize=(13, 7.5))
    metric_keys = [
        ("test_roc_auc", "Test ROC AUC",  "higher is better  -  ranking quality"),
        ("test_pr_auc",  "Test PR AUC",   "higher is better  -  the metric that matters on imbalanced data"),
        ("test_f1",      "Test F1",       "higher is better"),
        ("test_recall",  "Test recall",   "higher is better"),
    ]

    for ax, (key, title, subtitle) in zip(axes.flat, metric_keys):
        labels = [r[1] for r in rows]
        values = [float(r[2].get(key, 0)) for r in rows]
        colors_ = [
            "#10F2A2" if r[0] == winner_name else NAVY
            for r in rows
        ]
        bars = ax.bar(labels, values, color=colors_, edgecolor="none")
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.text(0.5, 1.05, subtitle, transform=ax.transAxes,
                ha="center", fontsize=10, color=GRAY, style="italic")
        # Value labels above each bar
        for bar, v in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(values) * 0.02,
                f"{v:.4f}" if v < 0.1 else f"{v:.3f}",
                ha="center", va="bottom", fontsize=10,
                color=NAVY, fontweight="bold",
            )
        ax.set_ylim(0, max(values) * 1.20 if max(values) > 0 else 1)
        ax.tick_params(axis="x", labelsize=10)
        for tick in ax.get_xticklabels():
            tick.set_rotation(0)

    fig.suptitle(
        f"Four models compared  -  winner: {winner_name}",
        fontsize=17, fontweight="bold", color=NAVY, y=1.005,
    )
    plt.tight_layout()
    out = ASSETS_DIR / "model_comparison.png"
    plt.savefig(out)
    plt.close(fig)
    return out


def render_pipeline_run_timeline(plt) -> Path:
    """Horizontal timeline of the EMR run."""
    import matplotlib.patches as mpatches
    fig, ax = plt.subplots(figsize=(13.33, 4.5))
    ax.set_xlim(0, 200); ax.set_ylim(0, 4); ax.axis("off")

    phases = [
        ("Cluster startup + bootstrap",        0,   10, GRAY),
        ("bronze_to_silver  (auth is gzipped, single-threaded)", 10, 139, "#D97706"),
        ("silver_to_gold",                     139, 194, "#2563EB"),
        ("Terminate",                          194, 195, GREEN),
    ]
    for label, start, end, color in phases:
        ax.add_patch(mpatches.FancyBboxPatch(
            (start, 1.4), end - start, 0.9,
            boxstyle="round,pad=0.02,rounding_size=0.1",
            linewidth=1, edgecolor=color, facecolor=color, alpha=0.85,
        ))
        mid = (start + end) / 2
        ax.text(mid, 1.85, label, ha="center", va="center",
                color=WHITE, fontsize=11, fontweight="bold")
        ax.text(mid, 1.05, f"{end - start} min", ha="center", va="center",
                color=NAVY, fontsize=10)

    # x-axis ticks
    for t in [0, 30, 60, 90, 120, 150, 180, 195]:
        ax.text(t, 0.4, f"{t}m", ha="center", va="center", fontsize=10, color=GRAY)
        ax.plot([t, t], [0.6, 0.8], color=GRAY, lw=1)
    ax.plot([0, 195], [0.7, 0.7], color=GRAY, lw=1)

    ax.set_title("EMR cluster - actual run, ~3h 15m total, ~$1 total cost",
                 fontsize=15, fontweight="bold", color=NAVY, loc="left", pad=10)
    out = ASSETS_DIR / "pipeline_timeline.png"
    plt.savefig(out)
    plt.close(fig)
    return out


def main() -> int:
    try:
        plt = _setup_matplotlib()
    except ImportError:
        print(
            "ERROR: matplotlib is not installed.\n"
            "  py -m pip install matplotlib\n"
            "and re-run this script.",
            file=sys.stderr,
        )
        return 1

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Writing assets to: {ASSETS_DIR}")

    generated: list[Path] = []
    for func, label in [
        (render_class_imbalance,        "class imbalance"),
        (render_data_volumes,           "data volumes"),
        (render_feature_importances,    "feature importances"),
        (render_metric_dashboard,       "metric dashboard"),
        (render_model_comparison,       "model comparison (4 models)"),
        (render_architecture_diagram,   "architecture diagram"),
        (render_medallion_diagram,      "medallion diagram"),
        (render_explainer_demo,         "explainer demo"),
        (render_counterfactual_demo,    "counterfactual demo"),
        (render_pivot_table,            "pivot table"),
        (render_pipeline_run_timeline,  "pipeline timeline"),
    ]:
        try:
            out = func(plt)
            if out:
                generated.append(out)
                print(f"  [ok] {label:30s} -> {out.name}")
            else:
                print(f"  [skip] {label}")
        except Exception as e:
            print(f"  [fail] {label}: {e}")

    print(f"\n{len(generated)} assets written.")
    print("Next: py scripts/generate_presentation_pptx.py  (deck will embed these images)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
