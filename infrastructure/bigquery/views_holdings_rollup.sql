CREATE OR REPLACE VIEW `lunanele_bi_mart.v_holdings_executive_rollup` AS
SELECT
  event_date,
  entity_slug,
  entity_type,
  SUM(sessions) AS total_sessions,
  SUM(active_users) AS total_active_users,
  SUM(engaged_sessions) AS total_engaged_sessions,
  SUM(conversions) AS total_conversions
FROM `lunanele_bi_raw.ga4_daily_metrics`
GROUP BY 1, 2, 3;
