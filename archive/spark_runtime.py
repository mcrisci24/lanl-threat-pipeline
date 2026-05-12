"""
spark_runtime.py
================

Purpose
-------
Create a SparkSession configured for local PySpark development.

Why this matters
----------------
A senior engineer centralizes runtime/session setup.
That way, every script gets the same Spark behavior.

Notes
-----
- This is LOCAL Spark for debugging and development.
- The same business logic can be moved into Databricks later.
- Delta support is required because the project should use Delta storage.
"""


from __future__ import annotations

import logging
import os
from pyspark.sql import SparkSession

logger = logging.getLogger(__name__)

# local = debug on your own machine
# databricks = authoritative distributed run
SPARK_RUNTIME_MODE = os.getenv("SPARK_RUNTIME_MODE", "local").strip().lower()


def build_spark_session(app_name: str) -> SparkSession:
    """
    Build a Spark session.

    Local mode:
    - uses local machine
    - increases driver memory
    - does NOT assume Delta is installed

    Databricks mode:
    - assumes Spark session is managed externally
    - this helper is not used there
    """
    if SPARK_RUNTIME_MODE == "databricks":
        raise RuntimeError(
            "build_spark_session() should not be called in Databricks notebooks. "
            "Use the Databricks-provided `spark` session there."
        )

    builder = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", "24g")
        .config("spark.sql.shuffle.partitions", "64")
        .config("spark.default.parallelism", "64")
        .config("spark.network.timeout", "600s")
        .config("spark.executor.heartbeatInterval", "60s")
    )

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    logger.info("Spark session created successfully")
    logger.info(f"Spark version: {spark.version}")
    logger.info(f"SPARK_RUNTIME_MODE: {SPARK_RUNTIME_MODE}")

    return spark