"""BigQuery writes: idempotent, free-tier friendly, with a run audit trail."""
import os
from collections import defaultdict

from google.cloud import bigquery

# table name -> partition/date column used for idempotent replace
TABLES = {
    "ga4": ("ga4_daily_metrics", "event_date"),
    "search_console": ("search_console_daily", "query_date"),
    "merchant_center": ("merchant_center_products", "snapshot_date"),
    "business_profile": ("business_profile_daily", "metric_date"),
}


def project_id() -> str:
    return os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT", "")


def dataset(kind: str = "raw") -> str:
    return f"{os.getenv('BQ_DATASET_PREFIX', 'lunanele_bi')}_{kind}"


def _client() -> bigquery.Client:
    return bigquery.Client(project=project_id())


def replace_rows(connector: str, rows: list[dict]) -> int:
    """Replace the (date, entity) slices present in `rows`, then load them.

    Re-running a day therefore never double-counts, and an entity that failed
    this run keeps whatever data it already had. Load jobs are free; streaming
    inserts are billed, so they are not used.
    """
    if not rows or not project_id():
        return 0
    table, date_col = TABLES[connector]
    table_id = f"{project_id()}.{dataset()}.{table}"
    client = _client()

    slices: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        slices[str(r[date_col])].add(r["entity_slug"])
    for day, slugs in slices.items():
        client.query(
            f"DELETE FROM `{table_id}` WHERE {date_col} = @day AND entity_slug IN UNNEST(@slugs)",
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("day", "DATE", day),
                bigquery.ArrayQueryParameter("slugs", "STRING", sorted(slugs)),
            ]),
        ).result()

    client.load_table_from_json(
        rows, table_id,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND", ignore_unknown_values=True),
    ).result()
    return len(rows)


def record_run(run: dict) -> None:
    """Append one row to sync_runs: the audit trail of every sync."""
    if not project_id():
        return
    _client().load_table_from_json(
        [run], f"{project_id()}.{dataset()}.sync_runs",
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND", ignore_unknown_values=True),
    ).result()
