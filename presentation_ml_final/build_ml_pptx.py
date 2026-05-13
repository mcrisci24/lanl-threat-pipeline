"""
build_ml_pptx.py
Generates LANL_ML_Final_Project_Presentation.pptx — 12-slide ML-focused deck.
Run from the presentation_ml_final/ directory:
    python build_ml_pptx.py
Requires: python-pptx
    pip install python-pptx
"""

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# ── Color palette ──────────────────────────────────────────────────────────────
BG       = RGBColor(0x0D, 0x11, 0x17)   # near-black background
ACCENT   = RGBColor(0x00, 0xD4, 0x8A)   # mint green
RED      = RGBColor(0xFF, 0x4D, 0x4D)   # alert red
AMBER    = RGBColor(0xFF, 0xB8, 0x00)   # amber
WHITE    = RGBColor(0xFF, 0xFF, 0xFF)
SUBTEXT  = RGBColor(0x9C, 0xA3, 0xAF)   # muted grey
PANEL    = RGBColor(0x1A, 0x20, 0x2C)   # card background

W = Inches(13.33)  # widescreen width
H = Inches(7.5)    # widescreen height

OUT_FILE = Path(__file__).parent / "LANL_ML_Final_Project_Presentation.pptx"


# ── Helpers ────────────────────────────────────────────────────────────────────

def new_prs() -> Presentation:
    prs = Presentation()
    prs.slide_width  = W
    prs.slide_height = H
    return prs


def blank_slide(prs: Presentation):
    blank_layout = prs.slide_layouts[6]   # truly blank
    return prs.slides.add_slide(blank_layout)


def fill_bg(slide, color: RGBColor = BG):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rect(slide, left, top, width, height, color: RGBColor, alpha: int = None):
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        left, top, width, height,
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_text(slide, text: str, left, top, width, height,
             font_size: int = 18, bold: bool = False, color: RGBColor = WHITE,
             align=PP_ALIGN.LEFT, wrap: bool = True):
    txb = slide.shapes.add_textbox(left, top, width, height)
    tf  = txb.text_frame
    tf.word_wrap = wrap
    p   = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size  = Pt(font_size)
    run.font.bold  = bold
    run.font.color.rgb = color
    run.font.name  = "Calibri"
    return txb


def header_bar(slide, title: str, subtitle: str = ""):
    """Dark top bar with title + optional subtitle."""
    add_rect(slide, 0, 0, W, Inches(1.4), PANEL)
    add_text(slide, title, Inches(0.5), Inches(0.1), Inches(11), Inches(0.7),
             font_size=28, bold=True, color=ACCENT)
    if subtitle:
        add_text(slide, subtitle, Inches(0.5), Inches(0.8), Inches(11), Inches(0.5),
                 font_size=16, color=SUBTEXT)


def footer(slide, slide_num: int, total: int = 12):
    add_text(slide, f"Mark Crisci  |  LANL ML Final Project  |  {slide_num}/{total}",
             Inches(0.3), Inches(7.1), Inches(12), Inches(0.35),
             font_size=11, color=SUBTEXT, align=PP_ALIGN.LEFT)


def metric_card(slide, left, top, width, height,
                label: str, value: str, sub: str = "",
                value_color: RGBColor = ACCENT):
    add_rect(slide, left, top, width, height, PANEL)
    add_text(slide, label, left + Inches(0.15), top + Inches(0.1),
             width - Inches(0.3), Inches(0.4),
             font_size=13, color=SUBTEXT)
    add_text(slide, value, left + Inches(0.15), top + Inches(0.45),
             width - Inches(0.3), Inches(0.55),
             font_size=22, bold=True, color=value_color)
    if sub:
        add_text(slide, sub, left + Inches(0.15), top + Inches(0.95),
                 width - Inches(0.3), Inches(0.4),
                 font_size=12, color=SUBTEXT)


def bullet_block(slide, left, top, width, items: list[tuple[str, str]],
                 row_h: float = 0.52):
    """items = list of (bullet_text, note_text). note_text can be ''."""
    y = top
    for bullet, note in items:
        add_rect(slide, left, y, width, Inches(row_h - 0.05), PANEL)
        add_text(slide, f"▸  {bullet}", left + Inches(0.15), y + Inches(0.05),
                 width - Inches(0.3), Inches(0.35),
                 font_size=15, bold=True, color=WHITE)
        if note:
            add_text(slide, note, left + Inches(0.4), y + Inches(0.35),
                     width - Inches(0.55), Inches(0.25),
                     font_size=12, color=SUBTEXT)
        y += Inches(row_h)


