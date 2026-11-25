SELECT
  event_date,
  entity_slug,
  entity_type,
  SUM(sessions) AS total_sessions,
  SUM(active_users) AS total_active_users,
  SUM(engaged_sessions) AS total_engaged_sessions,
  SUM(conversions) AS total_conversions
FROM (
  SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY event_date, entity_slug, session_source, session_medium ORDER BY ingested_at DESC) AS rn
    FROM `lunanele_bi_raw.ga4_daily_metrics`) WHERE rn = 1)
GROUP BY 1, 2, 3
