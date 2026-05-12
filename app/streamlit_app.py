"""
app/streamlit_app.py
====================

Streamlit web application for the LANL Threat Prediction Pipeline.

What this UI is for
-------------------
This is the human-facing window into the model. A grader, an instructor, a
SOC analyst, or a curious teammate should be able to:
    1. Understand what the system predicts.
    2. Pick or build an input scenario for one computer in one event-time
       window.
    3. See the prediction, the probability, and a clear interpretation.
    4. Get a sense of how confident the model is and which behaviors drive
       the prediction up or down.

Design principles
-----------------
- Explain everything in plain language; do not assume the viewer knows
  what "logon_type" means.
- Group features by source (auth / flows / dns / proc / derived) so the
  form is scannable instead of a wall of numbers.
- Provide preset scenarios so the demo never starts on a confusing blank
  form.
- Make the output emotionally legible: green/amber/red, a gauge, a bar
  chart, and a one-sentence interpretation.
- Show the pipeline story (bronze -> silver -> gold -> model) in a side
  tab so the project can be defended without leaving the app.

Run locally
-----------
    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Streamlit Cloud (and `streamlit run app/streamlit_app.py` in general) only
# puts the script's own directory on sys.path - NOT the repo root. So a bare
# `from config.settings import settings` fails with ModuleNotFoundError unless
# we explicitly add the repo root first.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd
import requests
import streamlit as st

# Plotly is used for the verdict gauge. Importing it inside a try/except so
# the app still loads in environments where Plotly isn't installed - it just
# falls back to the simpler bar chart in that case.
try:
    import plotly.graph_objects as go
    _PLOTLY_OK = True
except ImportError:
    _PLOTLY_OK = False

from config.settings import settings


# ============================================================
# CONSTANTS
# ============================================================
# The API URL is configurable so we can point the UI at:
# - localhost during dev
# - an EC2 internal address during cloud demo
# - a load balancer URL in production
API_URL = os.getenv("LANL_API_URL", "http://127.0.0.1:8000")

LOCAL_MODEL_DIR = Path(os.getenv("LANL_LOCAL_MODEL_DIR", "./model_outputs"))
FEATURE_NAMES_FILE = LOCAL_MODEL_DIR / "feature_names.json"
BEST_MODEL_SUMMARY_FILE = LOCAL_MODEL_DIR / "best_model_summary.json"
FEATURE_IMPORTANCES_FILE = LOCAL_MODEL_DIR / "feature_importances.json"


# ============================================================
# PAGE CONFIG  (must be the first Streamlit call)
# ============================================================
st.set_page_config(
    page_title="LANL Threat Operations",
    page_icon="*",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# STYLING — cyber-security operations dashboard
# ============================================================
# A SOC-tool aesthetic: near-black canvas, mint-green ARMED accent, amber for
# elevated risk, deep red with glow for high-risk verdicts. Monospace surfaces
# for technical values (model name, feature counts) reinforce the analyst-tool
# feel without becoming Matrix kitsch.
st.markdown(
    """
    <style>
    /* ---- Global typography + canvas tweaks ------------------------------ */
    html, body, [data-testid="stAppViewContainer"] {
        background: #0A0E1A;
        color: #E5E7EB;
    }
    h1, h2, h3, h4 {
        color: #F3F4F6 !important;
        letter-spacing: -0.01em;
    }
    /* Light-mode override: Streamlit applies inline styles to some elements */
    code, kbd, samp {
        background: rgba(16, 242, 162, 0.08) !important;
        color: #10F2A2 !important;
        padding: 0.1rem 0.4rem;
        border-radius: 4px;
        font-size: 0.9em;
    }

    /* ---- Sidebar -------------------------------------------------------- */
    [data-testid="stSidebar"] {
        background: #0F1623 !important;
        border-right: 1px solid #1F2937;
    }
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #10F2A2 !important;
        font-size: 0.85rem !important;
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 0.6rem;
    }

    /* ---- Page header banner -------------------------------------------- */
    .cyber-banner {
        border-left: 4px solid #10F2A2;
        padding: 0.9rem 1.4rem 0.9rem 1.2rem;
        margin: 0 0 1.4rem 0;
        background: linear-gradient(90deg, rgba(16, 242, 162, 0.06) 0%, transparent 80%);
    }
    .cyber-status {
        color: #10F2A2;
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        font-size: 0.78rem;
        letter-spacing: 0.18em;
        margin-bottom: 0.35rem;
        text-transform: uppercase;
    }
    .cyber-status .pulse {
        display: inline-block;
        width: 0.55rem;
        height: 0.55rem;
        border-radius: 50%;
        background: #10F2A2;
        box-shadow: 0 0 12px #10F2A2;
        margin-right: 0.55rem;
        vertical-align: middle;
        animation: cyber-pulse 1.8s infinite;
    }
    @keyframes cyber-pulse {
        0%   { opacity: 1.0; transform: scale(1.0); }
        50%  { opacity: 0.45; transform: scale(1.15); }
        100% { opacity: 1.0; transform: scale(1.0); }
    }
    .cyber-banner h1 {
        margin: 0 0 0.3rem 0 !important;
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #FFFFFF 0%, #10F2A2 90%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .cyber-banner p {
        color: #9CA3AF !important;
        margin: 0 !important;
        font-size: 0.96rem !important;
    }

    /* ---- Verdict cards (high / medium / low risk) ---------------------- */
    .verdict-card {
        padding: 1.1rem 1.4rem;
        border-radius: 10px;
        border: 1px solid;
        margin-bottom: 1rem;
        font-family: 'Inter', sans-serif;
    }
    .verdict-title {
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        margin-bottom: 0.35rem;
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        text-transform: uppercase;
    }
    .verdict-sub { font-size: 0.95rem; opacity: 0.88; }

    .verdict-low {
        background: linear-gradient(135deg, rgba(16, 242, 162, 0.08) 0%, rgba(16, 242, 162, 0.02) 100%);
        border-color: rgba(16, 242, 162, 0.45);
        color: #10F2A2;
    }
    .verdict-medium {
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.10) 0%, rgba(245, 158, 11, 0.02) 100%);
        border-color: rgba(245, 158, 11, 0.45);
        color: #F59E0B;
    }
    .verdict-high {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(239, 68, 68, 0.02) 100%);
        border-color: rgba(239, 68, 68, 0.55);
        color: #F87171;
        box-shadow: 0 0 28px rgba(239, 68, 68, 0.18);
    }
    .verdict-low .verdict-sub,
    .verdict-medium .verdict-sub,
    .verdict-high .verdict-sub { color: #E5E7EB; }

    /* ---- Sidebar API-status badge -------------------------------------- */
    .api-status-online {
        background: rgba(16, 242, 162, 0.12);
        border: 1px solid rgba(16, 242, 162, 0.45);
        padding: 0.7rem 0.9rem;
        border-radius: 8px;
        color: #10F2A2;
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        font-size: 0.85rem;
        line-height: 1.4;
    }
    .api-status-online .label {
        font-size: 0.72rem;
        letter-spacing: 0.18em;
        opacity: 0.85;
        text-transform: uppercase;
    }
    .api-status-offline {
        background: rgba(239, 68, 68, 0.10);
        border: 1px solid rgba(239, 68, 68, 0.5);
        padding: 0.7rem 0.9rem;
        border-radius: 8px;
        color: #F87171;
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        font-size: 0.85rem;
    }

    /* ---- Metric tiles ------------------------------------------------- */
    [data-testid="stMetric"] {
        background: #111827;
        border: 1px solid #1F2937;
        border-radius: 8px;
        padding: 0.85rem 1rem;
    }
    [data-testid="stMetric"] [data-testid="stMetricLabel"] {
        color: #9CA3AF !important;
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #10F2A2 !important;
        font-family: 'JetBrains Mono', 'Consolas', monospace;
    }

    /* ---- Buttons (Predict, etc.) -------------------------------------- */
    .stButton > button {
        background: linear-gradient(135deg, #10F2A2 0%, #06B6D4 100%) !important;
        color: #0A0E1A !important;
        font-weight: 700 !important;
        font-family: 'JetBrains Mono', 'Consolas', monospace !important;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        border: none !important;
        border-radius: 6px !important;
        box-shadow: 0 0 24px rgba(16, 242, 162, 0.25);
        transition: all 0.18s ease;
    }
    .stButton > button:hover {
        box-shadow: 0 0 36px rgba(16, 242, 162, 0.55);
        transform: translateY(-1px);
    }

    /* ---- Form inputs -------------------------------------------------- */
    [data-baseweb="input"] input,
    [data-baseweb="select"] {
        background: #1F2937 !important;
        color: #E5E7EB !important;
        border-color: #374151 !important;
    }
    .stNumberInput [data-baseweb="input"] {
        background: #1F2937 !important;
    }

    /* ---- Expander headers --------------------------------------------- */
    [data-testid="stExpander"] {
        background: #111827;
        border: 1px solid #1F2937;
        border-radius: 8px;
    }
    [data-testid="stExpander"] summary {
        color: #10F2A2;
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        font-size: 0.85rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    /* ---- Tabs --------------------------------------------------------- */
    [data-baseweb="tab-list"] {
        gap: 0.25rem;
        border-bottom: 1px solid #1F2937;
    }
    [data-baseweb="tab"] {
        color: #9CA3AF !important;
        background: transparent !important;
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        font-size: 0.85rem !important;
    }
    [data-baseweb="tab"][aria-selected="true"] {
        color: #10F2A2 !important;
        border-bottom: 2px solid #10F2A2 !important;
    }

    /* ---- Dataframes --------------------------------------------------- */
    [data-testid="stDataFrame"] {
        background: #111827;
        border-radius: 6px;
    }

    /* ---- Captions / muted text --------------------------------------- */
    .small-muted { font-size: 0.85rem; color: #6B7280; }
    [data-testid="stCaption"] { color: #9CA3AF !important; }

    /* ---- Hide the Streamlit "Made with" footer for a cleaner SOC look -- */
    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATA / METADATA LOADERS
# ============================================================
@st.cache_data(show_spinner=False)
def load_feature_names() -> list[str]:
    """Read the feature list the model expects.

    Cached so we don't re-read the JSON on every interaction.
    """
    if not FEATURE_NAMES_FILE.exists():
        return []
    return json.loads(FEATURE_NAMES_FILE.read_text(encoding="utf-8"))["feature_names"]


@st.cache_data(show_spinner=False)
def load_best_summary() -> dict[str, Any]:
    """Read the best-model summary (name, metrics, path)."""
    if not BEST_MODEL_SUMMARY_FILE.exists():
        return {}
    return json.loads(BEST_MODEL_SUMMARY_FILE.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_feature_importances() -> list[tuple[str, float]]:
    """Read feature importances saved by jobs/train_model.py."""
    if not FEATURE_IMPORTANCES_FILE.exists():
        return []
    payload = json.loads(FEATURE_IMPORTANCES_FILE.read_text(encoding="utf-8"))
    return [(item[0], float(item[1])) for item in payload.get("importances", [])]


def _build_gauge(prob: float) -> "go.Figure | None":
    """Plotly gauge re-themed for the cyber-SOC dashboard.

    The needle and ticks use the mint-green ARMED accent against the dark
    canvas. Risk bands stay green / amber / red so the operational meaning
    is unchanged, but the colors are tuned for legibility on the dark
    background rather than against a default light theme.
    """
    if not _PLOTLY_OK:
        return None
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=prob * 100,
            number={
                "suffix": " %",
                "font": {"size": 36, "color": "#E5E7EB", "family": "JetBrains Mono, Consolas, monospace"},
            },
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": "#374151",
                    "tickfont": {"color": "#9CA3AF", "size": 11},
                },
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "bar": {"color": "#10F2A2", "thickness": 0.22},
                "steps": [
                    {"range": [0,  20], "color": "rgba(16, 242, 162, 0.18)"},
                    {"range": [20, 60], "color": "rgba(245, 158, 11, 0.22)"},
                    {"range": [60,100], "color": "rgba(239, 68,  68, 0.30)"},
                ],
                "threshold": {
                    "line":  {"color": "#F87171", "width": 3},
                    "thickness": 0.85,
                    "value": prob * 100,
                },
            },
            title={
                "text": "NEXT-WINDOW RED-TEAM PROBABILITY",
                "font": {"size": 12, "color": "#9CA3AF", "family": "JetBrains Mono, Consolas, monospace"},
            },
        )
    )
    fig.update_layout(
        height=280,
        margin=dict(l=20, r=20, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def fetch_api_health() -> dict[str, Any] | None:
    """Check whether the FastAPI service is up."""
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        return None
    return None


# ============================================================
# FEATURE-GROUP DESCRIPTIONS
# ============================================================
# Plain-language descriptions of each feature family. These show up in the
# UI as captions so a viewer who has never heard of LANL still understands
# what they are looking at.
FEATURE_GROUP_DESCRIPTIONS = {
    "auth": (
        "Authentication behavior - logons this computer initiated (src) and "
        "received (dst), how many succeeded, how many failed, how many unique "
        "users and machines were involved."
    ),
    "flows": (
        "Network flow behavior - outbound and inbound flows, bytes, packets, "
        "unique peers and ports. Spikes here can mean lateral movement or "
        "exfiltration."
    ),
    "dns": (
        "DNS lookup behavior - how often this computer asked to resolve a "
        "hostname, and to how many distinct targets. Compromised hosts often "
        "scan or beacon."
    ),
    "proc": (
        "Process lifecycle behavior - process START / END events, how many "
        "distinct users and process names appeared, and the start/end "
        "imbalance."
    ),
    "derived": (
        "Combined behavioral ratios such as failure rates and bytes-per-event. "
        "These often carry stronger signal than raw counts."
    ),
    "time": (
        "Window / time bookkeeping features. Usually not predictive on their "
        "own but kept for completeness."
    ),
    "other": "Any features that don't fit the categories above.",
}


def categorize(feat: str) -> str:
    """Map a feature name to one of our friendly groups."""
    if feat.startswith("auth_") and "_total_" not in feat and "_ratio" not in feat:
        return "auth"
    if feat.startswith("flows_") and "_total_" not in feat and "_per_event" not in feat:
        return "flows"
    if feat.startswith("dns_"):
        return "dns"
    if feat.startswith("proc_"):
        return "proc"
    if feat in {"auth_total_events", "auth_total_failures", "auth_total_successes",
                "flows_total_events", "flows_total_bytes", "flows_total_packets",
                "auth_failure_ratio", "flows_bytes_per_event", "flows_packets_per_event"}:
        return "derived"
    if feat.startswith("time_"):
        return "time"
    return "other"


# ============================================================
# PRESET SCENARIOS
# ============================================================
# A demo is dramatically more legible when the viewer can hit ONE button
# and see a meaningful prediction, rather than typing 40 zeros into a form.
# These presets are illustrative, NOT real attack data.
PRESETS: dict[str, dict[str, float]] = {
    # =================================================================
    # DEMO PRESETS — sourced from REAL rows in the gold table that the
    # served model rates at HIGH / MEDIUM / LOW risk. Use these during
    # the live presentation to show the model actually discriminating
    # across risk levels. The "synthetic" presets below them (failed-
    # logon storm, lateral movement, etc.) were calibrated for the LR
    # baseline and are kept for historical comparison.
    # =================================================================
    "Demo HIGH risk - real row (P=0.745)": {
        "auth_src_event_count": 4,
        "auth_src_success_count": 4,
        "auth_src_unique_dst_computers": 1,
        "auth_src_unique_dst_users": 1,
        "flows_out_count": 12,
        "flows_out_unique_dst_computers": 2,
        "flows_out_unique_dst_ports": 2,
        "flows_out_total_duration": 109,
        "flows_out_total_packets": 36,
        "flows_out_total_bytes": 1824,
        "flows_out_mean_packets": 3,
        "flows_out_mean_bytes": 152,
        "auth_total_events": 4,
        "auth_total_successes": 4,
        "flows_total_events": 12,
        "flows_total_bytes": 1824,
        "flows_total_packets": 36,
        "flows_bytes_per_event": 152,
        "flows_packets_per_event": 3,
    },
    "Demo MEDIUM risk - real row (P=0.171)": {
        "auth_src_event_count": 1,
        "auth_src_success_count": 1,
        "auth_src_unique_dst_computers": 1,
        "auth_src_unique_dst_users": 1,
        "flows_out_count": 22,
        "flows_out_unique_dst_computers": 1,
        "flows_out_unique_dst_ports": 1,
        "flows_out_total_packets": 22,
        "flows_out_total_bytes": 1012,
        "flows_out_mean_packets": 1,
        "flows_out_mean_bytes": 46,
        "auth_total_events": 1,
        "auth_total_successes": 1,
        "flows_total_events": 22,
        "flows_total_bytes": 1012,
        "flows_total_packets": 22,
        "flows_bytes_per_event": 46,
        "flows_packets_per_event": 1,
    },
    "Demo LOW risk - real row (P=0.072)": {
        "auth_src_event_count": 7,
        "auth_src_success_count": 7,
        "auth_src_unique_dst_computers": 3,
        "auth_src_unique_dst_users": 1,
        "proc_event_count": 10,
        "proc_start_count": 10,
        "proc_unique_users": 1,
        "proc_unique_processes": 6,
        "proc_start_end_imbalance": 10,
        "auth_total_events": 7,
        "auth_total_successes": 7,
    },
    # ----- Historical / synthetic presets (calibrated for LR) ---------
    "Quiet workstation": {
        "auth_total_events": 8, "auth_total_failures": 0, "auth_total_successes": 8,
        "flows_total_events": 15, "flows_total_bytes": 4_200, "flows_total_packets": 60,
        "dns_lookup_count": 3, "dns_unique_resolved_computers": 2,
        "proc_event_count": 12, "proc_start_count": 6, "proc_end_count": 6,
    },
    "Busy admin host": {
        "auth_total_events": 120, "auth_total_failures": 2, "auth_total_successes": 118,
        "auth_src_unique_dst_computers": 18,
        "flows_total_events": 410, "flows_total_bytes": 9_800_000, "flows_total_packets": 41_000,
        "dns_lookup_count": 35, "dns_unique_resolved_computers": 22,
        "proc_event_count": 95, "proc_start_count": 48, "proc_end_count": 47,
    },
    "Suspicious - failed-logon storm": {
        "auth_total_events": 240, "auth_total_failures": 180, "auth_total_successes": 60,
        "auth_src_unique_dst_computers": 65, "auth_src_unique_dst_users": 80,
        "auth_failure_ratio": 0.75,
        "flows_total_events": 70, "flows_total_bytes": 9_000,
        "dns_lookup_count": 2, "dns_unique_resolved_computers": 2,
        "proc_event_count": 8, "proc_start_count": 5, "proc_end_count": 3,
        "proc_start_end_imbalance": 2,
    },
    "Suspicious - lateral movement": {
        "auth_total_events": 70, "auth_total_failures": 25, "auth_total_successes": 45,
        "auth_src_unique_dst_computers": 38, "auth_src_unique_dst_users": 14,
        "auth_failure_ratio": 0.36,
        "flows_total_events": 620, "flows_total_bytes": 1_500_000,
        "flows_out_unique_dst_computers": 31, "flows_out_unique_dst_ports": 19,
        "dns_lookup_count": 48, "dns_unique_resolved_computers": 34,
        "proc_event_count": 56, "proc_start_count": 34, "proc_end_count": 22,
        "proc_start_end_imbalance": 12,
    },
}


# ============================================================
# HEADER  (cyber-themed banner instead of plain st.title)
# ============================================================
st.markdown(
    """
    <div class="cyber-banner">
        <div class="cyber-status">
            <span class="pulse"></span>SECURITY OPERATIONS / NEXT-WINDOW THREAT PREDICTION
        </div>
        <h1>LANL Threat Operations Dashboard</h1>
        <p>End-to-end distributed pipeline (S3 &middot; EMR &middot; Spark &middot;
           MLflow &middot; FastAPI &middot; Streamlit) with explainable + counterfactual XAI
           for next-window red-team prediction.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR  (system status + global controls)
# ============================================================
with st.sidebar:
    st.header("System Status")

    health = fetch_api_health()
    if health:
        st.markdown(
            f"""
            <div class="api-status-online">
                <div class="label">API STATUS</div>
                <div style="font-size:1.05rem;font-weight:700;">[ ONLINE ]</div>
                <div style="margin-top:0.3rem;color:#E5E7EB;">
                    model &nbsp; <code>{health.get('model_name', '?')}</code><br/>
                    features &nbsp; <code>{health.get('feature_count', '?')}</code>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="api-status-offline">
                <div style="font-weight:700;">[ OFFLINE ]</div>
                <div style="margin-top:0.3rem;color:#E5E7EB;">
                    Cannot reach <code>{API_URL}/health</code>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "Start the API with:  "
            "`uvicorn app.api_app:app --host 0.0.0.0 --port 8000`"
        )

    st.divider()

    st.header("Quick presets")
    st.caption(
        "Pre-built feature scenarios for demoing. Pick one to populate the form."
    )
    preset_choice = st.selectbox(
        "Scenario", ["(choose...)"] + list(PRESETS.keys()),
        help="Each preset is an illustrative behavior pattern, not real telemetry."
    )

    st.divider()
    st.header("About")
    st.caption(
        "This is a capstone project. The model predicts compromise risk one "
        "window ahead - it does NOT label the current window. That design "
        "choice is what keeps the evaluation honest."
    )


# ============================================================
# LOAD FEATURE LIST + SUMMARY
# ============================================================
feature_names = load_feature_names()
best_summary = load_best_summary()

if not feature_names:
    st.error(
        f"Feature list not found at `{FEATURE_NAMES_FILE}`. "
        "Train the model first with `python -m jobs.train_model` "
        "(or `python run_local_demo.py`)."
    )
    st.stop()


# ============================================================
# TABS  (predict / metrics / architecture / how it works)
# ============================================================
tab_predict, tab_metrics, tab_arch, tab_explain = st.tabs(
    ["Predict", "Model metrics", "Architecture", "How it works"]
)


# ----------------------------------------------------------------------
# TAB 1 - PREDICT
# ----------------------------------------------------------------------
with tab_predict:
    left, right = st.columns([1.15, 1.0], gap="large")

    # --- LEFT: input form ------------------------------------------------
    with left:
        st.subheader("Input features")
        st.caption(
            "Each field describes one computer's behavior during ONE event-time "
            "window (the windows are one hour each in this pipeline). Missing "
            "values default to 0, which the model reads as 'no observed activity'."
        )

        # Apply a preset if the user picked one
        preset_values: dict[str, float] = {}
        if preset_choice != "(choose...)":
            preset_values = PRESETS.get(preset_choice, {})
            st.info(f"Preset loaded: **{preset_choice}**. Edit any field below to refine.")

        # Streamlit gotcha: `st.number_input(value=..., key=...)` only honors
        # the `value=` on FIRST render. After that the widget reads from
        # st.session_state[key]. So a preset-dropdown change re-runs the
        # script but does NOT update the form. Fix it by writing the preset
        # values directly to session_state whenever the dropdown changes.
        _last_preset_key = "__last_preset"
        if _last_preset_key not in st.session_state:
            st.session_state[_last_preset_key] = "(choose...)"

        if preset_choice != st.session_state[_last_preset_key]:
            for _f in feature_names:
                st.session_state[f"input_{_f}"] = float(preset_values.get(_f, 0.0))
            st.session_state[_last_preset_key] = preset_choice

        # Group features by source
        grouped: dict[str, list[str]] = {}
        for feat in feature_names:
            grouped.setdefault(categorize(feat), []).append(feat)

        # Important groups expanded by default for visibility
        default_open = {"auth", "flows", "derived"}

        inputs: dict[str, float] = {}

        # Render each group as an expander
        group_order = ["derived", "auth", "flows", "dns", "proc", "time", "other"]
        for group_name in group_order:
            feats = grouped.get(group_name, [])
            if not feats:
                continue
            with st.expander(
                f"{group_name.upper()}  -  {len(feats)} feature(s)",
                expanded=(group_name in default_open),
            ):
                st.caption(FEATURE_GROUP_DESCRIPTIONS.get(group_name, ""))
                # Use 2-column layout inside the expander to compact the form
                cols = st.columns(2)
                for i, feat in enumerate(feats):
                    with cols[i % 2]:
                        inputs[feat] = st.number_input(
                            label=feat,
                            value=float(preset_values.get(feat, 0.0)),
                            step=1.0,
                            format="%.4f",
                            key=f"input_{feat}",
                        )

        predict_clicked = st.button("Predict next-window risk", type="primary",
                                    use_container_width=True)

    # --- RIGHT: results --------------------------------------------------
    with right:
        st.subheader("Prediction")
        st.caption(
            "The model returns a probability between 0 and 1 that this computer "
            "will show red-team activity in the NEXT window."
        )

        if predict_clicked:
            try:
                response = requests.post(
                    f"{API_URL}/predict",
                    json={"features": inputs},
                    timeout=30,
                )
                response.raise_for_status()
                result = response.json()

                pred = int(result["prediction"])
                prob = float(result["probability_redteam_next_window"])
                model_name = result.get("model_name", "?")

                # ---- Verdict card -------------------------------------
                if prob < 0.20:
                    verdict_class = "verdict-low"
                    verdict_title = "Low predicted risk"
                    verdict_sub = (
                        "The model does not expect red-team activity on this "
                        "computer in the next window."
                    )
                elif prob < 0.60:
                    verdict_class = "verdict-medium"
                    verdict_title = "Elevated predicted risk"
                    verdict_sub = (
                        "Behavior in the current window resembles patterns the "
                        "model has seen ahead of compromise. Worth a closer look."
                    )
                else:
                    verdict_class = "verdict-high"
                    verdict_title = "High predicted risk"
                    verdict_sub = (
                        "The model strongly expects red-team activity in the "
                        "next window. Recommend investigating this computer."
                    )

                st.markdown(
                    f"""
                    <div class="verdict-card {verdict_class}">
                        <div class="verdict-title">{verdict_title}</div>
                        <div class="verdict-sub">{verdict_sub}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # ---- Metric tiles -------------------------------------
                m1, m2, m3 = st.columns(3)
                m1.metric(
                    "Predicted class",
                    "Red-team (1)" if pred == 1 else "Benign (0)",
                )
                m2.metric(
                    "Probability (next window)",
                    f"{prob:.2%}",
                )
                m3.metric("Model", model_name)

                # ---- Risk gauge (primary visualization) ---------------
                gauge = _build_gauge(prob)
                if gauge is not None:
                    st.plotly_chart(gauge, use_container_width=True)

                # ---- Probability split bar (secondary view) -----------
                st.markdown("**Probability split**")
                chart_df = pd.DataFrame(
                    {
                        "Outcome": ["No red-team activity", "Red-team activity"],
                        "Probability": [1 - prob, prob],
                    }
                ).set_index("Outcome")
                st.bar_chart(chart_df, height=180)

                # ---- WHY: per-feature contribution (explainable AI) ----
                # Call /explain to decompose the prediction. For the linear
                # baseline model, contribution = scaled_value * coefficient
                # for each feature - the EXACT log-odds decomposition, not
                # a SHAP approximation.
                try:
                    exp_response = requests.post(
                        f"{API_URL}/explain",
                        json={"features": inputs},
                        timeout=30,
                    )
                    if exp_response.status_code == 200:
                        exp = exp_response.json()
                        contribs = exp.get("contributions", [])
                        method = exp.get("method", "")

                        SUPPORTED_METHODS = {
                            "linear_log_odds_decomposition",
                            "xgboost_treeshap",
                            "lightgbm_treeshap",
                        }
                        if method in SUPPORTED_METHODS and contribs:
                            st.markdown("---")
                            st.subheader("Why this prediction?")
                            method_blurb = {
                                "linear_log_odds_decomposition":
                                    "exact `coefficient x scaled_input` from the linear model",
                                "xgboost_treeshap":
                                    "exact TreeSHAP via `booster.predict(pred_contribs=True)`",
                                "lightgbm_treeshap":
                                    "exact TreeSHAP via `booster.predict(pred_contrib=True)`",
                            }.get(method, "")
                            st.caption(
                                "Each feature's exact contribution to the model's "
                                "log-odds for next-window red-team activity. "
                                "**Red bars push risk UP** (toward compromised); "
                                "**green bars push risk DOWN** (toward benign). "
                                f"Source: {method_blurb}."
                            )

                            top = contribs[:12]
                            exp_df = pd.DataFrame(top).sort_values(
                                "contribution", ascending=True
                            )
                            colors = [
                                "#ef4444" if c > 0 else "#10b981"
                                for c in exp_df["contribution"]
                            ]

                            if _PLOTLY_OK:
                                fig_exp = go.Figure(
                                    go.Bar(
                                        x=exp_df["contribution"],
                                        y=exp_df["feature"],
                                        orientation="h",
                                        marker_color=colors,
                                        text=[
                                            f"raw={r:.2f}"
                                            for r in exp_df["raw_value"]
                                        ],
                                        textposition="outside",
                                        hovertemplate=(
                                            "<b>%{y}</b><br>"
                                            "Contribution: %{x:+.4f}<br>"
                                            "<extra></extra>"
                                        ),
                                    )
                                )
                                fig_exp.update_layout(
                                    height=480,
                                    margin=dict(l=10, r=10, t=20, b=40),
                                    xaxis_title="Contribution to log-odds  "
                                                "(negative = lowers risk, positive = raises risk)",
                                    yaxis_title="",
                                    showlegend=False,
                                )
                                fig_exp.add_vline(
                                    x=0, line_width=1.5,
                                    line_dash="dash", line_color="gray",
                                )
                                st.plotly_chart(fig_exp, use_container_width=True)
                            else:
                                # Plotly fallback - simple bar chart
                                st.bar_chart(
                                    exp_df.set_index("feature")["contribution"],
                                    height=400,
                                )

                            # Plain-language summary of the top driver
                            top_driver = contribs[0]
                            direction = "raised" if top_driver["contribution"] > 0 else "lowered"
                            st.markdown(
                                f"**Top driver:** `{top_driver['feature']}` "
                                f"(raw value `{top_driver['raw_value']:.2f}`) "
                                f"**{direction}** the predicted risk by "
                                f"`{abs(top_driver['contribution']):.4f}` log-odds."
                            )
                        elif method == "unsupported":
                            st.caption(
                                "Per-prediction decomposition requires a linear "
                                "model; the served model is non-linear. See the "
                                "Model metrics tab for global feature importance."
                            )
                except requests.RequestException:
                    pass  # explainer is a nice-to-have; never block the predict flow

                # ---- HOW TO LOWER: counterfactual recommender --------
                # /explain tells you WHY a prediction was high.
                # /counterfactual tells you WHAT TO CHANGE to bring it down.
                # For each top feature, it returns the SMALLEST raw-value
                # change (alone) that would push the predicted probability
                # below a chosen target. Exact mathematical inverse of the
                # linear model - not an approximation.
                try:
                    cf_target = 0.20  # target: "low risk" band
                    cf_response = requests.post(
                        f"{API_URL}/counterfactual",
                        json={"features": inputs, "target_probability": cf_target},
                        timeout=30,
                    )
                    if cf_response.status_code == 200:
                        cf = cf_response.json()
                        method_cf = cf.get("method", "")
                        cf_list = cf.get("interventions", [])
                        cf_note = cf.get("note", "")

                        if method_cf == "linear_counterfactual" and cf_list:
                            st.markdown("---")
                            st.subheader("How to lower this risk")
                            cur_p = cf.get("current_probability", 0.0)
                            tgt_p = cf.get("target_probability", cf_target)
                            st.caption(
                                f"Smallest single-feature interventions that would "
                                f"bring predicted risk from **{cur_p:.1%}** down "
                                f"below **{tgt_p:.0%}**. These are the exact "
                                f"mathematical inverses of the linear model - not "
                                f"approximations. In practice, an analyst would "
                                f"combine several of these for robust mitigation."
                            )

                            if not cf.get("all_feasible", True):
                                st.warning(
                                    "No single-feature change alone is "
                                    "physically feasible (would require negative "
                                    "values). The interventions below show the "
                                    "minimum-magnitude changes; combined "
                                    "interventions are needed in practice."
                                )

                            top5 = cf_list[:5]
                            display_rows = []
                            for c in top5:
                                arrow = "↓" if c["direction"] == "decrease" else "↑"
                                display_rows.append({
                                    "Feature": c["feature"],
                                    "Current": f"{c['current_raw']:.2f}",
                                    "Target": f"{c['suggested_raw']:.2f}",
                                    "Change": f"{arrow} {c['direction']} by {abs(c['delta_raw']):.2f}",
                                })
                            st.dataframe(
                                pd.DataFrame(display_rows),
                                use_container_width=True,
                                hide_index=True,
                            )

                            top_cf = cf_list[0]
                            arrow = "down" if top_cf["direction"] == "decrease" else "up"
                            st.markdown(
                                f"**Smallest single intervention:** Bring "
                                f"`{top_cf['feature']}` from "
                                f"`{top_cf['current_raw']:.2f}` "
                                f"{arrow} to `{top_cf['suggested_raw']:.2f}` "
                                f"(change of `{abs(top_cf['delta_raw']):.2f}`)."
                            )
                        elif method_cf == "linear_counterfactual" and not cf_list:
                            # Already below target - clean state
                            if "already" in cf_note.lower():
                                st.info(
                                    "Predicted risk is already at or below the "
                                    "20% target threshold - no intervention "
                                    "recommended."
                                )
                except requests.RequestException:
                    pass  # counterfactual is a nice-to-have; never block predict

                # ---- Behavior summary ---------------------------------
                st.markdown("**What you fed the model**")
                # Show only non-zero inputs so the table stays readable
                nonzero = {k: v for k, v in inputs.items() if v != 0}
                if nonzero:
                    st.dataframe(
                        pd.DataFrame(
                            sorted(nonzero.items(), key=lambda x: -abs(x[1])),
                            columns=["feature", "value"],
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.caption(
                        "All features were left at 0 - the model is essentially "
                        "predicting from 'no observed activity'. Try a preset."
                    )

                st.caption(
                    "Probabilities reflect what the model learned, not ground "
                    "truth. Always combine with analyst judgment."
                )

            except requests.HTTPError as e:
                st.error(f"API returned an error: {e.response.status_code}")
                st.code(e.response.text)
            except requests.RequestException as e:
                st.error(
                    "Could not reach the prediction API. "
                    "Is it running on the address shown in the sidebar?"
                )
                st.code(str(e))
        else:
            st.info(
                "Pick a preset in the sidebar (or fill any features) and click "
                "**Predict next-window risk**."
            )


# ----------------------------------------------------------------------
# TAB 2 - MODEL METRICS
# ----------------------------------------------------------------------
with tab_metrics:
    st.subheader("How well does the model perform?")
    st.caption(
        "Metrics are computed on a time-aware holdout: the *latest* 20 % of "
        "windows are reserved as the test set. The model never sees them "
        "during training, so these numbers represent how the model behaves "
        "on future data."
    )

    if not best_summary:
        st.warning("No `best_model_summary.json` found. Train the model first.")
    else:
        metrics = best_summary.get("metrics", {})
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Test ROC AUC", f"{metrics.get('test_roc_auc', 0):.3f}")
        col2.metric("Test PR AUC",  f"{metrics.get('test_pr_auc', 0):.3f}")
        col3.metric("Test F1",      f"{metrics.get('test_f1', 0):.3f}")
        col4.metric("Test recall",  f"{metrics.get('test_recall', 0):.3f}")

        st.markdown("**Full metric table**")
        st.dataframe(
            pd.DataFrame(
                {"metric": list(metrics.keys()), "value": list(metrics.values())}
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown(
            """
            **Why we report PR AUC, not just accuracy.**
            Red-team activity is rare. A model that always predicts "benign"
            could be 99 % accurate and 100 % useless. PR AUC and recall reflect
            the model's ability to actually catch the rare positive cases.
            """
        )

        # ---- Feature importance chart ---------------------------------
        importances = load_feature_importances()
        if importances:
            st.markdown("---")
            st.subheader("Which features drive the prediction?")
            st.caption(
                "Top 15 features by importance (random forest / XGBoost "
                "`feature_importances_` or absolute logistic-regression "
                "coefficients). Higher means the feature shifts the "
                "model's output more."
            )
            top = importances[:15]
            imp_df = (
                pd.DataFrame(top, columns=["feature", "importance"])
                  .set_index("feature")
                  .iloc[::-1]    # so the bar chart shows biggest at the top
            )
            st.bar_chart(imp_df, height=420)

        # ---- Threshold tuning + cost-matrix calculator ----------------
        # /threshold_analysis returns the validation-set PR curve. The user
        # provides FP / FN costs and the system recommends the threshold
        # that minimizes expected operational cost. This is the "cyberML"
        # threshold-tuning idea operationalized inside our API.
        try:
            thresh_resp = requests.get(
                f"{API_URL}/threshold_analysis", timeout=10
            )
            if thresh_resp.status_code == 200:
                thresh = thresh_resp.json()
                if thresh.get("available", False):
                    st.markdown("---")
                    st.subheader("Threshold tuning  /  cost-matrix calculator")
                    st.caption(
                        "The default decision threshold is 0.5, but the "
                        "operationally correct cutoff depends on the relative "
                        "cost of a missed attack vs an analyst chasing a "
                        "false alarm. The curve below is computed on the "
                        "validation set (never on test); use it to pick a "
                        "threshold that matches your operating cost ratio."
                    )

                    # PR curve + F1-vs-threshold chart
                    if _PLOTLY_OK:
                        ths = thresh.get("thresholds", [])
                        precisions = thresh.get("precisions", [])
                        recalls = thresh.get("recalls", [])
                        f1s = thresh.get("f1s", [])
                        opt_f1 = thresh.get("optimal_f1") or {}

                        if ths and f1s:
                            fig_curve = go.Figure()
                            fig_curve.add_trace(go.Scatter(
                                x=ths, y=precisions,
                                name="Precision", mode="lines",
                                line=dict(color="#10F2A2", width=2),
                            ))
                            fig_curve.add_trace(go.Scatter(
                                x=ths, y=recalls,
                                name="Recall", mode="lines",
                                line=dict(color="#06B6D4", width=2),
                            ))
                            fig_curve.add_trace(go.Scatter(
                                x=ths, y=f1s,
                                name="F1", mode="lines",
                                line=dict(color="#F59E0B", width=2.4),
                            ))
                            if opt_f1.get("threshold") is not None:
                                fig_curve.add_vline(
                                    x=opt_f1["threshold"],
                                    line_dash="dash",
                                    line_color="#F87171",
                                    annotation_text=(
                                        f"F1-optimal t = {opt_f1['threshold']:.3f}"
                                    ),
                                    annotation_position="top",
                                )
                            fig_curve.update_layout(
                                height=360,
                                margin=dict(l=10, r=10, t=30, b=40),
                                xaxis_title="Decision threshold",
                                yaxis_title="Metric value",
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                font=dict(color="#E5E7EB"),
                                xaxis=dict(gridcolor="#1F2937"),
                                yaxis=dict(gridcolor="#1F2937"),
                                legend=dict(orientation="h", y=-0.18),
                            )
                            st.plotly_chart(fig_curve, use_container_width=True)

                            if opt_f1:
                                cA, cB, cC = st.columns(3)
                                cA.metric("F1-optimal threshold",
                                          f"{opt_f1.get('threshold', 0):.3f}")
                                cB.metric("F1 at that threshold",
                                          f"{opt_f1.get('f1', 0):.3f}")
                                cC.metric("Recall at that threshold",
                                          f"{opt_f1.get('recall', 0):.3f}")

                    # ---- Interactive threshold slider -----------------
                    # The user drags a decision threshold; we look it up on
                    # the precomputed PR curve and surface precision / recall
                    # / F1 in real time. No API round-trip - the curve data
                    # is already in the page.
                    if ths and f1s:
                        st.markdown("**Interactive threshold explorer**")
                        st.caption(
                            "Drag the slider to set a decision threshold. "
                            "Precision, recall, and F1 update from the "
                            "validation-set PR curve in real time. The "
                            "F1-optimal threshold from above is the default."
                        )
                        default_t = float(
                            opt_f1.get("threshold", 0.5)
                            if opt_f1 else 0.5
                        )
                        # Slider bounds based on actual curve range
                        t_min = float(min(ths))
                        t_max = float(max(ths))
                        # Default fits inside the slider range
                        slider_default = max(t_min, min(t_max, default_t))
                        chosen_t = st.slider(
                            "Decision threshold",
                            min_value=float(t_min),
                            max_value=float(t_max),
                            value=slider_default,
                            step=max((t_max - t_min) / 200.0, 1e-6),
                            format="%.4f",
                            help=(
                                "P(predicted positive) above this value -> "
                                "flag as compromised. Default is the F1-"
                                "optimal cutoff."
                            ),
                        )
                        # Look up the closest curve point
                        ths_arr = list(ths)
                        nearest_idx = min(
                            range(len(ths_arr)),
                            key=lambda i: abs(ths_arr[i] - chosen_t),
                        )
                        p_at = precisions[nearest_idx]
                        r_at = recalls[nearest_idx]
                        f1_at = f1s[nearest_idx]

                        s1, s2, s3, s4 = st.columns(4)
                        s1.metric("Threshold", f"{ths_arr[nearest_idx]:.4f}")
                        s2.metric("Precision", f"{p_at:.4f}")
                        s3.metric("Recall", f"{r_at:.4f}")
                        s4.metric("F1", f"{f1_at:.4f}")

                        # Plain-language read of the operational meaning
                        n_pos = int(thresh.get("n_positives", 0))
                        n_total = int(thresh.get("n_total", 0))
                        caught = int(round(r_at * n_pos))
                        st.markdown(
                            f"At threshold **{ths_arr[nearest_idx]:.3f}**, "
                            f"you'd catch **{caught} of {n_pos}** "
                            f"known red-team windows in the validation set "
                            f"({r_at:.1%} recall). Of every 10,000 alerts "
                            f"raised at this threshold, roughly "
                            f"**{p_at * 10000:.0f}** would be true "
                            f"compromises — the rest are false alarms."
                        )

                        st.markdown("---")

                    # ---- Cost-matrix calculator -----------------------
                    st.markdown("**Cost-matrix calculator**")
                    st.caption(
                        "Enter the relative cost of each error type. The "
                        "system finds the threshold that minimizes total "
                        "expected cost on the validation set."
                    )
                    ccol1, ccol2, ccol3 = st.columns([1, 1, 2])
                    cost_fp = ccol1.number_input(
                        "Cost of False Positive (analyst time)",
                        min_value=0.0, value=1.0, step=1.0,
                        help="Cost in arbitrary units of investigating a"
                             " false alarm.",
                    )
                    cost_fn = ccol2.number_input(
                        "Cost of False Negative (missed attack)",
                        min_value=0.0, value=100.0, step=10.0,
                        help="Cost of letting a real attack go undetected.",
                    )
                    if ccol3.button(
                        "Compute optimal threshold",
                        use_container_width=True,
                    ):
                        try:
                            cost_resp = requests.post(
                                f"{API_URL}/cost_optimal_threshold",
                                json={"cost_fp": cost_fp, "cost_fn": cost_fn},
                                timeout=10,
                            )
                            if cost_resp.status_code == 200:
                                cost_payload = cost_resp.json()
                                if cost_payload.get("available"):
                                    st.success(
                                        "Optimal threshold for cost ratio "
                                        f"FN/FP = "
                                        f"{cost_payload.get('ratio_fn_over_fp', 0):.1f}"
                                    )
                                    oA, oB, oC = st.columns(3)
                                    oA.metric(
                                        "Recommended threshold",
                                        f"{cost_payload.get('optimal_threshold', 0):.3f}",
                                    )
                                    oB.metric(
                                        "Precision at that t",
                                        f"{cost_payload.get('optimal_precision', 0):.3f}",
                                    )
                                    oC.metric(
                                        "Recall at that t",
                                        f"{cost_payload.get('optimal_recall', 0):.3f}",
                                    )
                                    st.caption(
                                        f"Expected total cost at this "
                                        f"threshold: "
                                        f"{cost_payload.get('optimal_expected_cost', 0):,.1f}"
                                    )
                        except requests.RequestException as e:
                            st.error(f"Could not reach cost endpoint: {e}")
        except requests.RequestException:
            pass  # threshold panel is optional; never break the metrics tab


# ----------------------------------------------------------------------
# TAB 3 - ARCHITECTURE
# ----------------------------------------------------------------------
with tab_arch:
    st.subheader("Architecture")
    st.markdown(
        """
        ```text
                                        AWS-FIRST DISTRIBUTED PIPELINE

         LANL raw files (.txt.gz)
                    |
                    v
         +--------------------+
         |   S3 - bronze      |   raw, untouched landing zone
         +--------------------+
                    |
                    v   EMR PySpark job:  jobs/bronze_to_silver_emr.py
                    |   (explicit schemas, typing, light cleaning)
                    v
         +--------------------+
         |   S3 - silver      |   typed, cleaned, source-grain tables
         +--------------------+
                    |
                    v   EMR PySpark job:  jobs/silver_to_gold_emr.py
                    |   (time-windowed feature engineering + future target)
                    v
         +--------------------+
         |   S3 - gold        |   model-ready features
         +--------------------+      grain = one computer x one event window
                    |
                    v   jobs/train_model.py  +  MLflow
                    |   (time-aware split, leakage guard, LR + RF)
                    v
         +--------------------+
         | Model artifact      |  feature_names.json + best_model_summary.json
         +--------------------+
                    |
                    v   uvicorn  /  FastAPI
                    v
         +--------------------+
         |   /predict API     |   /health, /model_info, /features, /predict
         +--------------------+
                    |
                    v   HTTP
                    v
         +--------------------+
         |   Streamlit UI     |  (this page)
         +--------------------+
        ```
        """
    )

    st.markdown(
        """
        ### Why these layers exist
        - **Bronze** is the immutable record. If anything downstream goes
          wrong, we can always rebuild from bronze without re-pulling data.
        - **Silver** preserves *row grain* per source - one row per auth
          event, one row per flow, etc. - but with consistent types and
          basic helpers (`success_flag`, `event_day_bucket`).
        - **Gold** is the model-ready shape. The row grain changes here:
          one row = one computer in one event-time window. This is the
          natural unit of "is this host about to become a problem?".

        ### The two design decisions that matter most
        1. **Future-window target.** The label is `target_redteam_next_window`,
           built with a window function. The model never sees the answer for
           the window it is scoring.
        2. **Time-aware split.** The latest 20% of windows are held out as
           a test set. Random shuffling would let the model peek at the
           future and inflate its scores.
        """
    )


# ----------------------------------------------------------------------
# TAB 4 - HOW IT WORKS
# ----------------------------------------------------------------------
with tab_explain:
    st.subheader("Plain-English walkthrough")

    st.markdown(
        """
        **The question**
        > "Given a computer's behavior in the current hour, is it likely to
        > be involved in a red-team event in the next hour?"

        **The input**
        Five raw LANL telemetry streams: authentication, network flows, DNS,
        process events, and red-team labels. They are stored together but
        each describes a different aspect of activity.

        **The transformation**
        Each stream is cleaned (silver), then aggregated by
        `(computer, time_window)` (gold). After the join, each row tells
        the model: "during this hour, computer X did *this* much of *each*
        thing."

        **The trick that keeps it honest**
        We do not put current-window red-team counts into the feature set,
        because that would be the answer leaking in. Instead, the label is
        the *next* window's red-team activity. This is the difference between
        "describing the present" and actually "predicting the future".

        **The model**
        Two scikit-learn models are trained side by side: a logistic
        regression baseline and a random forest. Both are evaluated with
        precision, recall, F1, ROC AUC, and PR AUC. The best (by validation
        F1) is what the API serves.

        **The serving layer**
        FastAPI exposes the model behind `/predict`. This Streamlit app
        is the friendly window into that endpoint - try a preset in the
        sidebar to see the full loop in action.
        """
    )

    if best_summary:
        st.caption(
            f"Currently serving: **{best_summary.get('name', '?')}** "
            f"(test PR AUC = {best_summary.get('metrics', {}).get('test_pr_auc', 0):.3f})"
        )


# ============================================================
# FOOTER
# ============================================================
st.markdown(
    f"""
    <div class="small-muted">
        Window size: {settings.window_size_seconds} s   .
        Target: <code>{settings.target_column}</code>   .
        Leakage columns removed: <code>{', '.join(settings.current_window_redteam_columns)}</code>
    </div>
    """,
    unsafe_allow_html=True,
)