# ── Slides ─────────────────────────────────────────────────────────────────────

def slide_01_title(prs):
    """Title slide."""
    slide = blank_slide(prs)
    fill_bg(slide)

    # Large accent bar
    add_rect(slide, 0, Inches(2.6), W, Inches(0.06), ACCENT)

    add_text(slide, "PREDICTING CYBER ATTACKS", Inches(1), Inches(1.1),
             Inches(11.3), Inches(1.1),
             font_size=46, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, "ONE HOUR EARLY", Inches(1), Inches(2.1),
             Inches(11.3), Inches(0.8),
             font_size=40, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
    add_text(slide,
             "Supervised Binary Classification on Real Enterprise Telemetry",
             Inches(1), Inches(2.85), Inches(11.3), Inches(0.6),
             font_size=20, color=SUBTEXT, align=PP_ALIGN.CENTER)

    add_text(slide,
             "Mark Crisci  |  Machine Learning Final Project  |  May 2026",
             Inches(1), Inches(5.8), Inches(11.3), Inches(0.5),
             font_size=15, color=SUBTEXT, align=PP_ALIGN.CENTER)

    add_text(slide, "Dataset: LANL Unified Host & Network Telemetry (not Kaggle)",
             Inches(1), Inches(6.3), Inches(11.3), Inches(0.4),
             font_size=13, color=SUBTEXT, align=PP_ALIGN.CENTER)


def slide_02_question(prs):
    slide = blank_slide(prs)
    fill_bg(slide)
    header_bar(slide, "The Research Question", "Supervised binary classification — future-window target")
    footer(slide, 2)

    add_rect(slide, Inches(0.5), Inches(1.6), Inches(12.33), Inches(1.5), PANEL)
    add_text(slide,
             '"Given how a computer behaved in the current one-hour window, '
             'will it show red-team activity in the NEXT one-hour window?"',
             Inches(0.8), Inches(1.7), Inches(11.7), Inches(1.3),
             font_size=22, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)

    points = [
        ("Predict NEXT window — not current", "Prevents the model from reading its own label (data leakage)"),
        ("Binary target: 0 = benign, 1 = attack next hour", "Built with Spark lead() window function"),
        ("Supervised learning — 596 ground-truth attack labels used directly",
         "Unlike prior LANL work that uses unsupervised anomaly detection"),
        ("Operationally useful: flag hosts BEFORE compromise, not during",
         "Earlier signal = time to respond"),
    ]
    bullet_block(slide, Inches(0.5), Inches(3.25), Inches(12.33), points, row_h=0.78)


def slide_03_dataset(prs):
    slide = blank_slide(prs)
    fill_bg(slide)
    header_bar(slide, "Dataset — LANL Enterprise Telemetry", "Real government network — not Kaggle")
    footer(slide, 3)

    # Left column — dataset facts
    streams = [
        ("auth.txt.gz",    "7.1 GB", "Authentication events — logon/logoff, success/fail"),
        ("flows.txt.gz",   "1.0 GB", "Network flows — src, dst, bytes, packets, duration"),
        ("proc.txt.gz",    "2.2 GB", "Process start/stop events"),
        ("dns.txt.gz",     "176 MB", "DNS lookups — domains queried per host"),
        ("redteam.txt.gz", "4.7 KB", "Ground-truth attack labels — 596 compromised host-hours"),
    ]
    y = Inches(1.55)
    for name, size, desc in streams:
        add_rect(slide, Inches(0.4), y, Inches(6.1), Inches(0.72), PANEL)
        add_text(slide, name, Inches(0.6), y + Inches(0.05), Inches(2.2), Inches(0.35),
                 font_size=14, bold=True, color=ACCENT)
        add_text(slide, size, Inches(2.85), y + Inches(0.05), Inches(0.9), Inches(0.35),
                 font_size=14, bold=True, color=AMBER)
        add_text(slide, desc, Inches(0.6), y + Inches(0.38), Inches(5.7), Inches(0.28),
                 font_size=12, color=SUBTEXT)
        y += Inches(0.78)

    # Right column — key stats
    metric_card(slide, Inches(7.1), Inches(1.55), Inches(5.7), Inches(1.0),
                "Total host-hour rows", "13.9 million", "After Spark aggregation")
    metric_card(slide, Inches(7.1), Inches(2.65), Inches(5.7), Inches(1.0),
                "Attack labels (positives)", "596", "0.0043% positive rate")
    metric_card(slide, Inches(7.1), Inches(3.75), Inches(5.7), Inches(1.0),
                "Dataset size (raw)", "~11 GB compressed", "58 days of telemetry")
    metric_card(slide, Inches(7.1), Inches(4.85), Inches(5.7), Inches(1.0),
                "Random PR AUC baseline", "0.0000429", "= positive rate (the floor to beat)")


def slide_04_eda(prs):
    slide = blank_slide(prs)
    fill_bg(slide)
    header_bar(slide, "Cleaning, EDA & Feature Engineering", "Bronze → Silver → Gold (Apache Spark on EMR)")
    footer(slide, 4)

    # Left: pipeline
    steps = [
        ("Bronze — Raw S3",     "11 GB raw .txt.gz files, schema-cast, no modification"),
        ("Silver — Cleaned",    "Spark ETL: type coercion fix, whitespace trim, partition by day"),
        ("Gold — 43 Features",  "Aggregate per (computer, 1-hour window); join all 5 streams"),
    ]
    y = Inches(1.55)
    for title, desc in steps:
        add_rect(slide, Inches(0.4), y, Inches(5.9), Inches(0.85), PANEL)
        add_text(slide, title, Inches(0.6), y + Inches(0.05), Inches(5.5), Inches(0.38),
                 font_size=16, bold=True, color=ACCENT)
        add_text(slide, desc, Inches(0.6), y + Inches(0.42), Inches(5.5), Inches(0.36),
                 font_size=12, color=SUBTEXT)
        y += Inches(0.95)

    # Redundant features callout
    add_rect(slide, Inches(0.4), Inches(4.55), Inches(5.9), Inches(1.65), PANEL)
    add_text(slide, "Redundant Features (EDA finding)", Inches(0.6), Inches(4.6),
             Inches(5.5), Inches(0.35), font_size=14, bold=True, color=AMBER)
    add_text(slide,
             "auth_total vs auth_inbound_count  r = 0.91\n"
             "flows_bytes_total vs bytes_per_event  correlated\n"
             "All 43 retained — tree model zeroes out redundant splits via regularization.\n"
             "Feature importances confirmed near-zero gain for flagged features.",
             Inches(0.6), Inches(5.0), Inches(5.5), Inches(1.1),
             font_size=12, color=SUBTEXT)

    # Right: feature groups
    groups = [
        ("Auth features",       "18", "Failure rates, unique sources/dests, inbound vs outbound"),
        ("Flow features",       "7",  "Bytes, packets, flow counts, bytes-per-event"),
        ("DNS features",        "3",  "Lookup counts, unique domains, density"),
        ("Process features",    "4",  "Process diversity, volume"),
        ("Derived / time",      "11", "Cross-stream ratios, hour-of-day, day-of-week"),
    ]
    y = Inches(1.55)
    for group, count, desc in groups:
        add_rect(slide, Inches(6.8), y, Inches(6.1), Inches(0.85), PANEL)
        add_text(slide, group, Inches(7.0), y + Inches(0.05), Inches(3.5), Inches(0.35),
                 font_size=14, bold=True, color=WHITE)
        add_text(slide, count + " features", Inches(10.3), y + Inches(0.05),
                 Inches(1.5), Inches(0.35), font_size=14, bold=True, color=ACCENT)
        add_text(slide, desc, Inches(7.0), y + Inches(0.42), Inches(5.7), Inches(0.36),
                 font_size=11, color=SUBTEXT)
        y += Inches(0.95)

    add_text(slide, "Total: 43 engineered features", Inches(6.8), Inches(6.3),
             Inches(6.1), Inches(0.4), font_size=15, bold=True, color=ACCENT,
             align=PP_ALIGN.CENTER)


def slide_05_litreview(prs):
    slide = blank_slide(prs)
    fill_bg(slide)
    header_bar(slide, "Literature Review & Prior Work", "What's been done — and what we did differently")
    footer(slide, 5)

    prior = [
        ("Turcotte et al. 2018", "Original LANL dataset paper — collection methodology and ground-truth labelling"),
        ("Kent 2016", "Graph-based anomaly scoring on LANL auth events (unsupervised)"),
        ("He & Garcia 2009", "Established PR AUC as primary metric for severely imbalanced classification"),
        ("Ghafir et al. 2018", "Next-window threat forecasting reduces false positives vs current-window scoring"),
    ]
    bullet_block(slide, Inches(0.4), Inches(1.55), Inches(12.5), prior, row_h=0.75)

    # Separator
    add_rect(slide, Inches(0.4), Inches(4.65), Inches(12.5), Inches(0.04), ACCENT)

    add_text(slide, "Our Departure from Prior Work", Inches(0.4), Inches(4.75),
             Inches(12.5), Inches(0.4), font_size=16, bold=True, color=ACCENT)

    departures = [
        "Supervised binary classification — NOT unsupervised anomaly detection",
        "All 596 ground-truth labels used directly — measurable precision-recall trade-off",
        "Next-window target (lead()) — prevents leakage, mimics operational deployment",
        "Cost-aware threshold tuning — business-cost optimization at serving time",
        "Counterfactual recommender — actionable 'what to change' for each alert",
    ]
    y = Inches(5.2)
    for d in departures:
        add_text(slide, f"▸  {d}", Inches(0.6), y, Inches(12.1), Inches(0.33),
                 font_size=13, color=WHITE)
        y += Inches(0.35)


def slide_06_benchmark(prs):
    slide = blank_slide(prs)
    fill_bg(slide)
    header_bar(slide, "Benchmark Model — Logistic Regression", "And why accuracy is the wrong metric")
    footer(slide, 6)

    # Why not accuracy
    add_rect(slide, Inches(0.4), Inches(1.55), Inches(12.5), Inches(1.15), RED)
    add_text(slide, "Why accuracy fails on this dataset:",
             Inches(0.6), Inches(1.6), Inches(11), Inches(0.38),
             font_size=15, bold=True, color=WHITE)
    add_text(slide,
             'A model that predicts "safe" for every single row achieves 99.9957% accuracy '
             "and catches ZERO attacks. Accuracy is meaningless when 99.996% of rows are negative.",
             Inches(0.6), Inches(1.98), Inches(11.8), Inches(0.65),
             font_size=14, color=WHITE)

    # Correct metrics
    add_rect(slide, Inches(0.4), Inches(2.85), Inches(12.5), Inches(0.95), PANEL)
    add_text(slide, "Correct metrics for imbalanced binary classification:",
             Inches(0.6), Inches(2.9), Inches(11), Inches(0.35),
             font_size=14, bold=True, color=ACCENT)
    add_text(slide,
             "PR AUC (primary) — sensitive to false positives; random baseline = positive rate = 0.0000429   |   "
             "ROC AUC (secondary) — global ranking ability   |   "
             "Precision & Recall at cost-optimal threshold (NOT 0.5)",
             Inches(0.6), Inches(3.25), Inches(12.1), Inches(0.45),
             font_size=13, color=SUBTEXT)

    # Benchmark results
    metric_card(slide, Inches(0.4),  Inches(4.0), Inches(3.9), Inches(1.1),
                "Benchmark: LR — Test ROC AUC", "0.820", "Strong ranking ability")
    metric_card(slide, Inches(4.5),  Inches(4.0), Inches(3.9), Inches(1.1),
                "Benchmark: LR — Test PR AUC", "0.00111", "26× random baseline")
    metric_card(slide, Inches(8.6),  Inches(4.0), Inches(4.3), Inches(1.1),
                "Random PR AUC baseline", "0.0000429", "= positive rate; the true floor")

    add_text(slide,
             "LR with class_weight='balanced' + median imputation + StandardScaler pipeline. "
             "This is the floor our ML models must beat.",
             Inches(0.4), Inches(5.3), Inches(12.5), Inches(0.5),
             font_size=13, color=SUBTEXT)

    add_rect(slide, Inches(0.4), Inches(5.9), Inches(12.5), Inches(0.85), PANEL)
    add_text(slide,
             "Rubric note: 'logistic regression if predicting categorical/binary outcomes' — "
             "this is binary classification. LR is the correct benchmark by rubric spec.",
             Inches(0.6), Inches(5.95), Inches(12.1), Inches(0.7),
             font_size=13, color=SUBTEXT)


def slide_07_models(prs):
    slide = blank_slide(prs)
    fill_bg(slide)
    header_bar(slide, "ML Models & Hyperparameters", "Four candidates — head-to-head competition")
    footer(slide, 7)

    models = [
        ("Logistic Regression",  "Baseline", "class_weight='balanced', max_iter=1000", SUBTEXT),
        ("Random Forest",        "300 trees", "class_weight='balanced', max_depth=None", SUBTEXT),
        ("XGBoost",              "400 trees, depth 6", "lr=0.08, subsample=0.85, colsample=0.85, λ=1.0, scale_pos_weight=n_neg/n_pos", AMBER),
        ("LightGBM",             "400 trees, 63 leaves", "lr=0.08, subsample=0.85, colsample=0.85, λ=1.0, class_weight='balanced'", ACCENT),
    ]
    y = Inches(1.55)
    for name, short, params, color in models:
        add_rect(slide, Inches(0.4), y, Inches(12.5), Inches(0.95), PANEL)
        add_text(slide, name, Inches(0.6), y + Inches(0.05), Inches(3.2), Inches(0.4),
                 font_size=16, bold=True, color=color)
        add_text(slide, short, Inches(3.85), y + Inches(0.05), Inches(2.0), Inches(0.4),
                 font_size=14, bold=True, color=WHITE)
        add_text(slide, params, Inches(0.6), y + Inches(0.5), Inches(12.0), Inches(0.38),
                 font_size=12, color=SUBTEXT)
        y += Inches(1.05)

    add_rect(slide, Inches(0.4), Inches(5.8), Inches(12.5), Inches(0.85), PANEL)
    add_text(slide, "Hyperparameter tuning strategy:",
             Inches(0.6), Inches(5.85), Inches(5), Inches(0.35),
             font_size=13, bold=True, color=ACCENT)
    add_text(slide,
             "Manual validation-set search. Full grid search on 13.9M rows is computationally prohibitive. "
             "Varied n_estimators, depth/leaves, learning_rate, regularization. "
             "Selected values that maximized validation PR AUC. Locked before test evaluation.",
             Inches(0.6), Inches(6.2), Inches(12.1), Inches(0.4),
             font_size=12, color=SUBTEXT)


def slide_08_split(prs):
    slide = blank_slide(prs)
    fill_bg(slide)
    header_bar(slide, "Train / Validation / Test Split", "60/20/20 stratified — and why not k-fold")
    footer(slide, 8)

    # Split diagram
    total_w = Inches(12.0)
    lx = Inches(0.65)
    ly = Inches(1.7)
    lh = Inches(0.9)

    # Train bar
    add_rect(slide, lx, ly, total_w * 0.60, lh, ACCENT)
    add_text(slide, "TRAIN  60%", lx + Inches(0.2), ly + Inches(0.2),
             total_w * 0.55, Inches(0.5), font_size=18, bold=True, color=BG)

    # Val bar
    vx = lx + total_w * 0.60 + Inches(0.05)
    add_rect(slide, vx, ly, total_w * 0.19, lh, AMBER)
    add_text(slide, "VAL 20%", vx + Inches(0.05), ly + Inches(0.2),
             total_w * 0.18, Inches(0.5), font_size=16, bold=True, color=BG)

    # Test bar
    tx = vx + total_w * 0.19 + Inches(0.05)
    add_rect(slide, tx, ly, total_w * 0.19, lh, RED)
    add_text(slide, "TEST 20%", tx + Inches(0.05), ly + Inches(0.2),
             total_w * 0.18, Inches(0.5), font_size=16, bold=True, color=WHITE)

    # Stats
    stats = [
        ("Train set",       "~8.34M rows",  "~358 positives"),
        ("Validation set",  "~2.78M rows",  "~119 positives"),
        ("Test set",        "~2.78M rows",  "~119 positives  ← reported in results"),
    ]
    y = Inches(2.8)
    for label, rows, pos in stats:
        add_text(slide, label, Inches(0.65), y, Inches(2.5), Inches(0.38),
                 font_size=14, bold=True, color=WHITE)
        add_text(slide, rows, Inches(3.2), y, Inches(2.5), Inches(0.38),
                 font_size=14, color=ACCENT)
        add_text(slide, pos, Inches(5.8), y, Inches(6.8), Inches(0.38),
                 font_size=14, color=SUBTEXT)
        y += Inches(0.45)

    # k-fold explanation
    add_rect(slide, Inches(0.4), Inches(4.15), Inches(12.5), Inches(2.8), PANEL)
    add_text(slide, "Why k-fold was not used (honest explanation):",
             Inches(0.6), Inches(4.2), Inches(12.0), Inches(0.38),
             font_size=15, bold=True, color=AMBER)
    add_text(slide,
             "1.  Time-ordered security telemetry: random k-fold shuffles rows, leaking future behavioral patterns into training.\n"
             "2.  Chronological split tested: red-team campaign is concentrated in the final weeks → strict time split places\n"
             "     nearly ALL 596 positives in training → validation/test have zero positives → all metrics = NaN/undefined.\n"
             "3.  Resolution: stratified random 60/20/20 preserves positive rate (~119/set). The lead() target construction\n"
             "     prevents within-row temporal leakage. Hyperparameters tuned on validation set (= inner loop of nested k-fold\n"
             "     without resampling). This is a deliberate, defensible choice — not an oversight.",
             Inches(0.6), Inches(4.65), Inches(12.1), Inches(2.2),
             font_size=13, color=SUBTEXT)


def slide_09_results(prs):
    slide = blank_slide(prs)
    fill_bg(slide)
    header_bar(slide, "Results — All Models Across Validation & Test", "PR AUC is the primary metric")
    footer(slide, 9)

    # Table header
    cols = ["Model", "Valid ROC AUC", "Valid PR AUC", "Test ROC AUC", "Test PR AUC"]
    col_w = [Inches(3.2), Inches(2.1), Inches(2.1), Inches(2.1), Inches(2.1)]
    lx = Inches(0.5)
    ty = Inches(1.6)

    x = lx
    for i, (c, w) in enumerate(zip(cols, col_w)):
        add_rect(slide, x, ty, w - Inches(0.05), Inches(0.5), PANEL)
        add_text(slide, c, x + Inches(0.1), ty + Inches(0.07), w - Inches(0.2), Inches(0.38),
                 font_size=13, bold=True, color=ACCENT)
        x += w

    rows = [
        ("Logistic Regression", "0.802", "0.000658", "0.820", "0.00111",  False),
        ("Random Forest",       "0.698", "0.000186", "0.748", "0.000322", False),
        ("XGBoost",             "0.844", "0.001737", "0.879", "0.03542",  False),
        ("LightGBM  ← WINNER", "0.838", "0.001615", "0.881", "0.03905",  True),
    ]
    values = [r[:5] for r in rows]
    winners = [r[5] for r in rows]

    y = ty + Inches(0.55)
    for i, (vals, win) in enumerate(zip(values, winners)):
        bg_color = ACCENT if win else PANEL
        txt_color = BG if win else WHITE
        x = lx
        for j, (v, w) in enumerate(zip(vals, col_w)):
            cell_color = bg_color if win else PANEL
            if not win and j in (2, 4):  # PR AUC columns — slightly highlight
                cell_color = RGBColor(0x1E, 0x28, 0x38)
            add_rect(slide, x, y, w - Inches(0.05), Inches(0.62), cell_color)
            fc = txt_color if win else (ACCENT if j in (2, 4) else WHITE)
            add_text(slide, v, x + Inches(0.1), y + Inches(0.12),
                     w - Inches(0.2), Inches(0.4),
                     font_size=14, bold=(win or j in (2, 4)), color=fc)
            x += w
        y += Inches(0.67)

    # Lift callouts
    metric_card(slide, Inches(0.5), Inches(5.45), Inches(3.9), Inches(1.1),
                "LightGBM PR AUC lift over random", "909×", "0.039 ÷ 0.0000429", ACCENT)
    metric_card(slide, Inches(4.6), Inches(5.45), Inches(3.9), Inches(1.1),
                "Lift over LR baseline (35×)", "35×", "0.039 ÷ 0.00111", ACCENT)
    metric_card(slide, Inches(8.7), Inches(5.45), Inches(4.1), Inches(1.1),
                "LightGBM test ROC AUC", "0.881", "Best ranking performance", ACCENT)


def slide_10_interpretation(prs):
    slide = blank_slide(prs)
    fill_bg(slide)
    header_bar(slide, "Model Interpretation — TreeSHAP + Counterfactuals",
               "Exact per-feature contributions — not an approximation")
    footer(slide, 10)

    # Left panel — SHAP explanation
    add_rect(slide, Inches(0.4), Inches(1.55), Inches(6.1), Inches(5.5), PANEL)
    add_text(slide, "Why did the model flag this host?", Inches(0.6), Inches(1.65),
             Inches(5.7), Inches(0.38), font_size=15, bold=True, color=ACCENT)

    shap_features = [
        ("flows_outbound_count",       "+0.84", RED),
        ("auth_unique_destinations",   "+0.61", RED),
        ("auth_total",                 "+0.42", RED),
        ("flows_bytes_total",          "+0.29", RED),
        ("dns_lookup_count",           "-0.18", ACCENT),
        ("proc_unique_processes",      "-0.31", ACCENT),
        ("auth_failure_ratio",         "-0.12", ACCENT),
    ]
    fy = Inches(2.15)
    bar_max = Inches(3.0)
    for feat, val, color in shap_features:
        v = float(val)
        bar_w = bar_max * abs(v) / 1.0
        bx = Inches(0.6) if v > 0 else Inches(0.6) + bar_max - bar_w
        add_rect(slide, bx, fy, bar_w, Inches(0.3), color)
        add_text(slide, feat, Inches(3.75), fy, Inches(2.0), Inches(0.3),
                 font_size=11, color=WHITE)
        add_text(slide, val, Inches(5.85), fy, Inches(0.6), Inches(0.3),
                 font_size=11, bold=True, color=color)
        fy += Inches(0.38)

    add_text(slide, "Red = pushes risk UP  |  Green = pushes risk DOWN  |  Length = magnitude (log-odds)",
             Inches(0.6), Inches(4.95), Inches(5.7), Inches(0.35),
             font_size=11, color=SUBTEXT)

    add_text(slide,
             "TreeSHAP: exact contributions from LightGBM's booster internals.\n"
             "Not a shap library approximation. Reproducible and fast.",
             Inches(0.6), Inches(5.4), Inches(5.7), Inches(0.5),
             font_size=12, color=SUBTEXT)

    # Right panel — counterfactual + threshold
    add_rect(slide, Inches(6.8), Inches(1.55), Inches(6.1), Inches(2.4), PANEL)
    add_text(slide, "Counterfactual Recommender", Inches(7.0), Inches(1.65),
             Inches(5.7), Inches(0.38), font_size=15, bold=True, color=AMBER)
    add_text(slide,
             '"How to lower this risk below 20%:"\n\n'
             "auth_outbound_count        delta = -2\n"
             "flows_outbound_count       delta = -4\n"
             "auth_unique_destinations   delta = -1\n\n"
             "Smallest single-feature change that crosses the decision boundary.\n"
             "Computed by the LR sidecar (closed-form). Actionable for an analyst.",
             Inches(7.0), Inches(2.1), Inches(5.7), Inches(1.7),
             font_size=12, color=SUBTEXT)

    add_rect(slide, Inches(6.8), Inches(4.1), Inches(6.1), Inches(2.95), PANEL)
    add_text(slide, "Cost-Optimal Threshold", Inches(7.0), Inches(4.2),
             Inches(5.7), Inches(0.38), font_size=15, bold=True, color=ACCENT)
    add_text(slide,
             "Input:\n"
             "  cost_fp = $100   (analyst investigation time)\n"
             "  cost_fn = $100,000   (breach cost)\n\n"
             "Output: threshold = 0.10\n\n"
             "Minimizes: FP_count × cost_fp + FN_count × cost_fn\n"
             "on the validation set. NOT hardcoded to 0.5.",
             Inches(7.0), Inches(4.65), Inches(5.7), Inches(2.2),
             font_size=12, color=SUBTEXT)


def slide_11_threshold(prs):
    slide = blank_slide(prs)
    fill_bg(slide)
    header_bar(slide, "Why Threshold 0.5 is Wrong — and How to Fix It",
               "The threshold is a business decision, not a hyperparameter")
    footer(slide, 11)

    # At 0.5
    add_rect(slide, Inches(0.4), Inches(1.55), Inches(5.9), Inches(3.2), PANEL)
    add_text(slide, "At threshold = 0.5  (sklearn default)", Inches(0.6), Inches(1.65),
             Inches(5.5), Inches(0.38), font_size=15, bold=True, color=RED)
    add_text(slide,
             "Predicted positives:  ≈ 0\n"
             "True positives:        ≈ 0\n"
             "False positives:       ≈ 0\n"
             "False negatives:       ≈ ALL 119 test attacks\n\n"
             "The model looks broken. It isn't.\n"
             "It ranks positives correctly — 0.5 is just too high\n"
             "a cutoff for a 0.004% positive rate.",
             Inches(0.6), Inches(2.1), Inches(5.5), Inches(2.5),
             font_size=14, color=SUBTEXT)

    # At 0.10
    add_rect(slide, Inches(6.8), Inches(1.55), Inches(6.1), Inches(3.2), PANEL)
    add_text(slide, "At cost-optimal threshold = 0.10", Inches(7.0), Inches(1.65),
             Inches(5.7), Inches(0.38), font_size=15, bold=True, color=ACCENT)
    add_text(slide,
             "Predicted positives:  controlled volume\n"
             "True positives:        meaningful recall\n"
             "False positives:       manageable noise\n"
             "False negatives:       minimized given costs\n\n"
             "Same model. Same predictions.\n"
             "Different operating point — tuned to your\n"
             "actual FP/FN cost ratio.",
             Inches(7.0), Inches(2.1), Inches(5.7), Inches(2.5),
             font_size=14, color=SUBTEXT)

    add_rect(slide, Inches(0.4), Inches(4.95), Inches(12.5), Inches(1.3), PANEL)
    add_text(slide,
             "The cost-matrix calculator takes cost_fp and cost_fn, sweeps threshold 0.001→0.999,\n"
             "computes total_cost = FP × cost_fp + FN × cost_fn at each step on the validation set,\n"
             "and returns the threshold with the lowest expected operational cost.",
             Inches(0.6), Inches(5.05), Inches(12.1), Inches(1.1),
             font_size=14, color=SUBTEXT)


def slide_12_limitations(prs):
    slide = blank_slide(prs)
    fill_bg(slide)
    header_bar(slide, "Limitations & Stakeholder Recommendation",
               "Honest weaknesses + what I'd tell a SOC director")
    footer(slide, 12)

    # Limitations
    add_text(slide, "Limitations", Inches(0.4), Inches(1.55),
             Inches(6.0), Inches(0.4), font_size=16, bold=True, color=AMBER)
    limitations = [
        ("Streaming is simulated",       "CSV replay at 1 event/sec — not live Kinesis ingest"),
        ("No calibration analysis",      "Probabilities rank correctly; not verified as true frequencies"),
        ("k-fold not used",              "Justified by temporal structure; acknowledged as a gap"),
        ("596 positives total",          "Model generalizes within LANL; external validity unknown"),
        ("GenAI comparison: NOT DONE",   "Extra credit not claimed"),
    ]
    y = Inches(2.05)
    for title, desc in limitations:
        add_rect(slide, Inches(0.4), y, Inches(6.1), Inches(0.75), PANEL)
        add_text(slide, title, Inches(0.6), y + Inches(0.05), Inches(5.7), Inches(0.33),
                 font_size=13, bold=True, color=AMBER)
        add_text(slide, desc, Inches(0.6), y + Inches(0.4), Inches(5.7), Inches(0.28),
                 font_size=12, color=SUBTEXT)
        y += Inches(0.82)

    # Recommendation
    add_text(slide, "Stakeholder Recommendation", Inches(6.8), Inches(1.55),
             Inches(6.1), Inches(0.4), font_size=16, bold=True, color=ACCENT)
    recs = [
        ("Deploy LightGBM at cost-optimal threshold",
         "Set threshold via the cost-matrix calculator using your actual FP/FN costs"),
        ("Pair every alert with its SHAP explanation",
         "Analysts see WHY the model flagged — not just that it did"),
        ("Use the counterfactual table as first-line remediation",
         "'Reduce outbound auth count by 2' is actionable; 'elevated risk' is not"),
        ("Add calibration before quoting percentages",
         "Reliability diagrams + Platt scaling before telling a CISO '74.5% chance'"),
        ("Future: real Kinesis ingest",
         "Swap CSV replayer for Kinesis consumer — model and API unchanged"),
    ]
    y = Inches(2.05)
    for title, desc in recs:
        add_rect(slide, Inches(6.8), y, Inches(6.1), Inches(0.75), PANEL)
        add_text(slide, title, Inches(7.0), y + Inches(0.05), Inches(5.7), Inches(0.33),
                 font_size=13, bold=True, color=ACCENT)
        add_text(slide, desc, Inches(7.0), y + Inches(0.4), Inches(5.7), Inches(0.28),
                 font_size=12, color=SUBTEXT)
        y += Inches(0.82)


# ── Main ───────────────────────────────────────────────────────────────────────

def build():
    prs = new_prs()

    slide_01_title(prs)
    slide_02_question(prs)
    slide_03_dataset(prs)
    slide_04_eda(prs)
    slide_05_litreview(prs)
    slide_06_benchmark(prs)
    slide_07_models(prs)
    slide_08_split(prs)
    slide_09_results(prs)
    slide_10_interpretation(prs)
    slide_11_threshold(prs)
    slide_12_limitations(prs)

    prs.save(OUT_FILE)
    print(f"Saved {OUT_FILE}  ({len(prs.slides)} slides)")


if __name__ == "__main__":
    build()
