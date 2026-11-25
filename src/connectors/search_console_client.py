from datetime import date, timedelta

import google.auth
from googleapiclient.discovery import build

# Cloud Run's default token is cloud-platform scoped, which Search Console rejects.
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
ROW_LIMIT = 25000


def fetch_search_console_daily(entity: dict, target_date: str | None = None) -> list[dict]:
    site_url = entity.get("search_console_site")
    if not site_url:
        return []
    run_date = target_date or (date.today() - timedelta(days=2)).isoformat()
    credentials, _ = google.auth.default(scopes=SCOPES)
    service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)

    rows, start_row = [], 0
    while True:
        resp = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": run_date,
                "endDate": run_date,
                "dimensions": ["query", "page"],
                "rowLimit": ROW_LIMIT,
                "startRow": start_row,
            },
        ).execute()
        batch = resp.get("rows", [])
        rows.extend(batch)
        if len(batch) < ROW_LIMIT:
            break
        start_row += ROW_LIMIT

    return [{
        "query_date": run_date,
        "entity_slug": entity["slug"],
        "search_query": item.get("keys", ["", ""])[0],
        "page_url": item.get("keys", ["", ""])[1],
        "clicks": int(item.get("clicks", 0)),
        "impressions": int(item.get("impressions", 0)),
        "ctr": float(item.get("ctr", 0.0)),
        "avg_position": float(item.get("position", 0.0)),
    } for item in rows]
