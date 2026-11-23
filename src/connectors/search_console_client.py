from datetime import date, timedelta
from googleapiclient.discovery import build

def fetch_search_console_daily(entity: dict, target_date: str | None = None) -> list[dict]:
    site_url = entity.get("search_console_site")
    if not site_url:
        return []
    run_date = target_date or (date.today() - timedelta(days=2)).isoformat()
    service = build("searchconsole", "v1", cache_discovery=False)
    resp = service.searchanalytics().query(
        siteUrl=site_url,
        body={"startDate": run_date, "endDate": run_date, "dimensions": ["query", "page"], "rowLimit": 500},
    ).execute()
    return [{
        "query_date": run_date,
        "entity_slug": entity["slug"],
        "search_query": item.get("keys", ["", ""])[0],
        "page_url": item.get("keys", ["", ""])[1],
        "clicks": int(item.get("clicks", 0)),
        "impressions": int(item.get("impressions", 0)),
        "ctr": float(item.get("ctr", 0.0)),
        "avg_position": float(item.get("position", 0.0)),
    } for item in resp.get("rows", [])]
