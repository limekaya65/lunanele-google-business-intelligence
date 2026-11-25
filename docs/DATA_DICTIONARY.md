# Data dictionary

All tables are partitioned by their date column and clustered by `entity_slug`. No personal information is stored: GA4 and Search Console data are aggregated by Google.

## lunanele_bi_raw
| Table | Grain | Source lag | Key columns |
|---|---|---|---|
| `ga4_daily_metrics` | date × entity × source/medium | 1 day | `sessions`, `active_users`, `engaged_sessions`, `conversions` (= GA4 key events) |
| `search_console_daily` | date × entity × query × page | 2 days | `clicks`, `impressions`, `ctr` (0–1), `avg_position` |
| `business_profile_daily` | date × entity | 3 days | Search/Maps impressions (desktop/mobile), `call_clicks`, `website_clicks`, `direction_requests`, `conversations` |
| `merchant_center_products` | snapshot date × entity × product | same day | `offer_id`, `title`, `availability`, `approval_status` (approved/pending/disapproved); `clicks`/`impressions` NULL |
| `sync_runs` | one row per run | — | `run_id`, `status` (completed / completed_with_errors / failed), `rows_written`, `errors_json` |

## lunanele_bi_mart (Looker Studio)
| View | Use |
|---|---|
| `v_customer_acquisition_daily` | Main dashboard: per entity per day — sessions, leads, search clicks/impressions, profile views/actions |
| `v_top_search_queries` | Last 90 days of Google searches bringing people to each entity |
| `v_holdings_executive_rollup` | GA4 totals per entity per day |
| `v_data_freshness` | Latest date loaded per source and entity |

## Entities
`holdings`, `technology` (tech.lunaneleholdings.com), `agribusiness`, `infrastructure`, `capital`, `fx-trades` (all connectors off — not public-facing).
