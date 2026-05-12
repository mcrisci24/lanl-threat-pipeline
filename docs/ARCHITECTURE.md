# LANL Threat Prediction Pipeline — Architecture Walkthrough

This document is the long-form companion to the one-page write-up. It is
the document to read before defending the project to an instructor.

---

## 1. The system in one diagram

```
                                AWS-FIRST DISTRIBUTED PIPELINE

   LANL raw files (.txt.gz, ~11 GB compressed)
   auth / flows / dns / proc / redteam
                |
                v
   +----------------------+
   |  S3  bronze/         |   raw, untouched landing zone (immutable)
   +----------------------+
                |
                v   EMR PySpark - jobs/bronze_to_silver_emr.py
                |   explicit Spark schemas, typing, light cleaning,
                |   event_day_bucket partition helper
                v
   +----------------------+
   |  S3  silver/         |   one parquet folder per source, source-level row grain
   |   auth/  flows/      |
   |   dns/   proc/       |
   |   redteam/           |
   +----------------------+
                |
                v   EMR PySpark - jobs/silver_to_gold_emr.py
                |   hourly time windows, per-source aggregation,
                |   union keyspace, derived ratios,
                |   FUTURE-WINDOW target via Spark Window.lead()
                v
   +----------------------+
   |  S3  gold/           |   row grain = (computer, time_window)
   |   computer_time/     |   features + target_redteam_next_window
   +----------------------+
                |
                v   jobs/train_model.py (pandas + scikit-learn)
                |   - time-aware 60/20/20 split
                |   - leakage guard assertion
                |   - logistic regression baseline + random forest
                |   - MLflow tracking + Model Registry alias 'Production'
                v
   +---------------------------+
   |  Model artifact + meta    |   feature_names.json
   |  (model_outputs/)         |   best_model_summary.json
   |                           |   <best>.joblib
   +---------------------------+
                |
                v   uvicorn app.api_app:app  (FastAPI on EC2)
                v
   +---------------------------+
   |  /health      /model_info |
   |  /features                |
   |  /predict     /batch_predict
   +---------------------------+
                |
                v   HTTP
                v
   +---------------------------+
   |  Streamlit UI             |   presets, verdict card, probability chart,
   |  (Streamlit Cloud / EC2)  |   metrics tab, architecture tab
   +---------------------------+
```

## 2. Which stages are distributed? (mapping to the spec)

The project specification requires **at least two** of these four layers to
use distributed/cloud infrastructure. This project uses **three** of them:

| Spec layer       | Allowed options                          | This project          |
|------------------|------------------------------------------|-----------------------|
| Ingestion        | S3 / cloud object store, API, scraping   | **S3** (raw bronze)   |
| Transformation   | **Spark**, dbt, Polars                   | **PySpark on EMR**    |
| Storage          | Delta, Iceberg, **Parquet**, DynamoDB, Snowflake | **Parquet on S3** |
| Serving          | Lambda, API Gateway, **FastAPI/Flask on EC2** | **FastAPI on EC2** |

Streaming is optional and reserved for bonus credit; it is not used here.

## 3. The medallion layers in plain English

### Bronze
Bronze is the **immutable landing zone**. Raw `.txt.gz` files sit in
`s3://<bucket>/lanl/bronze/`. We never edit bronze — if anything downstream
breaks, we can rebuild from bronze without re-downloading data.
*Refinery metaphor:* crude oil on the receiving dock.

### Silver
Silver is **cleaned and typed but still source-grain**: one row per auth event,
one row per flow, one row per DNS lookup, etc. The silver job applies the
explicit Spark schema from `config/schemas.py`, casts `time` to `bigint`,
strips whitespace, adds per-source helpers (`success_flag`, `redteam_flag`),
and writes parquet partitioned by `event_day_bucket`.
*Refinery metaphor:* ingredients washed, sorted, and labeled.

### Gold
Gold changes the row grain to **one computer in one event-time window**.
This is the natural unit of operational risk - "is *this host* about to
become a problem?" The silver-to-gold job:

1. Adds `time_window = floor(time / 3600)` so each window is one hour.
2. Aggregates each source by `(computer, time_window)`, separately for the
   src and dst perspectives where applicable.
