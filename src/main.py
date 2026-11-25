import glob
import logging
import os
from datetime import date
from pathlib import Path

import httpx
import yaml
from fastapi import FastAPI
from google.cloud import bigquery

from src.connectors.ga4_client import fetch_ga4_daily
from src.connectors.merchant_center_client import fetch_merchant_products
from src.connectors.search_console_client import fetch_search_console_daily

logger = logging.getLogger("lunanele-google-bi")
logging.basicConfig(level=logging.INFO)

# Resolve config relative to the repo root so the app works from any working directory.
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"

app = FastAPI(title="Lunanele Google BI & Customer Acquisition")


def _read_yaml(path: Path | str) -> dict:
    # utf-8-sig tolerates a byte-order mark if a file is ever re-saved from Windows.
    with open(path, encoding="utf-8-sig") as fh:
        return yaml.safe_load(fh)["entity"]


def load_entities() -> list[dict]:
    entities = [_read_yaml(CONFIG_DIR / "holdings.yaml")]
    for p in sorted(glob.glob(str(CONFIG_DIR / "subsidiaries" / "*.yaml"))):
        entities.append(_read_yaml(p))
    return entities


def _project_id() -> str:
    return os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT", "")


def write_bq(table_id: str, rows: list[dict]) -> int:
    project = _project_id()
    if not rows or not project:
        return 0
    errors = bigquery.Client(project=project).insert_rows_json(f"{project}.{table_id}", rows)
    if errors:
        raise RuntimeError(f"BigQuery insert error on {table_id}: {errors[:5]}")
    return len(rows)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "holding": "Lunanele Holdings (Pty) Ltd",
        "entities": [e["slug"] for e in load_entities()],
    }


@app.post("/run-sync")
def run_sync():
    """Pull yesterday's Google data for every entity and load it into BigQuery.

    A failure in one entity/connector is logged and reported, but does not stop
    the rest of the group from syncing.
    """
    prefix = os.getenv("BQ_DATASET_PREFIX", "lunanele_bi")
    connectors = [
        ("ga4", fetch_ga4_daily),
        ("search_console", fetch_search_console_daily),
        ("merchant_center", fetch_merchant_products),
    ]
    collected: dict[str, list[dict]] = {name: [] for name, _ in connectors}
    errors: list[dict] = []

    for ent in load_entities():
        enabled = ent.get("connectors") or {}
        for name, fetch in connectors:
            if not enabled.get(name):
                continue
            try:
                collected[name].extend(fetch(ent))
            except Exception as exc:  # keep syncing the other entities
                logger.exception("%s sync failed for %s", name, ent.get("slug"))
                errors.append({"entity": ent.get("slug"), "connector": name, "error": str(exc)})

    targets = {
        "ga4": ("ga4_rows", f"{prefix}_raw.ga4_daily_metrics"),
        "search_console": ("gsc_rows", f"{prefix}_raw.search_console_daily"),
        "merchant_center": ("mc_rows", f"{prefix}_raw.merchant_center_products"),
    }
    summary: dict = {"source": "lunanele-google-bi", "sync_date": date.today().isoformat()}
    for name, (key, table) in targets.items():
        try:
            summary[key] = write_bq(table, collected[name])
        except Exception as exc:
            logger.exception("BigQuery write failed for %s", table)
            summary[key] = 0
            errors.append({"entity": "*", "connector": f"bigquery:{name}", "error": str(exc)})
    summary["errors"] = errors

    url, token = os.getenv("LUNACORE_WEBHOOK_URL", ""), os.getenv("LUNACORE_API_KEY", "")
    if url and token:
        try:
            httpx.post(url, json=summary, headers={"Authorization": f"Bearer {token}"}, timeout=20).raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("LunaCore webhook failed: %s", exc)
            errors.append({"entity": "*", "connector": "lunacore_webhook", "error": str(exc)})

    return {"status": "completed_with_errors" if errors else "completed", "summary": summary}
