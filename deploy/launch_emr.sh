#!/usr/bin/env bash
# =============================================================================
# deploy/launch_emr.sh
# =============================================================================
# Launch an AWS EMR cluster, submit both PySpark steps (bronze->silver,
# silver->gold), then terminate the cluster. This is the script that makes
# the "distributed pipeline" claim concrete instead of just a code shape.
#
# What it does
# ------------
#   1. Creates a transient EMR cluster (release 6.15.0, Spark 3.4) using
#      free-tier-friendly m5.xlarge instances.
#   2. Sync the project code to a "deploy" prefix in S3 so the EMR
#      executors can read it.
#   3. Submit `jobs/bronze_to_silver_emr.py` as Step 1.
#   4. Submit `jobs/silver_to_gold_emr.py` as Step 2.
#   5. Auto-terminate after Step 2 succeeds (transient cluster pattern).
#
# Requirements
# ------------
#   * AWS CLI v2 installed and `aws configure`-d.
#   * An S3 bucket you own. Set LANL_S3_BUCKET below.
#   * An EMR service role + EC2 instance profile in your account.
#     (Create with `aws emr create-default-roles` if you don't have them.)
#
# Usage
# -----
#   export LANL_S3_BUCKET=my-lanl-bucket
#   bash deploy/launch_emr.sh
#
# Notes
# -----
#   * Costs roughly $0.50-$1.00 per pipeline run on m5.xlarge / 3 nodes /
#     ~30 minutes. Always check your billing console.
#   * The cluster auto-terminates - don't leave it running on accident.
# =============================================================================
set -euo pipefail

BUCKET="${LANL_S3_BUCKET:?Set LANL_S3_BUCKET to your S3 bucket name}"
REGION="${AWS_REGION:-us-east-1}"
CLUSTER_NAME="${CLUSTER_NAME:-lanl-threat-pipeline}"
RELEASE="${EMR_RELEASE:-emr-6.15.0}"
LOG_URI="s3://${BUCKET}/lanl/emr-logs/"
CODE_PREFIX="s3://${BUCKET}/lanl/deploy"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# --------------------------------------------------------------------------
# Windows / Git Bash path helper.
#
# In MINGW64 / Git Bash, /tmp/foo is actually C:\Users\<user>\AppData\Local\
# Temp\foo on disk. Bash understands /tmp/foo, but the AWS CLI is a native
# Windows binary and tries to open the literal path '/tmp/foo' (which on
# Windows is parsed as C:\tmp\foo and does not exist). cygpath -m converts
# an MSYS path to a Windows path WITH FORWARD SLASHES, which is what
# `file://` URLs and AWS CLI both accept on Windows.
# --------------------------------------------------------------------------
to_native_path() {
    if command -v cygpath >/dev/null 2>&1; then
        cygpath -m "$1" 2>/dev/null || echo "$1"
    else
        echo "$1"
    fi
}

# --------------------------------------------------------------------------
# Pre-flight: confirm the EMR default IAM roles exist. Without these,
# RunJobFlow fails with "Invalid InstanceProfile: EMR_EC2_DefaultRole".
# `aws emr create-default-roles` is idempotent - safe to re-run.
# --------------------------------------------------------------------------
for role in EMR_DefaultRole EMR_EC2_DefaultRole; do
    if ! aws iam get-role --role-name "${role}" >/dev/null 2>&1; then
        echo "ERROR: IAM role '${role}' is missing." >&2
        echo "Create the EMR default roles with:" >&2
        echo "  aws emr create-default-roles" >&2
        exit 1
    fi
done

echo "[1/5] Building dependency zip + uploading project code to ${CODE_PREFIX}"
# Spark's --py-files needs a .zip that PRESERVES the package layout, not a
# directory and not loose .py files. We bundle config/ and utils/ together
# so that `from config.settings import settings` works on the workers.
if ! command -v zip >/dev/null 2>&1; then
    echo "ERROR: 'zip' command is not available in this shell." >&2
    echo "Install Git for Windows with default options, or run from WSL." >&2
    exit 1
fi

DEPS_ZIP="$(mktemp -t lanl-deps-XXXXXX).zip"
STEPS_FILE="$(mktemp -t lanl-steps-XXXXXX).json"
trap "rm -f '${DEPS_ZIP}' '${STEPS_FILE}'" EXIT

