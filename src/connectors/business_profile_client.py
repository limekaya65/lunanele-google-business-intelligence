"""Google Business Profile daily performance (free Business Profile Performance API).

Business Profile does not accept service accounts as managers, so this connector
uses an OAuth refresh token for the Google account that manages the profiles:
GBP_OAUTH_CLIENT_ID, GBP_OAUTH_CLIENT_SECRET, GBP_OAUTH_REFRESH_TOKEN
(store them in Secret Manager and expose them to Cloud Run as env vars).
Each entity names the env var holding its location ID (digits only, from
the profile's "Business Profile ID").
"""
import os
from datetime import date, timedelta

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/business.manage"]
URL = "https://businessprofileperformance.googleapis.com/v1/locations/{loc}:fetchMultiDailyMetricsTimeSeries"
METRICS = {
    "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH": "impressions_search_desktop",
    "BUSINESS_IMPRESSIONS_MOBILE_SEARCH": "impressions_search_mobile",
    "BUSINESS_IMPRESSIONS_DESKTOP_MAPS": "impressions_maps_desktop",
    "BUSINESS_IMPRESSIONS_MOBILE_MAPS": "impressions_maps_mobile",
    "CALL_CLICKS": "call_clicks",
    "WEBSITE_CLICKS": "website_clicks",
    "BUSINESS_DIRECTION_REQUESTS": "direction_requests",
    "BUSINESS_CONVERSATIONS": "conversations",
}


def _session() -> AuthorizedSession | None:
    cid, secret, token = (os.getenv(k, "").strip() for k in
                          ("GBP_OAUTH_CLIENT_ID", "GBP_OAUTH_CLIENT_SECRET", "GBP_OAUTH_REFRESH_TOKEN"))
    if not (cid and secret and token):
        return None
    creds = Credentials(None, refresh_token=token, client_id=cid, client_secret=secret,
                        token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES)
    return AuthorizedSession(creds)


def fetch_business_profile_daily(entity: dict, target_date: str | None = None) -> list[dict]:
    loc = os.getenv(entity.get("business_profile_location_env", ""), "").strip()
    loc = loc.removeprefix("locations/")
    if not loc:
        return []
    session = _session()
    if session is None:
        return []
    # Business Profile data settles over a few days; take the day 3 days back.
    run = date.fromisoformat(target_date) if target_date else date.today() - timedelta(days=3)
    params = [("dailyMetrics", m) for m in METRICS] + [
        ("dailyRange.startDate.year", run.year), ("dailyRange.startDate.month", run.month), ("dailyRange.startDate.day", run.day),
        ("dailyRange.endDate.year", run.year), ("dailyRange.endDate.month", run.month), ("dailyRange.endDate.day", run.day),
    ]
    resp = session.get(URL.format(loc=loc), params=params, timeout=60)
    resp.raise_for_status()

    row = {"metric_date": run.isoformat(), "entity_slug": entity["slug"], "location_id": loc}
    row.update({col: 0 for col in METRICS.values()})
    for multi in resp.json().get("multiDailyMetricTimeSeries", []):
        for series in multi.get("dailyMetricTimeSeries", []):
            col = METRICS.get(series.get("dailyMetric"))
            if not col:
                continue
            for dv in (series.get("timeSeries") or {}).get("datedValues", []):
                row[col] += int(dv.get("value", 0) or 0)  # value is omitted when zero
    return [row]
