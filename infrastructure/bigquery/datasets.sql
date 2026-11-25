CREATE TABLE IF NOT EXISTS `lunanele_bi_raw.ga4_daily_metrics` (
  event_date DATE NOT NULL,
  entity_slug STRING NOT NULL,
  entity_type STRING NOT NULL,
  session_source STRING,
  session_medium STRING,
  sessions INT64,
  active_users INT64,
  engaged_sessions INT64,
  conversions INT64,
  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
) PARTITION BY event_date CLUSTER BY entity_slug;

CREATE TABLE IF NOT EXISTS `lunanele_bi_raw.search_console_daily` (
  query_date DATE NOT NULL,
  entity_slug STRING NOT NULL,
  search_query STRING,
  page_url STRING,
  clicks INT64,
  impressions INT64,
  ctr FLOAT64,
  avg_position FLOAT64,
  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
) PARTITION BY query_date CLUSTER BY entity_slug;

CREATE TABLE IF NOT EXISTS `lunanele_bi_raw.merchant_center_products` (
  snapshot_date DATE NOT NULL,
  entity_slug STRING NOT NULL,
  offer_id STRING,
  title STRING,
  availability STRING,
  approval_status STRING,
  clicks INT64,
  impressions INT64,
  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
) PARTITION BY snapshot_date CLUSTER BY entity_slug;

CREATE TABLE IF NOT EXISTS `lunanele_bi_raw.business_profile_daily` (
  metric_date DATE NOT NULL,
  entity_slug STRING NOT NULL,
  location_id STRING,
  impressions_search_desktop INT64,
  impressions_search_mobile INT64,
  impressions_maps_desktop INT64,
  impressions_maps_mobile INT64,
  call_clicks INT64,
  website_clicks INT64,
  direction_requests INT64,
  conversations INT64,
  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
) PARTITION BY metric_date CLUSTER BY entity_slug;

-- Audit trail: one row per sync run.
CREATE TABLE IF NOT EXISTS `lunanele_bi_raw.sync_runs` (
  run_id STRING NOT NULL,
  started_at TIMESTAMP NOT NULL,
  finished_at TIMESTAMP,
  status STRING,
  target_date DATE,
  rows_written INT64,
  error_count INT64,
  errors_json STRING
) PARTITION BY DATE(started_at);
