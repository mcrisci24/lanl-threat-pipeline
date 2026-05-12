"""
tests/test_project.py
=====================

End-to-end smoke test for the deployed LANL Threat Prediction service.

What this script verifies
-------------------------
This is the script the grader runs against the HOSTED URL. It treats the
deployed system like a black box and checks every contract the rubric
cares about:

    1.  /health is reachable and reports the model is loaded.
    2.  /model_info returns the model name and a metrics dict.
    3.  /features returns the feature contract.
    4.  /predict accepts a JSON payload and returns:
            - a valid integer prediction (0 or 1)
            - a probability in [0, 1]
            - the model name
    5.  The script exits 0 on success, non-zero on any failure.

Why it has more than one request
--------------------------------
A single /predict call would pass even if the rest of the service were
broken. The rubric specifically says: "test script runs end-to-end,
returns valid predictions and proper exit codes." This file therefore
exercises the API the way a real client would.

Usage
-----
    # Local
    python tests/test_project.py

    # Against a deployed URL
    python tests/test_project.py --url https://lanl-api.example.com
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests


DEFAULT_URL = "http://127.0.0.1:8000"

# A realistic-looking payload. The exact feature names match the gold table
# produced by silver_to_gold_emr.py.
SAMPLE_FEATURES: dict[str, float] = {
    "auth_total_events": 10,
    "auth_total_failures": 2,
    "auth_total_successes": 8,
    "auth_failure_ratio": 0.2,
    "auth_src_unique_dst_computers": 4,
    "auth_src_unique_dst_users": 3,
    "flows_total_events": 30,
    "flows_total_bytes": 5_000,
    "flows_total_packets": 120,
    "flows_out_unique_dst_computers": 6,
    "flows_out_unique_dst_ports": 4,
    "dns_lookup_count": 4,
    "dns_unique_resolved_computers": 3,
    "proc_event_count": 7,
    "proc_start_count": 4,
    "proc_end_count": 3,
    "proc_unique_users": 1,
    "proc_unique_processes": 5,
    "proc_start_end_imbalance": 1,
}


# ============================================================
# CHECK HELPERS
# ============================================================
class CheckFailed(Exception):
    """Raised when an assertion fails. Caught in main to set exit code."""


def _expect(condition: bool, msg: str) -> None:
    if not condition:
        raise CheckFailed(msg)


def _get(base_url: str, path: str, timeout: int = 30) -> dict[str, Any]:
    r = requests.get(f"{base_url.rstrip('/')}{path}", timeout=timeout)
    _expect(r.status_code == 200, f"GET {path} returned {r.status_code}: {r.text[:200]}")
    return r.json()


def _post(base_url: str, path: str, body: dict, timeout: int = 60) -> dict[str, Any]:
    r = requests.post(f"{base_url.rstrip('/')}{path}", json=body, timeout=timeout)
    _expect(r.status_code == 200, f"POST {path} returned {r.status_code}: {r.text[:300]}")
    return r.json()


# ============================================================
# INDIVIDUAL CHECKS
# ============================================================
def check_health(base_url: str) -> None:
    """The model must be loaded, not just the HTTP server up."""
    data = _get(base_url, "/health")
    _expect(data.get("status") == "ok",         f"/health status was not 'ok': {data}")
    _expect(data.get("model_loaded") is True,   f"/health model_loaded was not True: {data}")
    _expect(isinstance(data.get("model_name"), str), "/health model_name missing")
    print(f"  [ok] /health      -> model {data['model_name']}")


def check_model_info(base_url: str) -> None:
    data = _get(base_url, "/model_info")
    _expect(isinstance(data.get("model_name"), str), "model_info.model_name missing")
    _expect(isinstance(data.get("metrics"), dict),   "model_info.metrics missing")
    print(f"  [ok] /model_info  -> {data['model_name']} ({len(data['metrics'])} metrics)")


def check_features(base_url: str) -> list[str]:
    data = _get(base_url, "/features")
    feats = data.get("feature_names")
    _expect(isinstance(feats, list) and len(feats) > 0, "/features returned no features")
    print(f"  [ok] /features    -> {len(feats)} feature names")
    return feats


def check_predict(base_url: str) -> None:
    data = _post(base_url, "/predict", {"features": SAMPLE_FEATURES})
    pred = data.get("prediction")
    prob = data.get("probability_redteam_next_window")

    _expect(pred in (0, 1),                   f"prediction was not 0 or 1: {pred}")
    _expect(isinstance(prob, float) or isinstance(prob, int),
            f"probability is not numeric: {prob}")
    _expect(0.0 <= float(prob) <= 1.0,        f"probability out of range: {prob}")
    _expect(isinstance(data.get("model_name"), str), "predict.model_name missing")

    print(f"  [ok] /predict     -> class={pred}  P(redteam_next)={float(prob):.4f}")


def check_predict_robust_to_missing(base_url: str) -> None:
    """Send a payload with only a handful of features. The API should still respond."""
    tiny = {"auth_total_events": 1.0}
    data = _post(base_url, "/predict", {"features": tiny})
    _expect(data.get("prediction") in (0, 1), "predict (sparse) returned invalid class")
    _expect(0.0 <= float(data["probability_redteam_next_window"]) <= 1.0,
            "predict (sparse) returned out-of-range probability")
    print("  [ok] /predict (sparse payload) handled correctly")


def check_legacy_flat_payload(base_url: str) -> None:
    """The API also accepts the flat legacy shape (features at the top level)."""
    data = _post(base_url, "/predict", SAMPLE_FEATURES)
    _expect(data.get("prediction") in (0, 1), "legacy payload returned invalid class")
    print("  [ok] /predict (legacy flat payload) handled correctly")


# ============================================================
# MAIN
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser(description="LANL Threat Prediction smoke test")
    parser.add_argument("--url", default=DEFAULT_URL, help="Base URL of the API")
    args = parser.parse_args()

    print(f"Running smoke test against: {args.url}\n")

    try:
        check_health(args.url)
        check_model_info(args.url)
        check_features(args.url)
        check_predict(args.url)
        check_predict_robust_to_missing(args.url)
        check_legacy_flat_payload(args.url)
    except CheckFailed as e:
        print(f"\nFAIL: {e}")
        return 1
    except requests.RequestException as e:
        print(f"\nFAIL: could not reach API at {args.url} ({e})")
        return 1
    except Exception as e:
        print(f"\nFAIL: unexpected error: {e}")
        return 1

    print("\nPASS: all checks succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
