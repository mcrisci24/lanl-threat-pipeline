# =============================================================================
# deploy/Dockerfile
# =============================================================================
# Container image for the FastAPI prediction service.
#
# Build:    docker build -f deploy/Dockerfile -t lanl-api:latest .
# Run:      docker run -p 8000:8000 lanl-api:latest
# Test:     python test_project.py --url http://localhost:8000
#
# The image only contains what the serving layer needs - it does NOT
# include PySpark or the EMR jobs, because those run on the cluster.
# =============================================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# --- System libraries -----------------------------------------------------
# LightGBM links against libgomp.so.1 (GNU OpenMP) at runtime for its
# parallel tree-fit/predict. The python:3.11-slim base image strips this
# out, so we install it explicitly via apt. Without this you get:
#   OSError: libgomp.so.1: cannot open shared object file
# at container startup when joblib.load() tries to unpickle a LightGBM
# pipeline. XGBoost ships its own OpenMP runtime in its wheel, so this is
# only needed for LightGBM - but the package is tiny (~140 KB).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# --- Install only the serving-time dependencies --------------------------
# We avoid installing pyspark in the API image - smaller image, faster boot.
# xgboost is REQUIRED here even if it's not used in the request path:
# joblib.load() of an XGBClassifier pipeline needs the xgboost module
# installed so the pickle can resolve the class. Without it, the API
# crashes at startup with ModuleNotFoundError.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir \
    "fastapi>=0.110" "uvicorn[standard]>=0.27" "pydantic>=2.5" \
    "scikit-learn>=1.4,<2.0" "joblib>=1.3" "numpy>=1.26" "pandas>=2.1" \
    "mlflow>=2.10" \
    "xgboost>=2.0" \
    "lightgbm>=4.0"

# --- Copy the code + the trained artifacts -------------------------------
# train_model.py writes ./model_outputs/ ; we bake that into the image so
# the API starts with a model ready to serve.
COPY config /app/config
COPY app /app/app
COPY model_outputs /app/model_outputs

ENV LANL_LOCAL_MODEL_DIR=/app/model_outputs

EXPOSE 8000

# --- Healthcheck so Docker Swarm / ECS knows the service is healthy ------
HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import requests,sys; r=requests.get('http://127.0.0.1:8000/health',timeout=3); sys.exit(0 if r.status_code==200 and r.json().get('model_loaded') else 1)"

CMD ["uvicorn", "app.api_app:app", "--host", "0.0.0.0", "--port", "8000"]
