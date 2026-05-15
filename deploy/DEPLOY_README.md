# Deployment Guide

How to deploy the LANL threat prediction API and Streamlit dashboard.

---

## Option A — Distributed cloud pipeline

This is the full cloud path: raw LANL files land in S3, Spark jobs run on EMR, cleaned parquet outputs are written back to S3, models are trained and tracked with MLflow, and the final model is served through FastAPI on EC2.

### 1) Configure AWS

```bash
aws configure
aws emr create-default-roles
```

`aws configure` sets your access key, secret key, default region, and output format.  
`aws emr create-default-roles` creates the default EMR service roles if they do not already exist.

---

### 2) Upload raw LANL data to S3

```bash
export LANL_S3_BUCKET=my-lanl-bucket

aws s3 mb "s3://${LANL_S3_BUCKET}" --region us-east-1

aws s3 cp auth.txt.gz    "s3://${LANL_S3_BUCKET}/lanl/bronze/"
aws s3 cp flows.txt.gz   "s3://${LANL_S3_BUCKET}/lanl/bronze/"
aws s3 cp dns.txt.gz     "s3://${LANL_S3_BUCKET}/lanl/bronze/"
aws s3 cp proc.txt.gz    "s3://${LANL_S3_BUCKET}/lanl/bronze/"
aws s3 cp redteam.txt.gz "s3://${LANL_S3_BUCKET}/lanl/bronze/"
```

The raw `.txt.gz` files are kept unchanged in the bronze layer so the entire pipeline can be rebuilt from the original source files.

---

### 3) Launch the EMR pipeline

```bash
bash deploy/launch_emr.sh
```

This creates a transient EMR cluster, runs both PySpark jobs, and auto-terminates after the steps finish.

The two Spark stages are:

```text
jobs/bronze_to_silver_emr.py
jobs/silver_to_gold_emr.py
```

The output gold table lands at:

```text
s3://${LANL_S3_BUCKET}/lanl/gold/computer_time/
```

The gold table is the model-ready layer. Each row represents one computer in one time window, with engineered behavioral features and the next-window red-team target.

---

### 4) Train the model and write artifacts

On an EC2 instance or local machine with AWS credentials:

```bash
pip install -r requirements.txt
python -m jobs.train_model
```

This step:

- reads the gold table from S3
- removes leakage-sensitive columns
- trains supervised models
- logs metrics and artifacts to MLflow
- writes the feature contract and model summary
- saves the winning model artifact used by the API

Expected output artifacts include:

```text
model_outputs/feature_names.json
model_outputs/best_model_summary.json
model_outputs/<model_name>/<model_name>.joblib
```

---

### 5) Serve the FastAPI backend

Build the container:

```bash
docker build -f deploy/Dockerfile -t lanl-api:latest .
```

Run the API:

```bash
docker run -d -p 8000:8000 --name lanl-api lanl-api:latest
```

The API container starts with the trained model artifact available, so it should be ready to serve predictions immediately.

Useful endpoints:

```text
GET  /health
GET  /model_info
GET  /features
POST /predict
POST /batch_predict
POST /explain
POST /counterfactual
```

---

### 6) Smoke-test the live API

```bash
python test_project.py --url http://<your-ec2-ip>:8000
```

Expected final line:

```text
PASS: all checks succeeded.
```

The smoke test checks that the API is running, the model is loaded, the feature contract is available, and prediction requests work.

---

### 7) Deploy the Streamlit UI

#### Streamlit Cloud

1. Push the repository to GitHub.
2. Go to https://share.streamlit.io.
3. Select the repository.
4. Set the app entry point to:

```text
app/streamlit_app.py
```

5. Add this secret or environment variable:

```text
LANL_API_URL=http://<your-ec2-ip>:8000
```

#### Hugging Face Spaces

1. Create a new Space.
2. Select Streamlit as the app type.
3. Upload or connect this repository.
4. Set the same environment variable:

```text
LANL_API_URL=http://<your-ec2-ip>:8000
```

---

## Option B — Single-host deployment with docker-compose

This is the faster demo path. It runs both the FastAPI backend and Streamlit UI on one host.

On the EC2 instance, after `train_model.py` has run at least once:

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

The services run on:

```text
API: http://<your-ec2-ip>:8000
UI:  http://<your-ec2-ip>:8501
```

Make sure the EC2 security group allows inbound traffic for the ports you want to expose.

---

## Local verification path

The full pipeline is cloud-first, but the repository also includes a local verification path using the small gold sample.

```bash
pip install -r requirements.txt
python run_local_demo.py
```

This script trains from the local gold sample, starts the API, runs the smoke test, and shuts the API down.

This path is useful for checking that the model artifact, FastAPI service, feature contract, and test script all work without rerunning EMR.

---

## Cold-start note

Free hosting tiers such as Streamlit Cloud or Hugging Face Spaces may sleep after inactivity. The first request can take around 30 seconds while the app wakes up. Subsequent requests are usually much faster.

---

## Security notes

Do not commit AWS credentials, API keys, tokens, `.env` files, or private SSH keys.

Recommended setup:

- keep AWS credentials in the AWS CLI credential store
- pass runtime settings through environment variables
- keep Streamlit secrets in the platform secret manager
- keep EC2 security groups limited to the ports needed for the API and UI
- use HTTPS and a reverse proxy for longer-term public deployments

---

## Deployment checklist

Before sharing the live app, confirm:

- [ ] Raw LANL files are uploaded to S3 bronze
- [ ] EMR bronze-to-silver job completed
- [ ] EMR silver-to-gold job completed
- [ ] Gold parquet exists in S3
- [ ] `python -m jobs.train_model` completed
- [ ] Model artifacts exist in `model_outputs/`
- [ ] FastAPI is running on port 8000
- [ ] `python test_project.py --url http://<your-ec2-ip>:8000` passes
- [ ] Streamlit app points to the correct `LANL_API_URL`
- [ ] No credentials are committed to the repository
