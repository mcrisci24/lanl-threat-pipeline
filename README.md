
# LANL Threat Prediction Pipeline

**Author:** Mark Crisci 
**Live app:** <https://lanlthreat.streamlit.app> 
**API endpoint:** <http://98.94.30.68:8000> 
**Repository:** <https://github.com/mcrisci24/lanl-threat-pipeline>
**API smoke test:** `python test_project.py --url http://98.94.30.68:8000`

------------------------------------------------------------------------

## Overview

This project is an end-to-end cybersecurity analytics and machine-learning system built on the Los Alamos National Laboratory enterprise telemetry dataset. The system ingests raw multi-source security logs, transforms them through a bronze -\> silver -\> gold medallion pipeline, trains and tracks supervised machine-learning models, and serves predictions through a FastAPI backend with a Streamlit dashboard for interpretation and demo use.

The core prediction question is:

> Given a computer's behavior in the current one-hour event window, will the same computer show red-team attacker activity in the next one-hour window?

That next-window framing is the central design decision. Predicting the current window would be easier, but it would also let the model learn from current red-team labels and turn the task into label detection instead of prediction. This project instead builds a future-window target, removes current-window red-team features from the predictors, and checks for leakage before model training.

------------------------------------------------------------------------

## What the system does

At a high level, the pipeline does four things:

1.  **Processes raw cybersecurity telemetry at scale** using S3, parquet, and PySpark on AWS EMR.
2.  **Builds a model-ready gold table** with one row per `(computer, time_window)`.
3.  **Trains and compares supervised ML models** including Logistic Regression, Random Forest, XGBoost, and LightGBM.
4.  **Serves risk predictions and model evidence** through a deployed FastAPI service and Streamlit dashboard.

The result is not just a notebook or static classifier. It is a working ML system with data engineering, model training, model tracking, API serving, dashboarding, and a reproducible smoke test.

------------------------------------------------------------------------

## Architecture at a glance

| Stage | Technology | Purpose |
|-----------------|-----------------|--------------------------------------|
| Raw storage | AWS S3 bronze layer | Stores the original LANL `.txt.gz` files unchanged |
| Bronze -\> Silver | AWS EMR + PySpark | Applies schemas, cleans types and strings, writes typed parquet |
| Silver -\> Gold | AWS EMR + PySpark | Aggregates behavior by `(computer, time_window)` and creates the future-window target |
| Clean storage | S3 parquet silver/gold layers | Stores analysis-ready and model-ready tables |
| Model training | scikit-learn, XGBoost, LightGBM, MLflow | Trains, evaluates, tracks, and registers models |
| Serving | FastAPI on EC2 | Exposes prediction, batch prediction, features, health, and model metadata endpoints |
| UI | Streamlit Cloud | Public dashboard for interpretation, demo, and stakeholder-friendly interaction |

**Pipeline flow:**

``` mermaid
flowchart LR
    R["LANL raw .txt.gz<br/>auth · flows · dns · proc · redteam"]
    B[("S3 — bronze<br/>raw landing")]
    EMR1["EMR PySpark<br/>bronze_to_silver_emr.py<br/><i>schemas · typing · cleanup</i>"]
    S[("S3 — silver<br/>typed parquet per source")]
    EMR2["EMR PySpark<br/>silver_to_gold_emr.py<br/><i>time windows · aggregates · future-window target</i>"]
    G[("S3 — gold<br/>(computer, time_window) features")]
    T["train_model.py<br/>+ MLflow tracking + Model Registry alias <b>Production</b>"]
    A["FastAPI on EC2<br/>/health /model_info /features /predict /batch_predict"]
    U["Streamlit UI<br/>presets · gauge · metrics · architecture"]
    R --> B --> EMR1 --> S --> EMR2 --> G --> T --> A --> U

    classDef cloud fill:#e0f2fe,stroke:#0369a1,color:#0c4a6e;
    classDef compute fill:#fef3c7,stroke:#b45309,color:#7c2d12;
    classDef serve fill:#dcfce7,stroke:#15803d,color:#14532d;
    class B,S,G cloud
    class EMR1,EMR2 compute
    class A,U serve
```

The blue boxes are the **distributed storage** layer (S3 parquet), the amber boxes are the **distributed compute** layer (Spark on EMR), and the green boxes are the **cloud serving** layer (FastAPI on EC2 + Streamlit hosting). That is **three** of the four pipeline layers using cloud or distributed infrastructure — the spec only requires two.

