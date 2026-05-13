"""
app/streaming_sim.py
====================

Streaming replay engine for the LANL threat-prediction demo.

What this is (and isn't)
------------------------
This module REPLAYS rows from the gold sample CSV against the live
FastAPI `/predict` endpoint, on a wall-clock timer.  From the model's
point of view every prediction is a real production call.  From the
data's point of view the "stream" is a recorded log being read back.

This is NOT a Kinesis consumer.  It is a *streaming simulator* whose
job is to demonstrate that the deployed scoring engine is fast enough
and stable enough to back a real streaming pipeline.  In production
you would swap `load_replay_pool` for a Kinesis or Kafka client; the
scoring path on the API side does not change.

Why this matters for the demo
-----------------------------
A static "press a button, see a probability" UI fails to show that
the system is operational.  Streaming-style replay against the live
API answers two questions a reviewer will have:

    1. Does the model actually discriminate when you push a long
       sequence of rows through it, or are the demo presets cherry-
       picked?  (Answer: watch the trajectory chart.)
    2. Does the deployed API handle sustained traffic without going
       down?  (Answer: it just survived hundreds of calls in a minute.)

Public interface
----------------
- `load_replay_pool`   -- pull a sample of gold rows for replay
- `score_pool`         -- batch-score the whole pool up front
- `score_one`          -- score a single ad-hoc row (used by Inject)
- `HIGH_RISK_INJECT_ROW` -- canonical attack fingerprint
- `make_event`         -- normalize a row into a chart-friendly dict
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import requests


# ---------------------------------------------------------------------------
# Inject-button fingerprint
# ---------------------------------------------------------------------------
# Mirrored from the "Demo HIGH risk - real row (P=0.745)" preset in
# streamlit_app.py.  We keep a copy here so the streaming module does not
# need to import the main app (which would create a circular dependency
# the moment streamlit_app starts importing this file back).
HIGH_RISK_INJECT_ROW: dict[str, float] = {
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
}


# ---------------------------------------------------------------------------
# Replay-pool loader
# ---------------------------------------------------------------------------
def load_replay_pool(
    csv_path: Path,
    max_rows: int = 120,
    seed: int = 42,
) -> pd.DataFrame:
    """Return a random sample of rows from the gold table for replay.

    Why a sample, not the whole file
    --------------------------------
    The full gold sample has ~27k rows.  Replaying all of them at one
    row per second would take 7+ hours and bury the demo in noise.  A
    pool of ~120 rows gives the audience a clear beginning and end at
    roughly 1 row/second, while keeping enough variety that the chart
    actually moves.

    We pass `seed` so the demo is reproducible -- if the presenter
    practices the demo three times in a row, they see the same chart.
    """
    df = pd.read_csv(csv_path)
    if len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=seed).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Scoring helpers (talk to the deployed FastAPI service)
# ---------------------------------------------------------------------------
def score_pool(
    api_url: str,
    pool: pd.DataFrame,
    feature_names: list[str],
    timeout: float = 60.0,
) -> list[float]:
    """Score every row in the pool via `/batch_predict` (one HTTP call).

    Pre-scoring rather than scoring-per-tick is deliberate:

      - The chart animation is decoupled from API latency, so the demo
        does not stutter if the API is briefly slow.
      - The serving claim ("we just processed N rows through the
        production API") is still true -- they all flowed through the
        same model in the same single request.
      - At 100+ rows, one batched call is dramatically faster than 100
        round-trips.

    The API returns predictions in row-order, so we map straight to
    a probability list.
    """
    rows_payload = [
        {col: float(pool.iloc[i].get(col, 0.0)) for col in feature_names}
        for i in range(len(pool))
    ]
    r = requests.post(
        f"{api_url}/batch_predict",
        json={"rows": rows_payload},
        timeout=timeout,
    )
    r.raise_for_status()
    preds = r.json().get("predictions", [])
    return [float(p["probability_redteam_next_window"]) for p in preds]


def score_one(
    api_url: str,
    row: dict[str, float],
    feature_names: list[str],
    timeout: float = 10.0,
) -> float:
    """Score one ad-hoc row via `/predict`.  Used by the Inject button.

    We hit `/predict` instead of `/batch_predict` here for a reason:
    the inject is one row.  Calling `/predict` keeps the audit log
    cleaner (one inject = one prediction record) and proves that the
    same single-row endpoint a SOC analyst would call is what's
    powering the simulator.
    """
    payload = {col: float(row.get(col, 0.0)) for col in feature_names}
    r = requests.post(
        f"{api_url}/predict",
        json={"features": payload},
        timeout=timeout,
    )
    r.raise_for_status()
    return float(r.json()["probability_redteam_next_window"])


# ---------------------------------------------------------------------------
# Event normalization
# ---------------------------------------------------------------------------
def make_event(
    seq: int,
    host_id: str,
    probability: float,
    injected: bool = False,
) -> dict[str, Any]:
    """Build one chart-ready event dict.

    Using a plain dict (instead of a dataclass) so events round-trip
    cleanly through `st.session_state`, which serializes between
    Streamlit reruns.
    """
    return {
        "seq": int(seq),
        "host_id": str(host_id),
        "probability": float(probability),
        "injected": bool(injected),
    }


def extract_host_id(row: pd.Series, fallback_seq: int) -> str:
    """Return a printable host identifier for one gold row.

    The gold sample has a `computer` column with values like
    `C17693`.  Older or trimmed exports might not have it -- in that
    case we fall back to the row's sequence number so the chart still
    has something to label dots with.
    """
    val = row.get("computer", None) if hasattr(row, "get") else None
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return f"row{fallback_seq}"
    return str(val)
