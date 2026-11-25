#!/usr/bin/env bash
# Idempotent GCP setup for the Lunanele Google BI ingestor.
# Run from the repo root (the Cloud Run button does this automatically).
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT_ID="${GCP_PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}}"
if [[ -z "${PROJECT_ID}" ]]; then
  echo "No GCP project set. Export GCP_PROJECT_ID or run: gcloud config set project <id>" >&2
  exit 1
fi
REGION="${GCP_REGION:-africa-south1}"
PREFIX="${BQ_DATASET_PREFIX:-lunanele_bi}"
SA_NAME="lunanele-bi-runner"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "${PROJECT_ID}"
# merchantapi replaces content.googleapis.com (Content API for Shopping, sunset 18 Aug 2026).
gcloud services enable run.googleapis.com cloudbuild.googleapis.com bigquery.googleapis.com \
  secretmanager.googleapis.com analyticsdata.googleapis.com searchconsole.googleapis.com \
  merchantapi.googleapis.com businessprofileperformance.googleapis.com cloudscheduler.googleapis.com

gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "${SA_NAME}" --display-name="Lunanele BI Ingestor"

# Least privilege: run queries at project level, but edit data only in the BI datasets.
for ROLE in "roles/bigquery.jobUser" "roles/secretmanager.secretAccessor"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" --condition=None --quiet >/dev/null
done

for DS in "${PREFIX}_raw" "${PREFIX}_mart"; do
  bq --location="${REGION}" mk --dataset --force "${PROJECT_ID}:${DS}"
  bq add-iam-policy-binding --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/bigquery.dataEditor" "${PROJECT_ID}:${DS}" >/dev/null
done
# Remove the old project-wide grant if an earlier version of this script added it.
gcloud projects remove-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.dataEditor" --condition=None --quiet >/dev/null 2>&1 || true

# SQL files use the default lunanele_bi prefix; substitute if a custom one is set.
run_sql() { sed "s/lunanele_bi_/${PREFIX}_/g" | bq query --use_legacy_sql=false --location="${REGION}" --project_id="${PROJECT_ID}" >/dev/null; }
run_sql < infrastructure/bigquery/datasets.sql
# Views in dependency order (the acquisition view reads the rollup view).
for V in v_holdings_executive_rollup v_customer_acquisition_daily v_top_search_queries v_data_freshness; do
  { echo "CREATE OR REPLACE VIEW \`lunanele_bi_mart.${V}\` AS"; cat "infrastructure/bigquery/views/${V}.sql"; } | run_sql
done

echo
echo "Done. Grant read access to ${SA_EMAIL} in GA4, Search Console and Merchant Center (see README)."
