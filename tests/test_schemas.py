"""The bootstrap SQL and the Terraform JSON schemas must describe the same tables."""
import json, re
from pathlib import Path

BQ = Path(__file__).resolve().parent.parent / "infrastructure" / "bigquery"

def _sql_tables():
    sql = (BQ / "datasets.sql").read_text()
    out = {}
    for m in re.finditer(r"CREATE TABLE IF NOT EXISTS `lunanele_bi_raw\.(\w+)` \((.*?)\n\)", sql, re.S):
        out[m.group(1)] = [l.strip().split()[0] for l in m.group(2).strip().splitlines()
                           if l.strip() and not l.strip().startswith("--")]
    return out

def test_sql_and_terraform_schemas_match():
    sql = _sql_tables()
    json_tables = {p.stem: [c["name"] for c in json.loads(p.read_text())] for p in (BQ / "schemas").glob("*.json")}
    assert sql == json_tables

def test_connector_rows_match_schema_columns():
    from src.connectors import ga4_client, search_console_client, business_profile_client
    cols = {p.stem: {c["name"] for c in json.loads(p.read_text())} for p in (BQ / "schemas").glob("*.json")}
    gbp_cols = {"metric_date", "entity_slug", "location_id", *business_profile_client.METRICS.values()}
    assert gbp_cols <= cols["business_profile_daily"]

def test_every_view_file_is_deployed_by_bootstrap():
    script = (BQ.parent.parent / "scripts" / "bootstrap_gcp.sh").read_text()
    for v in (BQ / "views").glob("*.sql"):
        assert v.stem in script, f"{v.stem} missing from bootstrap view list"
