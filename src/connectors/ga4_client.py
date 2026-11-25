import os
from datetime import date, timedelta

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest

PLACEHOLDER_IDS = {"", "000000000"}


def fetch_ga4_daily(entity: dict, target_date: str | None = None) -> list[dict]:
    prop_id = os.getenv(entity.get("ga4_property_env", ""), "").strip()
    if prop_id in PLACEHOLDER_IDS:
        return []
    run_date = target_date or (date.today() - timedelta(days=1)).isoformat()
    client = BetaAnalyticsDataClient()
    req = RunReportRequest(
        property=f"properties/{prop_id}",
        dimensions=[Dimension(name="sessionSource"), Dimension(name="sessionMedium")],
        # GA4 renamed "conversions" to "keyEvents"; the old metric name is deprecated.
        metrics=[
            Metric(name="sessions"),
            Metric(name="activeUsers"),
            Metric(name="engagedSessions"),
            Metric(name="keyEvents"),
        ],
        date_ranges=[DateRange(start_date=run_date, end_date=run_date)],
        limit=10000,
    )
    resp = client.run_report(req)
    return [{
        "event_date": run_date,
        "entity_slug": entity["slug"],
        "entity_type": entity["entity_type"],
        "session_source": r.dimension_values[0].value,
        "session_medium": r.dimension_values[1].value,
        "sessions": int(r.metric_values[0].value or 0),
        "active_users": int(r.metric_values[1].value or 0),
        "engaged_sessions": int(r.metric_values[2].value or 0),
        # Column keeps its original name so existing BigQuery tables stay compatible.
        "conversions": int(float(r.metric_values[3].value or 0)),
    } for r in resp.rows]