3. Unions a master keyspace so no `(computer, window)` is dropped just because
   it appeared in only one source.
4. Left-joins every source onto the keyspace and fills nulls with 0
   (a missing aggregate value means "no events of that kind this window").
5. Builds derived features (`auth_failure_ratio`, `flows_bytes_per_event`, …).
6. Creates the future target with a Spark window function:
   ```python
   target_redteam_next_window =
       lead(redteam_current_flag, 1).over(W.partitionBy("computer").orderBy("time_window"))
   ```
7. Writes parquet partitioned by `window_day_bucket`.

*Refinery metaphor:* the refined product, ready to power something.

## 4. The two design decisions that matter most

1. **Future-window target.** The label is the *next* window's red-team
   activity. Built with a window function in Spark; never the current
   window. The current-window red-team columns
   (`redteam_src_event_count`, `redteam_dst_event_count`,
   `redteam_event_count`, `redteam_current_flag`) are dropped from the
   feature set in `train_model.py`, and the script *asserts* none of them
   survive before training begins.

2. **Time-aware split.** The latest 20 % of windows are held out as the
   test set; the next-latest 20 % as validation; the earliest 60 % train.
   Random shuffling would let the model peek at the future and inflate its
   metrics.

Either one alone could quietly fail (`shift` mistakes are easy to make);
having both catches each other.

## 5. Configuration architecture

All paths, window sizes, leakage columns, partition strategies, and Spark
tuning live in `config/settings.py` (frozen dataclass). All Spark schemas
and row-grain descriptions live in `config/schemas.py`. These two files are
the blueprint - jobs read from them but never define their own paths.

That separation is what lets us swap S3 bucket names, retune partition
counts, or change the window size in one place without hunting through job
files.

## 6. Data quality

`utils/spark_dq.py` centralizes:

- structural overview (row count, column count),
- missingness by column,
- full-row duplicate report,
- business-key duplicate report,
- sample-based duplicate report (cheaper on huge sources),
- time-horizon summary (min/max event time),
- numeric distribution (mean, std, quantiles 0.01 / 0.25 / median / 0.75 / 0.99),
- class-balance report for the target.

Jobs invoke these helpers rather than recomputing checks ad-hoc.

## 7. Why these technology choices

- **S3** — durable, cheap, integrates with EMR, Athena, Glue. The medallion
  prefixes (`bronze/`, `silver/`, `gold/`) make the layout self-documenting.
- **EMR + PySpark** — the dataset is too large for a single machine; EMR
  gives genuine distributed compute and reads parquet from S3 natively.
- **Parquet** — columnar, compressed, partitioned. Cheap to read just the
  columns the model needs.
- **scikit-learn after Spark** — by the time we hit gold, the table is
  small (~few hundred MB), so single-node sklearn is the right tool for the
  modeling phase. Spark for data engineering, sklearn for modeling — each
  doing what it does best.
- **MLflow** — tracking server logs every run; the Model Registry promotes
  the winning version to alias `Production`.
- **FastAPI + EC2** — explicit option in the spec; fits the project size
  without the operational overhead of Lambda cold starts.
- **Streamlit** — fast to build, easy to host, accepts custom HTML/CSS for
  the "sizzle" the rubric asks for.

## 8. The Databricks-to-AWS pivot

The original architecture was Databricks-first because the course leaned
on it. Free-tier limits on managed storage made it impractical to push the
~11 GB raw dataset through DBFS at our credit allotment. Rather than gut
the project, we kept the medallion architecture and rebuilt it on the
allowed alternatives in the spec:

- Databricks Workspace -> EMR PySpark
- Unity Catalog Volumes -> S3 prefixes
- Delta Lake -> Parquet on S3
- Databricks Model Serving -> FastAPI on EC2
- Databricks MLflow -> MLflow with local backend (tracking + registry)

Every original capability is still present; only the host changed.

## 9. Limitations

- Single dataset (one enterprise's telemetry); generalization to other
  networks is not validated.
- Relative event time, not calendar time, so we can't reason about
  diurnal patterns.
- No streaming - bonus track left for future work.
- Local CSV in `gold_outputs/` is *verification only*; the canonical
  storage layer is parquet on S3.
