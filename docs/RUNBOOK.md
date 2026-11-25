# Runbook — Lunanele Google BI

**Owner:** Lunanele Holdings (Information Officer). **Service:** Cloud Run `lunanele-google-bi-ingestor` (africa-south1). **Schedule:** daily 06:10 SAST.

## Is it healthy?
1. Looker Studio "last updated" tile, or query `lunanele_bi_mart.v_data_freshness`. GA4 should be ≤ 2 days old, Search Console ≤ 3, Business Profile ≤ 4.
2. Last runs: `SELECT * FROM lunanele_bi_raw.sync_runs ORDER BY started_at DESC LIMIT 10`.
3. Errors: Cloud Console → Error Reporting (turn on email notifications there — free).

## Common failures
| Error in `sync_runs.errors_json` | Cause | Fix |
|---|---|---|
| `403` / `PERMISSION_DENIED` (GA4, Search Console, Merchant) | Service account not added to the property | Add `lunanele-bi-runner@<project>.iam.gserviceaccount.com` in that product's user settings |
| `invalid_grant` (Business Profile) | OAuth refresh token revoked/expired | Generate a new token, update the `GBP_OAUTH_REFRESH_TOKEN` secret, redeploy |
| `429` / quota | Google rate limit | Retried automatically; if persistent, lower `SYNC_MAX_WORKERS` |
| `bigquery:*` | Table missing or schema drift | Re-run `scripts/bootstrap_gcp.sh` (idempotent) |

## Re-running data
Re-runs are safe: each (date, entity) slice is replaced, never duplicated.
```bash
URL=$(gcloud run services describe lunanele-google-bi-ingestor --region africa-south1 --format='value(status.url)')
TOKEN=$(gcloud auth print-identity-token)
curl -X POST -H "Authorization: Bearer $TOKEN" "$URL/run-sync?date=2026-11-20"
curl -X POST -H "Authorization: Bearer $TOKEN" "$URL/backfill?start=2026-11-01&end=2026-11-20"
```
Merchant Center is a point-in-time snapshot and cannot be backfilled.

## Changing configuration
Edit `config/*.yaml` in a pull request. CI validates every file (unknown keys and missing settings fail the build). Merge → redeploy.

## Rotating secrets
`GBP_OAUTH_*` and `LUNACORE_API_KEY` live in Secret Manager. Add a new version, redeploy, then disable the old version.
