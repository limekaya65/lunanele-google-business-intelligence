"""Merchant Center product snapshot via the Merchant API (v1).

The Content API for Shopping (content v2.1) was sunset on 18 August 2026,
so this connector calls the Merchant API Products service instead.
"""
import os
from datetime import date

import google.auth
from google.auth.transport.requests import AuthorizedSession

SCOPES = ["https://www.googleapis.com/auth/content"]
PRODUCTS_URL = "https://merchantapi.googleapis.com/products/v1/accounts/{account_id}/products"
PLACEHOLDER_IDS = {"", "000000000"}


def _approval_status(product: dict) -> str:
    statuses = (product.get("productStatus") or {}).get("destinationStatuses") or []
    if any(s.get("disapprovedCountries") for s in statuses):
        return "disapproved"
    if any(s.get("pendingCountries") for s in statuses):
        return "pending"
    if any(s.get("approvedCountries") for s in statuses):
        return "approved"
    return "unknown"


def fetch_merchant_products(entity: dict) -> list[dict]:
    if not entity.get("ecommerce_enabled"):
        return []
    env_name = f"MERCHANT_CENTER_{entity['slug'].upper().replace('-', '_')}_ID"
    account_id = os.getenv(env_name, "").strip()
    if account_id in PLACEHOLDER_IDS:
        return []

    credentials, _ = google.auth.default(scopes=SCOPES)
    session = AuthorizedSession(credentials)
    url = PRODUCTS_URL.format(account_id=account_id)
    today = date.today().isoformat()

    rows, page_token = [], None
    while True:
        params = {"pageSize": 1000}
        if page_token:
            params["pageToken"] = page_token
        resp = session.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        for p in data.get("products", []):
            attrs = p.get("productAttributes") or p.get("attributes") or {}
            rows.append({
                "snapshot_date": today,
                "entity_slug": entity["slug"],
                "offer_id": p.get("offerId", ""),
                "title": attrs.get("title", ""),
                "availability": str(attrs.get("availability", "unknown")).lower(),
                "approval_status": _approval_status(p),
                # Clicks/impressions come from Merchant API Reports, not Products;
                # left NULL rather than writing fake zeros.
                "clicks": None,
                "impressions": None,
            })
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return rows
