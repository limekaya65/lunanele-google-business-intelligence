SELECT 'ga4' AS source, entity_slug, MAX(event_date) AS latest_date FROM `lunanele_bi_raw.ga4_daily_metrics` GROUP BY 1, 2
UNION ALL SELECT 'search_console', entity_slug, MAX(query_date) FROM `lunanele_bi_raw.search_console_daily` GROUP BY 1, 2
UNION ALL SELECT 'business_profile', entity_slug, MAX(metric_date) FROM `lunanele_bi_raw.business_profile_daily` GROUP BY 1, 2
UNION ALL SELECT 'merchant_center', entity_slug, MAX(snapshot_date) FROM `lunanele_bi_raw.merchant_center_products` GROUP BY 1, 2
