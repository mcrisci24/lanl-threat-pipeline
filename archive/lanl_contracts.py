"""
lanl_contracts.py
=================

Purpose
-------
This file is the single source of truth for:
1. File paths
2. Source schemas / column names
3. Business keys
4. Row-grain definitions
5. Time-window settings
6. Feature-leakage guardrails

Why this matters
----------------
Senior engineers do not scatter schemas and business logic across multiple files.
This module keeps the project organized and makes changes easier and safer.

Key analytical notes
--------------------
- LANL time is RELATIVE EVENT TIME, not real calendar dates.
- That means we can reason about event ordering and time windows,
  but NOT about seasons, weekdays, holidays, or pandemic periods.
- One row means different things in different source files.
  We explicitly document that here.
"""

from __future__ import annotations

from pathlib import Path

# ============================================================
# PROJECT ROOT
# ============================================================
BASE_DIR = Path(r"/LANL")

# ============================================================
# RAW INPUT FILES
# ============================================================
RAW_FILES = {
    "auth": BASE_DIR / "auth.txt.gz",
    "flows": BASE_DIR / "flows.txt.gz",
    "dns": BASE_DIR / "dns.txt.gz",
    "proc": BASE_DIR / "proc.txt.gz",
    "redteam": BASE_DIR / "redteam.txt.gz",
}

# ============================================================
# OUTPUT DIRECTORIES
# ============================================================
SILVER_DIR = BASE_DIR / "silver_outputs"
GOLD_DIR = BASE_DIR / "gold_outputs"
MODEL_DIR = BASE_DIR / "model_outputs"
DQ_DIR = BASE_DIR / "dq_reports"

for _dir in [SILVER_DIR, GOLD_DIR, MODEL_DIR, DQ_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ============================================================
# SILVER OUTPUT PATHS
# Local debug path uses parquet folders.
# ============================================================
SILVER_OUTPUTS = {
    "auth": SILVER_DIR / "silver_auth_parquet",
    "flows": SILVER_DIR / "silver_flows_parquet",
    "dns": SILVER_DIR / "silver_dns_parquet",
    "proc": SILVER_DIR / "silver_proc_parquet",
    "redteam": SILVER_DIR / "silver_redteam_parquet",
}

# ============================================================
# GOLD OUTPUT PATH
# ============================================================
GOLD_OUTPUT = GOLD_DIR / "gold_computer_time_parquet"

# ============================================================
# MODEL OUTPUT PATHS
# ============================================================
FEATURE_NAMES_FILE = MODEL_DIR / "feature_names.json"
BEST_MODEL_SUMMARY_FILE = MODEL_DIR / "best_model_summary.json"

# ============================================================
# WINDOW / TARGET SETTINGS
# ============================================================
WINDOW_SIZE_SECONDS = 3600
TARGET_COLUMN = "target_redteam_next_window"

# ============================================================
# SOURCE COLUMN DEFINITIONS
# ============================================================
AUTH_COLS = [
    "time",
    "src_user_domain",
    "dst_user_domain",
    "src_computer",
    "dst_computer",
    "auth_type",
    "logon_type",
    "auth_orientation",
    "success",
]

FLOWS_COLS = [
    "time",
    "duration",
    "src_computer",
    "src_port",
    "dst_computer",
    "dst_port",
    "protocol",
    "packet_count",
    "byte_count",
]

DNS_COLS = [
    "time",
    "src_computer",
    "resolved_computer",
]

PROC_COLS = [
    "time",
    "user_domain",
    "computer",
    "process_name",
    "event_type",
]

REDTEAM_COLS = [
    "time",
    "user_domain",
    "src_computer",
    "dst_computer",
]

SOURCE_COLUMNS = {
    "auth": AUTH_COLS,
    "flows": FLOWS_COLS,
    "dns": DNS_COLS,
    "proc": PROC_COLS,
    "redteam": REDTEAM_COLS,
}

# ============================================================
# SOURCE METADATA
# ============================================================
SOURCE_METADATA = {
    "auth": {
        "row_grain": "one authentication event",
        "time_col": "time",
        "business_key_cols": [
            "time", "src_user_domain", "dst_user_domain",
            "src_computer", "dst_computer", "auth_type",
            "logon_type", "auth_orientation", "success",
        ],
    },
    "flows": {
        "row_grain": "one network flow",
        "time_col": "time",
        "business_key_cols": [
            "time", "duration", "src_computer", "src_port",
            "dst_computer", "dst_port", "protocol",
            "packet_count", "byte_count",
        ],
    },
    "dns": {
        "row_grain": "one DNS resolution event",
        "time_col": "time",
        "business_key_cols": ["time", "src_computer", "resolved_computer"],
    },
    "proc": {
        "row_grain": "one process lifecycle event",
        "time_col": "time",
        "business_key_cols": ["time", "user_domain", "computer", "process_name", "event_type"],
    },
    "redteam": {
        "row_grain": "one labeled compromise event",
        "time_col": "time",
        "business_key_cols": ["time", "user_domain", "src_computer", "dst_computer"],
    },
    "gold": {
        "row_grain": "one computer in one event-time window",
        "business_key_cols": ["computer", "time_window"],
    },
}

# ============================================================
# LEAKAGE GUARDRAILS
# ============================================================
REDTEAM_CURRENT_COLUMNS = [
    "redteam_src_event_count",
    "redteam_dst_event_count",
    "redteam_event_count",
    "redteam_current_flag",
]

NON_FEATURE_COLUMNS = [
    "computer",
    "time_window",
    TARGET_COLUMN,
]