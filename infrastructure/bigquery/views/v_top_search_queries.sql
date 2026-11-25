SELECT entity_slug, search_query,
       SUM(clicks) AS clicks, SUM(impressions) AS impressions,
       SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
       ROUND(AVG(avg_position), 1) AS avg_position
FROM (SELECT * EXCEPT(rn) FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY query_date, entity_slug, search_query, page_url ORDER BY ingested_at DESC) AS rn
  FROM `lunanele_bi_raw.search_console_daily`) WHERE rn = 1)
WHERE query_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
GROUP BY 1, 2
