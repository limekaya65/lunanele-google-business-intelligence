import os
from datetime import date
from googleapiclient.discovery import build

def fetch_merchant_products(entity: dict) -> list[dict]:
    if not entity.get("ecommerce_enabled"):
        return []
    merchant_id = os.getenv(f"MERCHANT_CENTER_{entity['slug'].upper().replace('-', '_')}_ID", "")
    if not merchant_id or merchant_id == "000000000":
        return []
    service = build("content", "v2.1", cache_discovery=False)
    resp = service.products().list(merchantId=merchant_id, maxResults=250).execute()
    today = date.today().isoformat()
    return [{
        "snapshot_date": today,
        "entity_slug": entity["slug"],
        "offer_id": p.get("offerId", ""),
        "title": p.get("title", ""),
        "availability": p.get("availability", "unknown"),
        "approval_status": "active",
        "clicks": 0,
        "impressions": 0,
    } for p in resp.get("resources", [])]
