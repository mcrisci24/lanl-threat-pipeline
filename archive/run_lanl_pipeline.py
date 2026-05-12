"""
run_lanl_pipeline.py
====================

Purpose
-------
Simple orchestration script for the PySpark-first pipeline.

What it runs
------------
- silver build
- gold build
- training (optional)

Why this matters
----------------
A senior engineer separates orchestration from transformation logic.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def log_msg(msg: str) -> None:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")


def run_stage(script_path: Path, stage_name: str) -> None:
    log_msg(f"STARTING STAGE: {stage_name}")
    log_msg(f"SCRIPT: {script_path}")

    if not script_path.exists():
        raise FileNotFoundError(f"{stage_name} script not found: {script_path}")

    start = time.time()

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=False,
        text=True
    )

    elapsed = time.time() - start

    if result.returncode != 0:
        raise RuntimeError(f"{stage_name} failed with return code {result.returncode}")

    log_msg(f"COMPLETED STAGE: {stage_name} in {elapsed:.2f} seconds")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LANL cybersecurity pipeline.")
    parser.add_argument(
        "--mode",
        choices=["silver", "gold", "train", "all"],
        default="all",
        help="Which pipeline stage(s) to run."
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=r"C:\Users\markc\Documents\DistributedCompProject2\LANL",
        help="Base LANL project directory."
    )

    args = parser.parse_args()
    base_dir = Path(args.base_dir)

    silver_script = base_dir / "build_lanl_silver_pyspark.py"
    gold_script = base_dir / "build_lanl_gold_pyspark.py"
    train_script = base_dir / "ml_training_lanl.py"

    log_msg("LANL PIPELINE STARTED")
    log_msg(f"BASE DIRECTORY: {base_dir}")
    log_msg(f"MODE: {args.mode}")

    try:
        if args.mode in ["silver", "all"]:
            run_stage(silver_script, "SILVER BUILD")

        if args.mode in ["gold", "all"]:
            run_stage(gold_script, "GOLD BUILD")

        if args.mode in ["train", "all"]:
            run_stage(train_script, "MODEL TRAINING")

        log_msg("PIPELINE COMPLETE")
        log_msg("ALL REQUESTED STAGES FINISHED SUCCESSFULLY")

    except Exception as e:
        log_msg("PIPELINE FAILED")
        log_msg(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()