"""
test_project.py
===============

End-to-end smoke test for the LANL Threat Prediction Pipeline.

This is the script the grader runs. The project specification requires it
to live at the REPO ROOT, send at least one request to the prediction
endpoint, print the result, and exit 0 on success / non-zero on failure.

Run it with a single command:
    python test_project.py                          # local API
    python test_project.py --url <hosted_url>       # graded URL

Setup
-----
    pip install -r requirements.txt
    uvicorn app.api_app:app --host 0.0.0.0 --port 8000   # start API
    python test_project.py                                # run this script

What this script checks
-----------------------
    1. GET  /health        - process is up AND the model is loaded
    2. GET  /model_info    - model name + metrics surface correctly
    3. GET  /features      - feature contract returned
    4. POST /predict       - returns {prediction in {0,1}, probability in [0,1]}
    5. POST /predict       - is robust to sparse payloads (missing features)
    6. POST /predict       - accepts the flat legacy payload shape

Exit codes
----------
    0 - all checks passed
    1 - any check failed, or the API was unreachable
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import requests


DEFAULT_URL = "http://127.0.0.1:8000"

# Realistic-looking gold-table-shaped payload.
# These keys match feature names produced by jobs/silver_to_gold_emr.py.
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


class CheckFailed(Exception):
    """Raised when an assertion fails. Caught in main() to set the exit code."""


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise CheckFailed(msg)


def _get(base: str, path: str, timeout: int = 30) -> dict[str, Any]:
    r = requests.get(f"{base.rstrip('/')}{path}", timeout=timeout)
    _expect(r.status_code == 200, f"GET {path} returned {r.status_code}: {r.text[:200]}")
    return r.json()


def _post(base: str, path: str, body: dict, timeout: int = 60) -> dict[str, Any]:
    r = requests.post(f"{base.rstrip('/')}{path}", json=body, timeout=timeout)
    _expect(r.status_code == 200, f"POST {path} returned {r.status_code}: {r.text[:300]}")
    return r.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="LANL Threat Prediction smoke test")
    parser.add_argument("--url", default=DEFAULT_URL,
                        help="Base URL of the API (default: http://127.0.0.1:8000)")
    args = parser.parse_args()

    print(f"Smoke test target: {args.url}\n")

    try:
        # 1) Health
        health = _get(args.url, "/health")
        _expect(health.get("status") == "ok",        f"/health: {health}")
        _expect(health.get("model_loaded") is True,  f"/health: model not loaded ({health})")
        print(f"  [ok] /health      -> {health.get('model_name')}")

        # 2) Model info
        info = _get(args.url, "/model_info")
        _expect(isinstance(info.get("metrics"), dict), "/model_info: metrics missing")
        print(f"  [ok] /model_info  -> {info['model_name']}  "
              f"({len(info['metrics'])} metrics)")

        # 3) Features
        feats = _get(args.url, "/features").get("feature_names") or []
        _expect(len(feats) > 0, "/features: no features returned")
        print(f"  [ok] /features    -> {len(feats)} feature names")

        # 4) Predict (primary)
        out = _post(args.url, "/predict", {"features": SAMPLE_FEATURES})
        pred = out.get("prediction")
        prob = out.get("probability_redteam_next_window")
        _expect(pred in (0, 1),                 f"/predict: bad class {pred}")
        _expect(0.0 <= float(prob) <= 1.0,      f"/predict: bad prob {prob}")
        print(f"  [ok] /predict     -> class={pred}  P(redteam_next)={float(prob):.4f}")
        print("        full response:", out)

        # 5) Predict with a sparse payload (missing features default to 0)
        tiny = {"auth_total_events": 1.0}
        out2 = _post(args.url, "/predict", {"features": tiny})
        _expect(out2.get("prediction") in (0, 1), "/predict (sparse): bad class")
        print("  [ok] /predict (sparse payload) handled correctly")

        # 6) Predict accepting the flat legacy shape
        out3 = _post(args.url, "/predict", SAMPLE_FEATURES)
        _expect(out3.get("prediction") in (0, 1), "/predict (flat): bad class")
        print("  [ok] /predict (flat legacy payload) handled correctly")

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