(
    cd "${REPO_ROOT}"
    zip -qr "${DEPS_ZIP}" config utils -x "*/__pycache__/*" "*.pyc"
)
DEPS_ZIP_NATIVE="$(to_native_path "${DEPS_ZIP}")"
echo "       built deps zip: ${DEPS_ZIP_NATIVE} ($(du -h "${DEPS_ZIP}" | cut -f1))"

aws s3 cp "${DEPS_ZIP_NATIVE}" "${CODE_PREFIX}/lanl_deps.zip" --region "${REGION}"

aws s3 sync "${REPO_ROOT}" "${CODE_PREFIX}" \
    --exclude "*" \
    --include "jobs/*.py" \
    --region "${REGION}"

echo "[2/5] Writing EMR steps file"
# Why a file instead of a shell variable?
# AWS CLI v2 on Windows (Git Bash, MINGW64) word-splits multi-line JSON
# variables in unpredictable ways. The recommended pattern for complex JSON
# inputs on Windows is to write the JSON to a temp file and pass it with
# the `file://` scheme - that bypasses every shell quoting trap.
cat > "${STEPS_FILE}" <<EOF
[
  {
    "Type": "CUSTOM_JAR",
    "Name": "bronze_to_silver",
    "ActionOnFailure": "TERMINATE_CLUSTER",
    "Jar": "command-runner.jar",
    "Args": [
      "spark-submit",
      "--deploy-mode", "cluster",
      "--py-files", "${CODE_PREFIX}/lanl_deps.zip",
      "${CODE_PREFIX}/jobs/bronze_to_silver_emr.py"
    ]
  },
  {
    "Type": "CUSTOM_JAR",
    "Name": "silver_to_gold",
    "ActionOnFailure": "TERMINATE_CLUSTER",
    "Jar": "command-runner.jar",
    "Args": [
      "spark-submit",
      "--deploy-mode", "cluster",
      "--py-files", "${CODE_PREFIX}/lanl_deps.zip",
      "${CODE_PREFIX}/jobs/silver_to_gold_emr.py"
    ]
  }
]
EOF
STEPS_FILE_NATIVE="$(to_native_path "${STEPS_FILE}")"
echo "       wrote steps file: ${STEPS_FILE_NATIVE}"

echo "[3/5] Creating cluster + submitting steps"
# Use --instance-groups shorthand (key=value,key=value tokens). This avoids
# the JSON-quoting issue on Windows that bites --instances. --auto-terminate
# tells EMR to shut the cluster down once all steps finish.
CLUSTER_ID=$(aws emr create-cluster \
    --name "${CLUSTER_NAME}" \
    --release-label "${RELEASE}" \
    --applications Name=Spark Name=Hadoop \
    --service-role EMR_DefaultRole \
    --ec2-attributes InstanceProfile=EMR_EC2_DefaultRole \
    --log-uri "${LOG_URI}" \
    --auto-terminate \
    --instance-groups \
        Name=Primary,InstanceCount=1,InstanceGroupType=MASTER,InstanceType=m5.xlarge \
        Name=Core,InstanceCount=2,InstanceGroupType=CORE,InstanceType=m5.xlarge \
    --steps "file://${STEPS_FILE_NATIVE}" \
    --region "${REGION}" \
    --query 'ClusterId' --output text)

echo "[4/5] Cluster id: ${CLUSTER_ID}"
echo "       Logs: ${LOG_URI}${CLUSTER_ID}/"

echo "[5/5] Waiting for cluster to terminate (this is the auto-terminate pattern)"
# Don't use `aws emr wait cluster-terminated` here - its default max-attempts
# is 60 polls * 30s = 30 minutes, and our LANL pipeline regularly takes
# longer than that. We poll manually with no max-attempts cap so the script
# never gives up before the cluster does.
STATE=""
while true; do
    STATE=$(aws emr describe-cluster --cluster-id "${CLUSTER_ID}" \
            --region "${REGION}" \
            --query 'Cluster.Status.State' --output text)
    echo "       $(date +%H:%M:%S)  state=${STATE}"
    case "${STATE}" in
        TERMINATED|TERMINATED_WITH_ERRORS)
            break
            ;;
    esac
    sleep 60
done

echo "Final cluster state: ${STATE}"

if [[ "${STATE}" == "TERMINATED_WITH_ERRORS" ]]; then
  echo "Cluster terminated with errors. Check ${LOG_URI}${CLUSTER_ID}/"
  exit 1
fi

echo "Done. Gold table is at s3://${BUCKET}/lanl/gold/computer_time/"
echo "Next: python -m jobs.train_model   then  uvicorn app.api_app:app ..."
