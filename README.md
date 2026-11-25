# Lunanele Google Business Intelligence & Customer Acquisition System

[![Run on Google Cloud](https://deploy.cloud.run/button.svg)](https://deploy.cloud.run?git_repo=https://github.com/limekaya65/lunanele-google-business-intelligence)

Production Google Business Intelligence & Customer Acquisition pipeline for **Lunanele Holdings (Pty) Ltd** (pure holding entity) and its five subsidiaries:
- **Infrastructure**
- **Technology**
- **Capital**
- **Agribusiness** (Merchant Center product feed enabled)
- **FX Trades**

## What it does

A FastAPI service on Cloud Run. Calling `POST /run-sync` pulls, for every entity in `config/`:

| Source | Data | BigQuery table |
|---|---|---|
| Google Analytics 4 (Data API) | sessions, users, engaged sessions, key events by source/medium (yesterday) | `lunanele_bi_raw.ga4_daily_metrics` |
| Search Console | clicks, impressions, CTR, position by query/page (2 days ago) | `lunanele_bi_raw.search_console_daily` |
| Merchant Center (Merchant API v1) | product snapshot + approval status | `lunanele_bi_raw.merchant_center_products` |

A summary is optionally posted to LunaCore (`LUNACORE_WEBHOOK_URL` + `LUNACORE_API_KEY`). `GET /health` lists the configured entities.

## Deploy

1. Click **Run on Google Cloud** above (or run `./scripts/bootstrap_gcp.sh`, then deploy with `gcloud run deploy --source .`).
2. The bootstrap creates the `lunanele-bi-runner` service account, BigQuery datasets/tables and the executive roll-up view, and the Cloud Run service runs as that account.
3. **Grant that service account read access to your data** — Google APIs will return 403 until you do:
   - **GA4**: Admin → Property access management → add `lunanele-bi-runner@<project>.iam.gserviceaccount.com` as *Viewer*.
   - **Search Console**: Settings → Users and permissions → add the same email (*Restricted* is enough).
   - **Merchant Center**: Settings → People and access → add the same email.
4. Schedule the sync daily with Cloud Scheduler, e.g.
   ```bash
   gcloud scheduler jobs create http lunanele-bi-daily --location africa-south1 \
     --schedule "0 6 * * *" --time-zone "Africa/Johannesburg" \
     --uri "https://<service-url>/run-sync" --http-method POST \
     --oidc-service-account-email lunanele-bi-runner@<project>.iam.gserviceaccount.com
   ```
   (give that account `roles/run.invoker` on the service).

## Configuration

| Env var | Purpose |
|---|---|
| `GCP_PROJECT_ID` | Project holding the BigQuery datasets |
| `BQ_DATASET_PREFIX` | Dataset prefix (default `lunanele_bi`) |
| `GA4_<ENTITY>_PROPERTY_ID` | GA4 property per entity (`HOLDINGS`, `INFRASTRUCTURE`, `TECHNOLOGY`, `CAPITAL`, `AGRIBUSINESS`, `FX_TRADES`); unset = skipped |
| `MERCHANT_CENTER_AGRIBUSINESS_ID` | Merchant Center account ID |
| `LUNACORE_WEBHOOK_URL`, `LUNACORE_API_KEY` | Optional LunaCore push |

Entities live in `config/holdings.yaml` and `config/subsidiaries/*.yaml`. A failing connector for one entity is reported in the response's `errors` list without stopping the others.

## Notes

- Files must be saved as UTF-8 **without BOM** and with LF line endings (enforced by `.gitattributes` / `.editorconfig`). On Windows PowerShell 5, use `Set-Content -Encoding utf8NoBOM` (PS 7+) or save from VS Code.
- The `conversions` column holds GA4 **key events** (GA4 renamed the metric in 2024).
