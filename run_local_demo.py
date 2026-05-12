"""
run_local_demo.py
=================

Convenience runner used ONLY for offline verification of the LANL pipeline.

Why this file exists
--------------------
The real, graded pipeline runs on AWS:
    raw .txt.gz files in S3
        -> EMR PySpark  bronze_to_silver_emr.py
        -> S3 silver parquet
        -> EMR PySpark  silver_to_gold_emr.py
        -> S3 gold parquet
        -> jobs/train_model.py + MLflow
        -> FastAPI on EC2  (live URL for grading)

That cloud path is expensive to keep running 24/7 on a student free tier.
This script lets a grader sanity-check the model and the API on a laptop
without standing EMR back up:

    1. Train the model from the local gold sample (opt-in CSV fallback).
    2. Start the FastAPI service in the background.
    3. Run test_project.py against it.
    4. Print a clear pass/fail and shut the API back down.

This script is NEVER the canonical pipeline. The project spec disallows
"local CSV files" as the storage layer; this is a verification harness,
not a substitute for the distributed pipeline.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import requests


REPO_ROOT = Path(__file__).resolve().parent
API_URL = "http://127.0.0.1:8000"


def _run(cmd: list[str], env: dict | None = None) -> int:
    """Run a subprocess synchronously and stream its output."""
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=REPO_ROOT, env=env)


def _wait_for_api(timeout_s: int = 30) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = requests.get(f"{API_URL}/health", timeout=2)
            if r.status_code == 200 and r.json().get("model_loaded"):
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


def main() -> int:
    # 1) Train, explicitly using the local CSV fallback.
    env = os.environ.copy()
    env["LANL_USE_LOCAL_GOLD"] = "1"

    rc = _run([sys.executable, "-m", "jobs.train_model"], env=env)
    if rc != 0:
        print("FAIL: training step failed.")
        return rc

    # 2) Start uvicorn in the background.
    print("\nStarting FastAPI service in the background...")
    api_proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "app.api_app:app", "--host", "127.0.0.1", "--port", "8000",
        ],
        cwd=REPO_ROOT,
    )

    try:
        if not _wait_for_api():
            print("FAIL: API never became ready.")
            return 1

        # 3) Run the smoke test.
        rc = _run([sys.executable, "test_project.py"])
        if rc != 0:
            print("FAIL: smoke test failed.")
            return rc

        print("\nSUCCESS: local verification passed.")
        print(
            "Reminder: this is the offline path. The graded URL must be "
            "served from the cloud (FastAPI on EC2 in front of the trained model)."
        )
        return 0
    finally:
        api_proc.terminate()
        try:
            api_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            api_proc.kill()


if __name__ == "__main__":
    sys.exit(main())