------------------------------------------------------------------------

## Dataset

The project uses the LANL enterprise cybersecurity telemetry dataset, which contains multiple event streams from a real corporate network environment:

- authentication events
- network flow records
- DNS lookups
- process start/stop events
- red-team attack labels

The raw data is large and highly imbalanced. The red-team file is tiny compared with the rest of the telemetry, which means the project is a rare-event prediction problem. Accuracy is not useful here because a model could predict every row as benign and still look almost perfect. The meaningful evaluation question is whether the model can rank and flag rare attack-like windows better than random guessing.

------------------------------------------------------------------------

## Feature engineering

The silver-to-gold Spark job changes the row grain from raw events to behavioral windows. The gold table contains one row per computer per time window, with engineered features such as:

- authentication event counts
- authentication success and failure counts
- authentication failure ratios
- unique destination computers
- network flow counts
- total bytes and packets
- bytes per event and packets per event
- DNS lookup counts
- unique resolved computers
- process event counts
- process start/end imbalance

The target is `target_redteam_next_window`, which asks whether the same computer shows red-team behavior in the following time window.

------------------------------------------------------------------------

## Machine-learning approaches

The modeling task is supervised binary classification:

``` text
0 = no red-team activity in the next window
1 = red-team activity in the next window
```

The project trains and compares several models:

| Model | Role in the project |
|-------------------|-----------------------------------------------------|
| Logistic Regression | Interpretable benchmark model |
| Random Forest | Nonlinear tree-based baseline |
| XGBoost | Gradient-boosted tree model |
| LightGBM | Histogram-based boosted tree model and strongest served model |

The preprocessing pipeline uses median imputation and standardization where appropriate. Class imbalance is handled through balanced class weights or equivalent positive-class weighting.

The main evaluation metrics are:

- **PR-AUC**, because the positive class is extremely rare
- **ROC-AUC**, for general ranking/separation ability
- **precision and recall**, for operational alert tradeoffs
- **F1**, for balance between precision and recall
- **false-positive burden**, because too many false alerts can overwhelm analysts

The strongest current model is LightGBM. Its high ROC-AUC shows strong ranking/separation ability, but the more honest metric for this problem is PR-AUC because the attack class is a tiny sliver of the data. The project treats the model as a risk-ranking tool for analyst triage, not as an automatic replacement for human judgment.

------------------------------------------------------------------------

## Leakage prevention

Leakage prevention is one of the most important parts of the project.

The model does **not** predict whether a computer is currently involved in red-team activity. It predicts whether a computer will show red-team activity in the **next** time window.

The training code defends against leakage in three ways:

1.  Builds a future-window target using a per-computer window shift.
2.  Removes current-window red-team columns from the feature set.
3.  Runs an assertion before training to fail the pipeline if leakage-sensitive columns survive.

This matters because the first version of this kind of model can easily look unrealistically good if it accidentally reads the answer from same-window red-team features. The honest version produces messier but meaningful results.

------------------------------------------------------------------------

## Application and API

The deployed FastAPI service exposes:

``` text
GET  /health
GET  /model_info
GET  /features
POST /predict
POST /batch_predict
POST /explain
POST /counterfactual
```

The Streamlit dashboard provides:

- preset cybersecurity scenarios
- live prediction calls to the deployed API
- a risk gauge
- model metrics
- feature-level explanation views
- counterfactual-style recommendations
- an architecture walkthrough
- a replay-based live monitoring simulator

The live monitor is a simulator, not a true Kafka/Kinesis stream. It replays sample rows and sends real HTTP scoring requests to the API. In production, the replay source could be replaced with Kinesis or Kafka while keeping the FastAPI model boundary unchanged.

------------------------------------------------------------------------

## Repository layout

