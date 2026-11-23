import glob, os
from datetime import date
import httpx, yaml
from fastapi import FastAPI
from google.cloud import bigquery
from src.connectors.ga4_client import fetch_ga4_daily
from src.connectors.search_console_client import fetch_search_console_daily
from src.connectors.merchant_center_client import fetch_merchant_products

app = FastAPI(title="Lunanele Google BI & Customer Acquisition")

def load_entities() -> list[dict]:
    entities = [yaml.safe_load(open("config/holdings.yaml", encoding="utf-8"))["entity"]]
    for p in sorted(glob.glob("config/subsidiaries/*.yaml")):
        entities.append(yaml.safe_load(open(p, encoding="utf-8"))["entity"])
    return entities

def write_bq(table_id: str, rows: list[dict]) -> int:
    project = os.getenv("GCP_PROJECT_ID")
    if not rows or not project:
        return 0
    errors = bigquery.Client(project=project).insert_rows_json(f"{project}.{table_id}", rows)
    if errors:
        raise RuntimeError(f"BigQuery error: {errors}")
    return len(rows)

@app.get("/health")
def health():
    return {"status": "healthy", "holding": "Lunanele Holdings (Pty) Ltd", "entities": [e["slug"] for e in load_entities()]}

@app.post("/run-sync")
async def run_sync():
    prefix = os.getenv("BQ_DATASET_PREFIX", "lunanele_bi")
    entities = load_entities()
    ga4_all, gsc_all, mc_all = [], [], []
    for ent in entities:
        if ent["connectors"].get("ga4"): ga4_all.extend(fetch_ga4_daily(ent))
        if ent["connectors"].get("search_console"): gsc_all.extend(fetch_search_console_daily(ent))
        if ent["connectors"].get("merchant_center"): mc_all.extend(fetch_merchant_products(ent))

    summary = {
        "source": "lunanele-google-bi",
        "sync_date": date.today().isoformat(),
        "ga4_rows": write_bq(f"{prefix}_raw.ga4_daily_metrics", ga4_all),
        "gsc_rows": write_bq(f"{prefix}_raw.search_console_daily", gsc_all),
        "mc_rows": write_bq(f"{prefix}_raw.merchant_center_products", mc_all),
    }
    url, token = os.getenv("LUNACORE_WEBHOOK_URL", ""), os.getenv("LUNACORE_API_KEY", "")
    if url and token:
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(url, json=summary, headers={"Authorization": f"Bearer {token}"})
    return {"status": "completed", "summary": summary}
