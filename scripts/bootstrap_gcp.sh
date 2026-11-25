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
  merchantapi.googleapis.com

gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "${SA_NAME}" --display-name="Lunanele BI Ingestor"

for ROLE in "roles/bigquery.dataEditor" "roles/bigquery.jobUser" "roles/secretmanager.secretAccessor"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" --condition=None --quiet >/dev/null
done

for DS in "${PREFIX}_raw" "${PREFIX}_mart"; do
  bq --location="${REGION}" mk --dataset --force "${PROJECT_ID}:${DS}"
done

# SQL files use the default lunanele_bi prefix; substitute if a custom one is set.
for SQL in infrastructure/bigquery/datasets.sql infrastructure/bigquery/views_holdings_rollup.sql; do
  sed "s/lunanele_bi_/${PREFIX}_/g" "${SQL}" | \
    bq query --use_legacy_sql=false --location="${REGION}" --project_id="${PROJECT_ID}"
done

echo
echo "Done. Grant read access to ${SA_EMAIL} in GA4, Search Console and Merchant Center (see README)."