``` text
LANL/
  app/
    api_app.py                  # FastAPI service
    streamlit_app.py            # Streamlit dashboard
    streaming_sim.py            # replay-based live monitor simulator
  config/
    settings.py                 # S3 paths, target column, leakage columns
    schemas.py                  # explicit schemas for LANL raw sources
  deploy/
    Dockerfile                  # serving container
    docker-compose.yml          # API + UI deployment helper
    launch_emr.sh               # transient EMR launch helper
    README.md                   # deployment notes
  docs/
    ARCHITECTURE.md             # detailed architecture explanation
    PRESENTATION.md             # presentation notes / script
    WRITEUP.md                  # project write-up source
  jobs/
    bronze_to_silver_emr.py     # Spark raw -> silver
    silver_to_gold_emr.py       # Spark silver -> gold
    train_model.py              # model training + MLflow tracking
  gold_outputs/                 # small local sample for offline verification
  model_outputs/                # trained model artifacts used by API
  presentation_assets/          # figures and visual assets
  reports/                      # reports, diagnostics, and generated summaries
  tests/
    test_project.py             # local-dev copy of smoke test
  test_project.py               # root smoke test
  WRITEUP.pdf                   # project write-up PDF
  README.md
  requirements.txt
```

------------------------------------------------------------------------

## How to run the deployed smoke test

``` bash
pip install requests
python test_project.py --url http://98.94.30.68:8000
```

The smoke test checks that:

- `/health` returns a working API and loaded model
- `/model_info` exposes the served model and metrics
- `/features` returns the expected feature contract
- `/predict` works with a complete payload
- `/predict` handles sparse payloads
- `/predict` accepts the legacy flat payload shape

A successful run exits with code `0`. Any failure exits nonzero.

------------------------------------------------------------------------

## How to run locally

The canonical pipeline is cloud-first: S3 + EMR + parquet. A small local fallback exists only so the API and dashboard can be verified without paying to rerun the full EMR pipeline.

``` bash
pip install -r requirements.txt
python run_local_demo.py
```

That script trains from the local gold sample using `LANL_USE_LOCAL_GOLD=1`, starts the API, runs `test_project.py`, and shuts the API back down.

------------------------------------------------------------------------

## How to run the full cloud pipeline

At a high level:

``` bash
# 1. Upload raw LANL files to S3 bronze
aws s3 cp auth.txt.gz s3://<bucket>/lanl/bronze/auth.txt.gz
aws s3 cp flows.txt.gz s3://<bucket>/lanl/bronze/flows.txt.gz
aws s3 cp dns.txt.gz s3://<bucket>/lanl/bronze/dns.txt.gz
aws s3 cp proc.txt.gz s3://<bucket>/lanl/bronze/proc.txt.gz
aws s3 cp redteam.txt.gz s3://<bucket>/lanl/bronze/redteam.txt.gz

# 2. Launch EMR and run Spark jobs
bash deploy/launch_emr.sh

# 3. Train models
python -m jobs.train_model

# 4. Start API
uvicorn app.api_app:app --host 0.0.0.0 --port 8000

# 5. Start Streamlit app
streamlit run app/streamlit_app.py
```



------------------------------------------------------------------------

## Results summary

The LightGBM model currently provides the strongest rare-event ranking performance. The important interpretation is not simply that the model has a high ROC-AUC. In this dataset, the attack class is extremely rare, so PR-AUC and false-positive burden are more honest indicators of usefulness.

The model is best understood as a triage system:

> It ranks host-hour windows by risk so an analyst can focus attention where the telemetry looks most suspicious.

It is not meant to automatically declare guilt or replace a SOC analyst.

------------------------------------------------------------------------

## Important lessons from the project to note for future 

The biggest lesson was that distributed systems and machine learning fail in different ways.

On the distributed side, the hardest issue was not writing Spark syntax. It was dealing with real infrastructure limits: file formats, storage restrictions, cloud permissions, and the fact that gzip is not splittable in Spark. The raw authentication file became a bottleneck because one compressed file could not be parallelized the way parquet can.

On the machine-learning side, the hardest issue was leakage and imbalance. A model can look nearly perfect if it is allowed to read same-window red-team information. Once that was fixed, the metrics became much more honest. The model still ranks rare attacks far better than random, but the false-positive tradeoff remains real.

That is the point of the project: build the system honestly, expose the tradeoffs, and make the pipeline reproducible.

------------------------------------------------------------------------

#### Security notes

No AWS keys, tokens, passwords, or private credentials are committed. Runtime paths and settings are controlled through environment variables and `config/settings.py`. The Streamlit app calls the FastAPI service and does not expose AWS credentials in the browser.

------------------------------------------------------------------------

This is an original cybersecurity ML pipeline built around the LANL enterprise telemetry dataset. The main design decision, predicting next-window red-team activity while removing current-window red-team features, turns the project from a label-reading demo into a real predictive system.
