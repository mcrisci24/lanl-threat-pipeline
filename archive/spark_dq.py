"""
spark_dq.py
===========

Purpose
-------
Reusable Spark data-quality utilities.

Why this matters
----------------
A senior engineer does not duplicate DQ logic in every script.

What we check
-------------
- missing values
- duplicate full rows
- duplicate business keys
- time horizon
- numeric distributions
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def basic_overview(df: DataFrame, label: str) -> dict:
    return {
        "label": label,
        "row_count": int(df.count()),
        "column_count": len(df.columns),
        "columns": list(df.columns),
    }


def missing_value_report(df: DataFrame) -> dict:
    total_rows = df.count()

    row = df.select([
        F.sum(F.when(F.col(c).isNull(), 1).otherwise(0)).alias(c)
        for c in df.columns
    ]).collect()[0].asDict()

    pct = {
        col: (count / total_rows * 100.0 if total_rows > 0 else 0.0)
        for col, count in row.items()
    }

    return {
        "total_rows": int(total_rows),
        "missing_count_by_column": {k: int(v) for k, v in row.items()},
        "missing_pct_by_column": pct,
    }


def full_row_duplicate_report(df: DataFrame) -> dict:
    """
    Heavy check. Safe only on moderate-size dataframes.
    """
    total_rows = df.count()
    distinct_rows = df.dropDuplicates().count()
    duplicate_rows = total_rows - distinct_rows

    return {
        "total_rows": int(total_rows),
        "distinct_rows": int(distinct_rows),
        "duplicate_rows": int(duplicate_rows),
        "duplicate_pct": (duplicate_rows / total_rows * 100.0 if total_rows > 0 else 0.0),
    }


def business_key_duplicate_report(df: DataFrame, key_cols: list[str]) -> dict:
    """
    Heavy check. Safe only on moderate-size dataframes.
    """
    dupes = (
        df.groupBy(*key_cols)
        .count()
        .filter(F.col("count") > 1)
    )

    return {
        "key_columns": key_cols,
        "duplicate_key_rows": int(dupes.count()),
        "sample_duplicate_keys": [r.asDict() for r in dupes.limit(10).collect()],
    }


def sample_duplicate_report(df: DataFrame, key_cols: list[str], fraction: float = 0.001) -> dict:
    """
    Lightweight approximation for huge sources.
    We sample a tiny fraction and inspect duplicates there.
    This is NOT a final truth statement. It is a local debugging compromise.
    """
    sample_df = df.sample(withReplacement=False, fraction=fraction, seed=42)

    sample_rows = sample_df.count()
    sample_dupes = (
        sample_df.groupBy(*key_cols)
        .count()
        .filter(F.col("count") > 1)
    )

    return {
        "sample_fraction": fraction,
        "sample_rows": int(sample_rows),
        "sample_duplicate_key_rows": int(sample_dupes.count()),
        "sample_duplicate_keys": [r.asDict() for r in sample_dupes.limit(10).collect()],
        "note": "Sample-based duplicate check only. Full duplicate audit should run in Databricks.",
    }


def time_horizon_report(df: DataFrame, time_col: str = "time") -> dict:
    row = df.select(
        F.min(F.col(time_col)).alias("min_time"),
        F.max(F.col(time_col)).alias("max_time"),
    ).collect()[0]

    min_time = row["min_time"]
    max_time = row["max_time"]

    return {
        "time_col": time_col,
        "min_time": int(min_time) if min_time is not None else None,
        "max_time": int(max_time) if max_time is not None else None,
        "time_span_seconds": int(max_time - min_time) if min_time is not None and max_time is not None else None,
    }


def numeric_distribution_report(df: DataFrame, cols: list[str]) -> dict:
    out = {}

    for c in cols:
        non_null_count = df.filter(F.col(c).isNotNull()).count()

        if non_null_count == 0:
            out[c] = {
                "count": 0,
                "mean": None,
                "std": None,
                "min": None,
                "q01": None,
                "q25": None,
                "median": None,
                "q75": None,
                "q99": None,
                "max": None,
            }
            continue

        stats = df.select(
            F.mean(F.col(c)).alias("mean"),
            F.stddev(F.col(c)).alias("std"),
            F.min(F.col(c)).alias("min"),
            F.max(F.col(c)).alias("max"),
        ).collect()[0]

        q01, q25, q50, q75, q99 = df.approxQuantile(c, [0.01, 0.25, 0.50, 0.75, 0.99], 0.001)

        out[c] = {
            "count": int(non_null_count),
            "mean": float(stats["mean"]) if stats["mean"] is not None else None,
            "std": float(stats["std"]) if stats["std"] is not None else None,
            "min": float(stats["min"]) if stats["min"] is not None else None,
            "q01": float(q01),
            "q25": float(q25),
            "median": float(q50),
            "q75": float(q75),
            "q99": float(q99),
            "max": float(stats["max"]) if stats["max"] is not None else None,
        }

    return out


def class_balance_report(df: DataFrame, target_col: str) -> dict:
    total_rows = df.count()

    counts = {
        str(r[target_col]): int(r["count"])
        for r in df.groupBy(target_col).count().collect()
    }

    pct = {
        k: (v / total_rows * 100.0 if total_rows > 0 else 0.0)
        for k, v in counts.items()
    }

    return {
        "target_col": target_col,
        "counts": counts,
        "proportions_pct": pct,
    }