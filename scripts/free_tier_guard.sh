#!/usr/bin/env bash
# Run once after the Cloud Run service exists.
#  1. Daily Cloud Scheduler job -> POST /run-sync (3 jobs per billing account are free)
#  2. Billing budget alert at R1 / $1 so you are emailed before anything is charged
#  3. Artifact Registry cleanup so old container images don't exceed the free 0.5 GB
#
# Usage: GCP_PROJECT_ID=... BILLING_ACCOUNT_ID=XXXXXX-XXXXXX-XXXXXX ./scripts/free_tier_guard.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT_ID="${GCP_PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}}"
REGION="${GCP_REGION:-africa-south1}"
SERVICE="${SERVICE_NAME:-lunanele-google-bi-ingestor}"
SA_EMAIL="lunanele-bi-runner@${PROJECT_ID}.iam.gserviceaccount.com"

URL="$(gcloud run services describe "${SERVICE}" --region "${REGION}" --project "${PROJECT_ID}" --format='value(status.url)')"
echo "Service: ${URL}"

# 1. Scheduler: 06:10 Johannesburg every day, authenticated as the runner account.
gcloud run services add-iam-policy-binding "${SERVICE}" --region "${REGION}" --project "${PROJECT_ID}" \
  --member "serviceAccount:${SA_EMAIL}" --role roles/run.invoker --quiet >/dev/null
if gcloud scheduler jobs describe lunanele-bi-daily --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  ACTION=update
else
  ACTION=create
fi
gcloud scheduler jobs "${ACTION}" http lunanele-bi-daily --location "${REGION}" --project "${PROJECT_ID}" \
  --schedule "10 6 * * *" --time-zone "Africa/Johannesburg" \
  --uri "${URL}/run-sync" --http-method POST --attempt-deadline 600s \
  --oidc-service-account-email "${SA_EMAIL}" --oidc-token-audience "${URL}" --quiet

# 2. Budget alert (needs Billing Account Administrator or Costs Manager on the billing account).
if [[ -n "${BILLING_ACCOUNT_ID:-}" ]]; then
  gcloud services enable billingbudgets.googleapis.com --project "${PROJECT_ID}"
  if ! gcloud billing budgets list --billing-account "${BILLING_ACCOUNT_ID}" --format='value(displayName)' | grep -qx "Lunanele free-tier guard"; then
    gcloud billing budgets create --billing-account "${BILLING_ACCOUNT_ID}" \
      --display-name "Lunanele free-tier guard" --budget-amount 1 \
      --threshold-rule percent=0.01 --threshold-rule percent=1.0
  fi
else
  echo "BILLING_ACCOUNT_ID not set: skipping budget alert (find it with: gcloud billing accounts list)"
fi

# 3. Keep only the 2 newest images in the Cloud Run source-deploy repository.
REPO="${AR_REPO:-cloud-run-source-deploy}"
if gcloud artifacts repositories describe "${REPO}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  cat > /tmp/ar-cleanup.json <<'JSON'
[
  {"name": "keep-latest-2", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 2}},
  {"name": "delete-rest", "action": {"type": "Delete"}, "condition": {"tagState": "any"}}
]
JSON
  gcloud artifacts repositories set-cleanup-policies "${REPO}" --location "${REGION}" \
    --project "${PROJECT_ID}" --policy /tmp/ar-cleanup.json --no-dry-run --quiet
fi
echo "Free-tier guard in place."
