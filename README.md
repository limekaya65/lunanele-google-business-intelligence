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
| Business Profile (Performance API) | Search/Maps views, calls, website clicks, directions, chats | `lunanele_bi_raw.business_profile_daily` |

Looker Studio dashboards read the views in `lunanele_bi_mart`:
`v_customer_acquisition_daily` (one row per entity per day), `v_top_search_queries`, `v_holdings_executive_rollup`.

`POST /run-sync?date=YYYY-MM-DD` re-runs one day and `POST /backfill?start=…&end=…` re-runs up to 31 days; re-runs replace data, never duplicate it. Every run is recorded in `lunanele_bi_raw.sync_runs`.

See `docs/RUNBOOK.md` (operations) and `docs/DATA_DICTIONARY.md` (tables and views).

A summary is optionally posted to LunaCore (`LUNACORE_WEBHOOK_URL` + `LUNACORE_API_KEY`). `GET /health` lists the configured entities.

## Deploy

1. Click **Run on Google Cloud** above (or run `./scripts/bootstrap_gcp.sh`, then deploy with `gcloud run deploy --source .`).
2. The bootstrap creates the `lunanele-bi-runner` service account, BigQuery datasets/tables and the executive roll-up view, and the Cloud Run service runs as that account.
3. **Grant that service account read access to your data** — Google APIs will return 403 until you do:
   - **GA4**: Admin → Property access management → add `lunanele-bi-runner@<project>.iam.gserviceaccount.com` as *Viewer*.
   - **Search Console**: Settings → Users and permissions → add the same email (*Restricted* is enough).
   - **Merchant Center**: Settings → People and access → add the same email.
   - **Business Profile** does not accept service accounts: create an OAuth client (Desktop app) in the same project, request access to the Business Profile APIs (free, via Google's application form), generate a refresh token for the Google account that manages the profiles, and set `GBP_OAUTH_*` plus each `GBP_<ENTITY>_LOCATION_ID`.
4. Run `BILLING_ACCOUNT_ID=... ./scripts/free_tier_guard.sh`. It schedules the sync daily at 06:10 SAST, adds a $1 budget alert so you hear before anything is charged, and limits stored container images.

## Staying on free tiers

- BigQuery is written with **load jobs** (free), not streaming inserts (billed).
- One Cloud Scheduler job, a small Cloud Run service and a few MB of BigQuery data sit well inside Google's monthly free allowances; the budget alert is the safety net.
- FX Trades has every connector switched off (not public-facing). Subsidiaries without a live website have Search Console off until one exists.

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
