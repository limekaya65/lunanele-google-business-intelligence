-- Views for Looker Studio (free). Connect Looker Studio to the lunanele_bi_mart dataset.
-- Each sync appends rows, so views de-duplicate by keeping the latest ingest per key.

CREATE OR REPLACE VIEW `lunanele_bi_mart.v_holdings_executive_rollup` AS
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
GROUP BY 1, 2, 3;

-- One row per entity per day: website, Google Search and Business Profile side by side.
CREATE OR REPLACE VIEW `lunanele_bi_mart.v_customer_acquisition_daily` AS
WITH ga4 AS (
  SELECT event_date AS d, entity_slug, total_sessions AS sessions, total_engaged_sessions AS engaged_sessions,
         total_conversions AS leads
  FROM `lunanele_bi_mart.v_holdings_executive_rollup`),
gsc AS (
  SELECT query_date AS d, entity_slug, SUM(clicks) AS search_clicks, SUM(impressions) AS search_impressions
  FROM (SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY query_date, entity_slug, search_query, page_url ORDER BY ingested_at DESC) AS rn
    FROM `lunanele_bi_raw.search_console_daily`) WHERE rn = 1)
  GROUP BY 1, 2),
gbp AS (
  SELECT metric_date AS d, entity_slug,
         impressions_search_desktop + impressions_search_mobile + impressions_maps_desktop + impressions_maps_mobile AS profile_views,
         call_clicks + website_clicks + direction_requests + conversations AS profile_actions
  FROM (SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY metric_date, entity_slug ORDER BY ingested_at DESC) AS rn
    FROM `lunanele_bi_raw.business_profile_daily`) WHERE rn = 1))
SELECT
  COALESCE(ga4.d, gsc.d, gbp.d) AS date,
  COALESCE(ga4.entity_slug, gsc.entity_slug, gbp.entity_slug) AS entity_slug,
  IFNULL(sessions, 0) AS sessions, IFNULL(engaged_sessions, 0) AS engaged_sessions, IFNULL(leads, 0) AS leads,
  IFNULL(search_clicks, 0) AS search_clicks, IFNULL(search_impressions, 0) AS search_impressions,
  IFNULL(profile_views, 0) AS profile_views, IFNULL(profile_actions, 0) AS profile_actions
FROM ga4
FULL OUTER JOIN gsc ON ga4.d = gsc.d AND ga4.entity_slug = gsc.entity_slug
FULL OUTER JOIN gbp ON COALESCE(ga4.d, gsc.d) = gbp.d AND COALESCE(ga4.entity_slug, gsc.entity_slug) = gbp.entity_slug;

-- Top Google searches that bring people to each entity (last 90 days).
CREATE OR REPLACE VIEW `lunanele_bi_mart.v_top_search_queries` AS
SELECT entity_slug, search_query,
       SUM(clicks) AS clicks, SUM(impressions) AS impressions,
       SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
       ROUND(AVG(avg_position), 1) AS avg_position
FROM (SELECT * EXCEPT(rn) FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY query_date, entity_slug, search_query, page_url ORDER BY ingested_at DESC) AS rn
  FROM `lunanele_bi_raw.search_console_daily`) WHERE rn = 1)
WHERE query_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
GROUP BY 1, 2;
