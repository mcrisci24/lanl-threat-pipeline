# Deployment Guide

How to get the live URL the grader will hit.

---

## Option A — Distributed cloud pipeline (the canonical path)

This is what the rubric is grading: a genuine distributed pipeline,
medallion layers on S3, Spark on EMR, FastAPI on EC2, MLflow tracking +
Model Registry.

### 1) Configure AWS
```bash
aws configure                                  # set key + region
aws emr create-default-roles                   # one-time, idempotent
```

### 2) Upload raw data to S3
```bash
export LANL_S3_BUCKET=my-lanl-bucket
aws s3 mb "s3://${LANL_S3_BUCKET}" --region us-east-1
aws s3 cp auth.txt.gz    "s3://${LANL_S3_BUCKET}/lanl/bronze/"
aws s3 cp flows.txt.gz   "s3://${LANL_S3_BUCKET}/lanl/bronze/"
aws s3 cp dns.txt.gz     "s3://${LANL_S3_BUCKET}/lanl/bronze/"
aws s3 cp proc.txt.gz    "s3://${LANL_S3_BUCKET}/lanl/bronze/"
aws s3 cp redteam.txt.gz "s3://${LANL_S3_BUCKET}/lanl/bronze/"
```

### 3) Launch the EMR pipeline
```bash
bash deploy/launch_emr.sh
```
This creates a transient EMR cluster, runs both PySpark steps
(`bronze_to_silver_emr.py` and `silver_to_gold_emr.py`), and
auto-terminates. Gold parquet lands at
`s3://${LANL_S3_BUCKET}/lanl/gold/computer_time/`.

### 4) Train the model + write artifacts
On a small EC2 box (or your laptop with AWS credentials):
```bash
pip install -r requirements.txt
python -m jobs.train_model
```
This reads gold from S3, logs runs to MLflow (tracking + registry), and
writes `model_outputs/feature_names.json`, `model_outputs/best_model_summary.json`,
and the winning `.joblib`.

### 5) Serve the API
```bash
docker build -f deploy/Dockerfile -t lanl-api:latest .
docker run -d -p 8000:8000 --name lanl-api lanl-api:latest
```
The API container ships with the trained artifact baked in, so it starts
ready to serve.

### 6) Smoke-test the live API
```bash
python test_project.py --url http://<your-ec2-ip>:8000
```
Expected output ends with `PASS: all checks succeeded.`

### 7) Deploy the Streamlit UI
- **Streamlit Cloud** (free, recommended): push the repo to GitHub,
  go to https://share.streamlit.io, point it at `app/streamlit_app.py`,
  set the secret `LANL_API_URL=http://<your-ec2-ip>:8000`.
- **Hugging Face Spaces**: create a Space with type "Streamlit",
  upload this repo, set the same env var.

---

## Option B — Single host with docker-compose (faster demo)

For a self-contained EC2 deploy that puts both the API and the UI on
the same machine:

```bash
# On the EC2 instance, after train_model.py has run once:
docker compose -f deploy/docker-compose.yml up -d --build
```

The API is on port 8000, the UI on port 8501. Open security-group inbound
for both.

---

## Cold-start note for graders

Free-tier hosting (Streamlit Cloud, HF Spaces) sleeps after inactivity.
The first request can take ~30 seconds to wake the dyno. Subsequent
requests are immediate. This is documented in the top-level README so the
grader doesn't mistake a cold start for a failure.
