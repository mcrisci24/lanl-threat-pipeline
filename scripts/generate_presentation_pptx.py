"""
scripts/generate_presentation_pptx.py
=====================================

Generate the LANL Threat Prediction capstone deck as a real .pptx file.

Visuals come from scripts/generate_presentation_assets.py (run that first).
This generator builds a 16:9 deck with:
  - A hero title slide
  - Section slides that lead with an IMAGE and a short caption
  - Bullet slides only where text is genuinely the right medium
  - Speaker notes baked into every slide (View -> Speaker Notes)

Output:  PRESENTATION.pptx  at the repo root.

Usage:
    py -m pip install -q python-pptx
    py scripts/generate_presentation_assets.py        # produces PNGs
    py scripts/generate_presentation_pptx.py          # builds the deck
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "presentation_assets"
OUT = REPO_ROOT / "PRESENTATION.pptx"

# Project metadata baked into the deck
PROJECT_TITLE = "LANL Threat Prediction Pipeline"
PROJECT_SUBTITLE = (
    "An AWS-first distributed pipeline\nwith explainable + counterfactual XAI"
)
PRESENTER = "Mark Crisci"
LIVE_URL = "https://lanlthreat.streamlit.app"
API_URL = "http://98.94.30.68:8000"
GITHUB_URL = "https://github.com/mcrisci24/lanl-threat-pipeline"


def _asset(name: str) -> Path | None:
    """Return the asset path if it exists, else None (slide will fall back to bullets)."""
    p = ASSETS_DIR / name
    return p if p.exists() else None


def main() -> int:
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt, Emu
        from pptx.dml.color import RGBColor
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.enum.text import PP_ALIGN
    except ImportError:
        print(
            "ERROR: python-pptx is not installed.\n"
            "  py -m pip install python-pptx\n"
            "and re-run this script.",
            file=sys.stderr,
        )
        return 1

    # ----- Theme colors --------------------------------------------------
    NAVY = RGBColor(0x1F, 0x2A, 0x44)
    NAVY_LIGHT = RGBColor(0x3B, 0x48, 0x66)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    BODY = RGBColor(0x1A, 0x1A, 0x1A)
    ACCENT = RGBColor(0xE6, 0x55, 0x55)
    MUTED = RGBColor(0x6B, 0x72, 0x80)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    BLANK = prs.slide_layouts[6]

    # ----- Helpers -------------------------------------------------------
    def new_slide(notes: str = ""):
        slide = prs.slides.add_slide(BLANK)
        if notes:
            slide.notes_slide.notes_text_frame.text = notes
        return slide

    def add_accent_bar(slide):
        bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0), Inches(0),
            Inches(0.2), prs.slide_height,
        )
        bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT; bar.line.fill.background()

    def add_header(slide, title_text: str):
        bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0), Inches(0),
            prs.slide_width, Inches(0.85),
        )
        bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()

        tb = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.13), prs.slide_width - Inches(0.6), Inches(0.7),
        )
        tf = tb.text_frame
        tf.margin_top = Pt(0); tf.margin_bottom = Pt(0)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        r = p.add_run()
        r.text = title_text
        r.font.size = Pt(26); r.font.bold = True; r.font.color.rgb = WHITE

    def add_page_number(slide, idx: int, total: int):
        tb = slide.shapes.add_textbox(
            prs.slide_width - Inches(1.5), prs.slide_height - Inches(0.4),
            Inches(1.3), Inches(0.3),
        )
        p = tb.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        r = p.add_run()
        r.text = f"{idx} / {total}"
        r.font.size = Pt(10); r.font.color.rgb = MUTED

    def add_text_block(slide, text: str, left, top, width, height,
                       size=18, color=BODY, bold=False, italic=False,
                       align=PP_ALIGN.LEFT, mono=False):
        tb = slide.shapes.add_textbox(left, top, width, height)
        tf = tb.text_frame; tf.word_wrap = True; tf.margin_top = Pt(0)
        p = tf.paragraphs[0]; p.alignment = align
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size); r.font.color.rgb = color
        r.font.bold = bold; r.font.italic = italic
        if mono:
            r.font.name = "Consolas"
        return tb

    def add_bullets(slide, items, left, top, width, height, size=16,
                    line_spacing_pt=4):
        tb = slide.shapes.add_textbox(left, top, width, height)
        tf = tb.text_frame; tf.word_wrap = True; tf.margin_top = Pt(0)
        first = True
        for text in items:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.space_after = Pt(line_spacing_pt)
            r = p.add_run()
            if not text:
                r.text = " "
                continue
            r.text = text
            r.font.size = Pt(size); r.font.color.rgb = BODY

    def add_image(slide, asset_name, left, top, width=None, height=None):
        path = _asset(asset_name)
        if not path:
            return None
        kwargs = {}
        if width: kwargs["width"] = width
        if height: kwargs["height"] = height
        return slide.shapes.add_picture(str(path), left, top, **kwargs)

    # =====================================================================
    # SLIDE LIST  (composer functions per slide)
    # =====================================================================
    slide_composers = []

    # ---------- 1. Title (hero) -----------------------------------------
    def s1(slide):
        # Full-bleed navy background
        bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0), Inches(0),
            prs.slide_width, prs.slide_height,
        )
        bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
        # Accent strip
        strip = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0), Inches(0),
            Inches(0.25), prs.slide_height,
        )
        strip.fill.solid(); strip.fill.fore_color.rgb = ACCENT; strip.line.fill.background()
        # Subtitle pretitle
        add_text_block(slide, "DISTRIBUTED COMPUTING FOR DATA SCIENCE  -  PROJECT 2",
                       Inches(1.2), Inches(1.7), Inches(11), Inches(0.4),
                       size=14, color=ACCENT, bold=True)
        # Title
        add_text_block(slide, PROJECT_TITLE,
                       Inches(1.2), Inches(2.2), Inches(11), Inches(1.6),
                       size=48, color=WHITE, bold=True)
        # Subtitle
        add_text_block(slide, PROJECT_SUBTITLE,
                       Inches(1.2), Inches(3.7), Inches(11), Inches(1.3),
                       size=24, color=RGBColor(0xD1, 0xD5, 0xDB))
        # URLs block
        urls = [
            f"Presenter      {PRESENTER}",
            f"Live URL       {LIVE_URL}",
            f"API endpoint   {API_URL}",
            f"Repository     {GITHUB_URL}",
        ]
        tb = slide.shapes.add_textbox(
            Inches(1.2), Inches(5.5), Inches(11), Inches(1.8),
        )
        tf = tb.text_frame; tf.word_wrap = True
        first = True
        for line in urls:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            r = p.add_run()
            r.text = line
            r.font.size = Pt(15); r.font.color.rgb = RGBColor(0xE5, 0xE7, 0xEB)
            r.font.name = "Consolas"
            p.space_after = Pt(2)

    notes_s1 = (
        "Open with the live URL. Pause to let people read it. Note the subtitle: "
        "this is more than a model + API. The two-line subtitle is the framing - "
        "distributed pipeline plus explainable + counterfactual XAI."
    )
    slide_composers.append((s1, notes_s1))

    # ---------- 2. The Prediction Question -------------------------------
    def s2(slide):
        add_accent_bar(slide); add_header(slide, "The Prediction Question")
        # Big quote-style framing
        add_text_block(slide,
            '"Given a computer\'s behavior in the current hour,\n'
            ' will it show red-team activity in the NEXT hour?"',
            Inches(0.7), Inches(1.2), Inches(12), Inches(1.6),
            size=24, color=NAVY, bold=True, italic=True)
        # Bullets
        bullets = [
            "Target = redteam_current_flag at window t+1 (Spark window lead)",
            "All current-window red-team columns explicitly removed from features",
            "Training script asserts no leakage column survives - fails the run if any do",
            "",
            "Why not predict the CURRENT window?",
            "    Same-window prediction is description, not prediction.",
            "    Next-window framing is the operationally honest question.",
        ]
        add_bullets(slide, bullets, Inches(0.7), Inches(3.2), Inches(12), Inches(3.5),
                    size=17)
    notes_s2 = (
        "The framing decision that separates this from a tutorial. Our first model "
        "had validation F1 near 1.0 because of subtle leakage. Rebuilding the target "
        "as 'next window' and adding the leakage assertion was the fix."
    )
    slide_composers.append((s2, notes_s2))

    # ---------- 3. The Data (visualization) -----------------------------
    def s3(slide):
        add_accent_bar(slide); add_header(slide, "The Data — LANL multi-source telemetry")
        add_image(slide, "data_volumes.png",
                  Inches(0.5), Inches(1.1), width=Inches(7.8))
        add_text_block(slide, "5 telemetry streams,  ~11 GB compressed",
                       Inches(8.6), Inches(1.4), Inches(4.5), Inches(0.5),
                       size=18, color=NAVY, bold=True)
        bullets = [
            "auth — authentication events (the bottleneck source)",
            "flows — network flow records",
            "proc — process lifecycle events",
            "dns — DNS resolutions",
            "redteam — ground-truth attack labels (4.7 KB)",
            "",
            "Refresh: one-time historical dataset.",
            "Each source has its own row grain in silver.",
        ]
        add_bullets(slide, bullets, Inches(8.6), Inches(2.0),
                    Inches(4.5), Inches(5), size=14)
    notes_s3 = (
        "Auth is 7.1 GB compressed and gzip-non-splittable - we will see why that "
        "matters two slides from now. Redteam is the tiny ground-truth file."
    )
    slide_composers.append((s3, notes_s3))

    # ---------- 4. Class imbalance (visualization) ----------------------
    def s4(slide):
        add_accent_bar(slide); add_header(slide, "The signal is a red sliver")
        add_image(slide, "class_imbalance.png",
                  Inches(0.5), Inches(1.2), width=Inches(12.5))
        add_text_block(slide,
            "596 positives in 13.9 M rows = 0.0043 % positive rate. "
            "Accuracy is meaningless on this scale - a model that predicts "
            "ALL benign is 99.996 % accurate AND completely useless.",
            Inches(0.7), Inches(5.4), Inches(12), Inches(1.5),
            size=17, color=NAVY, bold=False)
    notes_s4 = (
        "Drive this home: the entire signal is the red sliver. ROC AUC and "
        "PR AUC are the right metrics; F1 is misleading without context."
    )
    slide_composers.append((s4, notes_s4))

    # ---------- 5. Architecture diagram ---------------------------------
    def s5(slide):
        add_accent_bar(slide); add_header(slide, "Architecture — AWS-first, 3 distributed stages")
        add_image(slide, "architecture_diagram.png",
                  Inches(0.5), Inches(1.0), width=Inches(12.5))
        add_text_block(slide,
            "Spec requires >= 2 distributed stages. This project has 3: "
            "S3 (cloud storage), EMR PySpark (distributed compute), "
            "FastAPI on EC2 + Streamlit Cloud (cloud serving).",
            Inches(0.7), Inches(6.4), Inches(12), Inches(0.9),
            size=15, color=NAVY)
    notes_s5 = (
        "Lead with the rubric framing. The accent colors on the diagram match "
        "the legend. Walk top to bottom following the arrows."
    )
    slide_composers.append((s5, notes_s5))

    # ---------- 6. Medallion in plain English ---------------------------
    def s6(slide):
        add_accent_bar(slide); add_header(slide, "Medallion in plain English")
        add_image(slide, "medallion_diagram.png",
                  Inches(0.5), Inches(1.0), width=Inches(12.5))
        add_text_block(slide,
            "The row grain CHANGES at gold. Silver is many events. Gold is "
            "one host per hour. That shift is what makes this a behavior-prediction "
            "problem rather than an event classifier.",
            Inches(0.7), Inches(6.4), Inches(12), Inches(0.9),
            size=15, color=NAVY)
    notes_s6 = "The single most important conceptual point about the architecture."
    slide_composers.append((s6, notes_s6))

    # ---------- 7. Signature design: anti-leakage ----------------------
    def s7(slide):
        add_accent_bar(slide); add_header(slide, "Anti-leakage by construction")
        # 3 boxes side by side
        items = [
            ("1.  Future-window target",
             "Built with Spark `lead()` over (computer, time_window).\n"
             "target = next-window redteam_current_flag."),
            ("2.  Drop current-window red-team",
             "redteam_src_event_count\nredteam_dst_event_count\n"
             "redteam_event_count\nredteam_current_flag"),
            ("3.  Code-level assertion",
             "assert_no_leakage(feature_cols)\nfails the training run if any\nleakage column survives."),
        ]
        for i, (h, body) in enumerate(items):
            x = Inches(0.5 + i * 4.3)
            shape = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(1.4),
                Inches(4.1), Inches(4.4),
            )
            shape.fill.solid(); shape.fill.fore_color.rgb = NAVY
            shape.line.fill.background()
            shape.shadow.inherit = False

            add_text_block(slide, h, x + Inches(0.3), Inches(1.6),
                           Inches(3.7), Inches(0.7),
                           size=18, color=ACCENT, bold=True)
            add_text_block(slide, body, x + Inches(0.3), Inches(2.3),
                           Inches(3.7), Inches(3.4),
                           size=14, color=WHITE, mono=("`" in body or "_" in body))
        add_text_block(slide,
            "Plus stratified random 60/20/20 split: in LANL all positives "
            "occur in a finite campaign window, so a strict time-aware split "
            "leaves valid/test with zero positives. Documented trade-off.",
            Inches(0.5), Inches(6.0), Inches(12.5), Inches(1.0),
            size=14, color=NAVY)
    notes_s7 = (
        "Three layers of defense. Real-world anti-leakage isn't a vibe - "
        "it's three concrete code mechanisms working together."
    )
    slide_composers.append((s7, notes_s7))

    # ---------- 8. EMR run timeline -------------------------------------
    def s8(slide):
        add_accent_bar(slide); add_header(slide, "The pipeline actually ran")
        add_image(slide, "pipeline_timeline.png",
                  Inches(0.5), Inches(1.2), width=Inches(12.5))
        bullets = [
            "Single transient EMR cluster, 3 x m5.xlarge (12 vCPUs total).",
            "Cluster auto-terminated after both Spark steps completed.",
            "",
            "Surprise constraint: gzip-compressed CSV is NOT splittable in Spark.",
            "The 7.1 GB auth file was decompressed on ONE core. The other 11 cores",
            "sat idle through most of bronze_to_silver. In production we'd land",
            "raw .gz files as bzip2 or Snappy parquet on ingest to fix this.",
        ]
        add_bullets(slide, bullets, Inches(0.7), Inches(4.6),
                    Inches(12), Inches(2.7), size=15)
    notes_s8 = (
        "Real distributed-computing trade-offs. The gzip-non-splittable insight "
        "is exactly the kind of detail that signals deep understanding."
    )
    slide_composers.append((s8, notes_s8))

    # ---------- 9. Model + MLflow ----------------------------------------
    def s9(slide):
        add_accent_bar(slide); add_header(slide, "The model + MLflow")
        bullets = [
            "Two scikit-learn pipelines, both wrapped:",
            "    ColumnTransformer(SimpleImputer(median) -> StandardScaler) -> classifier",
            "",
            "        1.  logistic_regression_baseline   (class_weight='balanced')",
            "        2.  random_forest_model            (300 trees, balanced)",
            "",
            "Every run logged to MLflow: metrics, params, leakage metadata, artifact.",
            "",
            "Winning version registered as  lanl_threat_predictor  v4,",
            "alias  Production  (the version the API actually serves).",
            "",
            "The Model Registry alias is the auditable answer to:",
            "    'Which version is in production right now?'",
        ]
        add_bullets(slide, bullets, Inches(0.7), Inches(1.2),
                    Inches(12), Inches(6), size=16)
    notes_s9 = (
        "The rubric requires Model Registry, not just MLflow tracking. The alias "
        "is what makes it auditable - any reviewer can answer 'which version is "
        "serving prod' in one query."
    )
    slide_composers.append((s9, notes_s9))

    # ---------- 10. Metric dashboard ------------------------------------
    def s10(slide):
        add_accent_bar(slide); add_header(slide, "Evaluation — honest numbers")
        add_image(slide, "metric_dashboard.png",
                  Inches(0.5), Inches(1.1), width=Inches(12.5))
        bullets = [
            "ROC AUC of 0.82 is the headline:  given a positive + negative pair,",
            "the model ranks the positive higher 82 % of the time.",
            "",
            "Why precision / F1 are tiny:  class_weight='balanced' is aggressive,",
            "so the model produces many false positives in absolute terms - but",
            "very few in relative terms (negatives are 99.996 % of the data).",
            "",
            "PR AUC is the right honest metric on data this imbalanced.",
        ]
        add_bullets(slide, bullets, Inches(0.7), Inches(4.7),
                    Inches(12), Inches(2.7), size=14)
    notes_s10 = (
        "Pre-empt the obvious 'why is precision so low?' question by leading "
        "with the explanation."
    )
    slide_composers.append((s10, notes_s10))

    # ---------- 11. Feature importance ----------------------------------
    def s11(slide):
        add_accent_bar(slide); add_header(slide, "Top 15 features driving the model")
        add_image(slide, "feature_importances.png",
                  Inches(0.5), Inches(1.0), width=Inches(9.0))
        bullets = [
            "Top driver: dns_unique_resolved_computers",
            "    The model has learned that the DIVERSITY of DNS",
            "    targets a host queries is a strong red-team signal.",
            "",
            "Flow-level features dominate the top of the list -",
            "fewer auth signals than you might expect.",
            "",
            "Interpretation: real attackers move laterally via",
            "DNS reconnaissance and flow probes more visibly",
            "than via the auth log alone.",
        ]
        add_bullets(slide, bullets, Inches(9.7), Inches(1.4),
                    Inches(3.5), Inches(5.8), size=12)
    notes_s11 = (
        "Frame this as a domain insight, not just an ML artifact. The model is "
        "telling us something interesting about how attacks look in telemetry."
    )
    slide_composers.append((s11, notes_s11))

    # ---------- 12. API surface ------------------------------------------
    def s12(slide):
        add_accent_bar(slide); add_header(slide, "Serving layer — FastAPI on EC2")
        rows = [
            ("GET",  "/health",          "liveness + model_loaded check"),
            ("GET",  "/model_info",      "served model + last-known metrics"),
            ("GET",  "/features",        "feature contract for clients"),
            ("POST", "/predict",         "single-row prediction"),
            ("POST", "/batch_predict",   "many-row prediction"),
            ("POST", "/explain",         "per-feature contribution (XAI)"),
            ("POST", "/counterfactual",  "smallest interventions to lower risk"),
        ]
        # Render as a clean table
        y = 1.4
        for verb, path, desc in rows:
            color = ACCENT if verb == "POST" else NAVY_LIGHT
            box = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Inches(0.7), Inches(y), Inches(0.9), Inches(0.55),
            )
            box.fill.solid(); box.fill.fore_color.rgb = color
            box.line.fill.background()
            add_text_block(slide, verb, Inches(0.7), Inches(y + 0.07),
                           Inches(0.9), Inches(0.45),
                           size=14, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
            add_text_block(slide, path, Inches(1.8), Inches(y + 0.08),
                           Inches(4), Inches(0.5),
                           size=18, color=NAVY, mono=True, bold=True)
            add_text_block(slide, desc, Inches(6.0), Inches(y + 0.13),
                           Inches(7), Inches(0.45),
                           size=15, color=BODY)
            y += 0.72
        # Wow callout
        callout = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(8.7), Inches(5.45), Inches(4.0), Inches(1.3),
        )
        callout.fill.solid(); callout.fill.fore_color.rgb = ACCENT
        callout.line.fill.background()
        add_text_block(slide, "WOW factor lives in the last 2 endpoints",
                       Inches(8.7), Inches(5.55), Inches(4.0), Inches(0.5),
                       size=15, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        add_text_block(slide, "/explain and /counterfactual together =\nreal decision support",
                       Inches(8.7), Inches(5.95), Inches(4.0), Inches(0.7),
                       size=12, color=WHITE, align=PP_ALIGN.CENTER)
    notes_s12 = (
        "The /health endpoint actually checks the MODEL is loaded, not just that "
        "the process is alive - small detail that matters for monitoring."
    )
    slide_composers.append((s12, notes_s12))

    # ---------- 13. WOW: Explainable AI ----------------------------------
    def s13(slide):
        add_accent_bar(slide); add_header(slide, "Wow #1 — Explainable AI by exact decomposition")
        add_image(slide, "explainer_demo.png",
                  Inches(0.5), Inches(1.1), width=Inches(8.6))
        add_text_block(slide, "/explain", Inches(9.4), Inches(1.2),
                       Inches(3.7), Inches(0.5),
                       size=24, color=ACCENT, bold=True, mono=True)
        bullets = [
            "Linear-model decomposition:",
            "    contribution_i =",
            "        coef_i x scaled_value_i",
            "",
            "Exact log-odds breakdown,",
            "not a SHAP approximation.",
            "",
            "Red bars = raises risk",
            "Green bars = lowers risk",
            "",
            "Top driver labeled in plain",
            "language under the chart.",
        ]
        add_bullets(slide, bullets, Inches(9.4), Inches(2.0),
                    Inches(3.7), Inches(5.0), size=13)
    notes_s13 = (
        "Most demos hand-wave explainability with SHAP. We do the EXACT "
        "decomposition. This makes the model behave like a triage assistant - "
        "a SOC analyst reads 'auth_failure_ratio of 0.75 raised risk by 2.33 "
        "log-odds' and knows what to investigate."
    )
    slide_composers.append((s13, notes_s13))

    # ---------- 14. WOW: Counterfactual ---------------------------------
    def s14(slide):
        add_accent_bar(slide); add_header(slide, "Wow #2 — Counterfactual recommender")
        add_image(slide, "counterfactual_demo.png",
                  Inches(0.5), Inches(1.1), width=Inches(8.6))
        add_text_block(slide, "/counterfactual", Inches(9.4), Inches(1.2),
                       Inches(3.7), Inches(0.5),
                       size=20, color=ACCENT, bold=True, mono=True)
        bullets = [
            "explain  =  WHY",
            "counterfactual  =  WHAT TO DO",
            "",
            "For each feature j:",
            "    smallest raw change to",
            "    bring P(risk) below 20%",
            "",
            "Exact inverse of the linear",
            "model. Not a heuristic.",
            "",
            "Result is a ranked table of",
            "single-feature interventions.",
            "Combine in practice.",
        ]
        add_bullets(slide, bullets, Inches(9.4), Inches(1.9),
                    Inches(3.7), Inches(5.0), size=13)
    notes_s14 = (
        "Counterfactual XAI is an active 2024 research area. Few capstones "
        "implement it. The math is exact for our linear model. Demo on stage: "
        "pick the failed-logon-storm preset, system literally suggests "
        "'reduce auth_failure_ratio from 0.75 to 0.04'."
    )
    slide_composers.append((s14, notes_s14))

    # ---------- 14b. WOW: XGBoost + threshold tuning --------------------
    def s14b(slide):
        add_accent_bar(slide); add_header(slide, "Wow #3 — XGBoost + cost-aware threshold tuning")
        # Left column: XGBoost
        add_text_block(slide, "Three models compared, MLflow picks the winner",
                       Inches(0.6), Inches(1.2), Inches(6), Inches(0.5),
                       size=18, color=ACCENT, bold=True)
        add_bullets(slide, [
            "logistic_regression_baseline    - linear, interpretable, sidecar",
            "random_forest_model              - non-linear, robust baseline",
            "xgboost_model                    - gradient boosting, top performer",
            "",
            "All three logged to MLflow tracking.",
            "Winner aliased Production in the Model Registry.",
            "Loser's role: LR is kept loaded as a sidecar so",
            "/counterfactual still works when a tree wins.",
            "",
            "/explain handles BOTH:",
            "    linear -> exact coefficient * scaled_value decomposition",
            "    XGBoost -> exact TreeSHAP via booster.predict(pred_contribs=True)",
        ], Inches(0.6), Inches(1.7), Inches(6.2), Inches(5.5), size=12)

        # Right column: threshold tuning
        add_text_block(slide, "Cost-aware threshold tuning",
                       Inches(7.0), Inches(1.2), Inches(6), Inches(0.5),
                       size=18, color=ACCENT, bold=True)
        add_bullets(slide, [
            "Default cutoff is 0.5. Operationally it should NOT be.",
            "Validation-set precision / recall / F1 curve computed at train time;",
            "saved to threshold_analysis.json per model.",
            "",
            "Two API endpoints expose this:",
            "    GET  /threshold_analysis        full curve + F1-optimal threshold",
            "    POST /cost_optimal_threshold    given {cost_fp, cost_fn},",
            "                                     return the threshold that",
            "                                     minimizes expected cost.",
            "",
            "UI: PR curve + cost-matrix calculator.",
            "Analyst inputs:  cost of analyst time  vs  cost of missed breach.",
            "System outputs:  the threshold that minimizes total expected loss.",
        ], Inches(7.0), Inches(1.7), Inches(6.0), Inches(5.5), size=12)
    notes_s14b = (
        "This slide is the third wow. It does two things at once: (1) "
        "demonstrates that we train three models and pick the winner by "
        "MLflow-tracked validation metrics; (2) operationalizes the "
        "threshold-tuning insight that most ML capstones skip. The "
        "cost-matrix calculator is the part to demo live - input a 100-to-1 "
        "FN-vs-FP cost and the system recommends a much lower threshold "
        "than 0.5, which is exactly what a real SOC would want."
    )
    slide_composers.append((s14b, notes_s14b))

    # ---------- 15. Hosting + test script -------------------------------
    def s15(slide):
        add_accent_bar(slide); add_header(slide, "Hosting + test script")
        bullets = [
            f"Live URL:   {LIVE_URL}",
            f"API:        {API_URL}",
            "",
            "test_project.py at repo root.  Six end-to-end checks:",
            "    /health      -> model_loaded == True",
            "    /model_info  -> metrics surface",
            "    /features    -> contract returned",
            "    /predict     -> {full / sparse / legacy-flat payloads}",
            "",
            "Single command:",
            f"    python test_project.py --url {API_URL}",
            "",
            "Exit 0 on success, 1 on any failure.",
            "CI workflow runs this on every push (.github/workflows/ci.yml).",
        ]
        add_bullets(slide, bullets, Inches(0.7), Inches(1.2),
                    Inches(12), Inches(6), size=16)
    notes_s15 = (
        "Run the smoke test on stage. PASS shows up at the end. That's the "
        "same script the grader will run."
    )
    slide_composers.append((s15, notes_s15))

    # ---------- 16. The pivot -------------------------------------------
    def s16(slide):
        add_accent_bar(slide); add_header(slide, "The pivot — Databricks → AWS")
        add_image(slide, "pivot_table.png",
                  Inches(0.5), Inches(1.1), width=Inches(12.5))
        add_text_block(slide,
            "Started on Databricks. Hit free-tier storage limits on the 11 GB "
            "dataset. Rerouted to AWS equivalents WITHOUT changing the architecture. "
            "Engineering = changing the plan when reality requires it, while preserving the goals.",
            Inches(0.7), Inches(6.3), Inches(12), Inches(1.1),
            size=15, color=NAVY)
    notes_s16 = (
        "Frame the pivot as a strength, not a weakness. Every capability the "
        "rubric requires is still present."
    )
    slide_composers.append((s16, notes_s16))

    # ---------- 17. Limitations + future work ---------------------------
    def s17(slide):
        add_accent_bar(slide); add_header(slide, "Limitations & future work")
        add_text_block(slide, "Honest caveats",
                       Inches(0.7), Inches(1.2), Inches(6), Inches(0.5),
                       size=20, color=ACCENT, bold=True)
        add_bullets(slide, [
            "Single dataset; generalization not validated.",
            "Time is relative seconds; no diurnal features.",
            "No streaming layer (offline batch only).",
            "Red-team campaign ends mid-dataset;",
            "    stratified random split with disclosure.",
        ], Inches(0.7), Inches(1.7), Inches(6), Inches(4.5), size=15)

        add_text_block(slide, "Future work, by impact",
                       Inches(7.0), Inches(1.2), Inches(6), Inches(0.5),
                       size=20, color=ACCENT, bold=True)
        add_bullets(slide, [
            "1.  Per-cost-matrix threshold tuning.",
            "      analyst would supply FP-cost / FN-cost; the system picks",
            "      the threshold that minimizes expected operational cost.",
            "2.  Streaming: Kinesis -> Spark Structured Streaming -> live scoring.",
            "3.  Automated retraining: EventBridge cron -> EMR Step + train_model.",
            "4.  Multi-feature counterfactual paths (ensemble of interventions).",
        ], Inches(7.0), Inches(1.7), Inches(6), Inches(4.5), size=13)
    notes_s17 = "Show what you didn't do. Honesty + specific roadmap signals real understanding."
    slide_composers.append((s17, notes_s17))

    # ---------- 18. Thank you / Q&A -------------------------------------
    def s18(slide):
        bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0), Inches(0),
            prs.slide_width, prs.slide_height,
        )
        bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
        strip = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0), Inches(0),
            Inches(0.25), prs.slide_height,
        )
        strip.fill.solid(); strip.fill.fore_color.rgb = ACCENT; strip.line.fill.background()

        add_text_block(slide, "Thank you. Questions?",
                       Inches(1.2), Inches(1.8), Inches(11), Inches(1.5),
                       size=48, color=WHITE, bold=True)
        add_text_block(slide, "Live demo follows.",
                       Inches(1.2), Inches(3.3), Inches(11), Inches(0.6),
                       size=22, color=RGBColor(0xD1, 0xD5, 0xDB))

        urls = [
            f"Live URL       {LIVE_URL}",
            f"API            {API_URL}",
            f"Repository     {GITHUB_URL}",
        ]
        tb = slide.shapes.add_textbox(
            Inches(1.2), Inches(5.3), Inches(11), Inches(1.5),
        )
        tf = tb.text_frame; tf.word_wrap = True
        first = True
        for line in urls:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            r = p.add_run()
            r.text = line
            r.font.size = Pt(16); r.font.color.rgb = RGBColor(0xE5, 0xE7, 0xEB)
            r.font.name = "Consolas"
            p.space_after = Pt(4)
    notes_s18 = (
        "Close confidently. Repeat the live URL. Prepared Q&A topics: "
        "(1) why stratified random split, (2) why precision so low, "
        "(3) why sklearn after Spark, (4) /counterfactual vs SHAP, "
        "(5) what about cost overruns, (6) what would streaming change."
    )
    slide_composers.append((s18, notes_s18))

    # ===================================================================
    # Build the deck
    # ===================================================================
    total = len(slide_composers)
    for idx, (composer, notes) in enumerate(slide_composers, start=1):
        slide = new_slide(notes=notes)
        composer(slide)
        # Add page number on every non-title slide (skip 1 and last for cleanliness)
        if idx not in (1, total):
            add_page_number(slide, idx, total)

    prs.save(str(OUT))
    missing = [
        n for n in [
            "data_volumes.png", "class_imbalance.png",
            "architecture_diagram.png", "medallion_diagram.png",
            "feature_importances.png", "metric_dashboard.png",
            "explainer_demo.png", "counterfactual_demo.png",
            "pivot_table.png", "pipeline_timeline.png",
        ] if not _asset(n)
    ]
    print(f"Wrote {OUT}")
    print(f"  {total} slides")
    if missing:
        print(
            f"  WARNING: {len(missing)} image asset(s) missing - slides will "
            f"still render but some panels will be empty:"
        )
        for m in missing:
            print(f"    - {m}")
        print(
            "  Fix by running:  py scripts/generate_presentation_assets.py"
        )
    else:
        print("  All image assets embedded.")
    print(
        "  Open in PowerPoint / Google Slides / Keynote. "
        "Speaker notes are baked in (View -> Speaker Notes)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
