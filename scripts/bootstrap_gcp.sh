#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project)}"
REGION="${GCP_REGION:-africa-south1}"
SA_NAME="lunanele-bi-runner"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "${PROJECT_ID}"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com bigquery.googleapis.com secretmanager.googleapis.com analyticsdata.googleapis.com searchconsole.googleapis.com content.googleapis.com

gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "${SA_NAME}" --display-name="Lunanele BI Ingestor"

for ROLE in "roles/bigquery.dataEditor" "roles/bigquery.jobUser" "roles/secretmanager.secretAccessor"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${SA_EMAIL}" --role="${ROLE}" --quiet >/dev/null
done

for DS in "lunanele_bi_raw" "lunanele_bi_mart"; do
  bq --location="${REGION}" mk --dataset --force "${PROJECT_ID}:${DS}"
done

bq query --use_legacy_sql=false --project_id="${PROJECT_ID}" < infrastructure/bigquery/datasets.sql
bq query --use_legacy_sql=false --project_id="${PROJECT_ID}" < infrastructure/bigquery/views_holdings_rollup.sql
