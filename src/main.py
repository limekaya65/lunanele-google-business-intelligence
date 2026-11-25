"""Lunanele Google BI & Customer Acquisition — Cloud Run service.

POST /run-sync                    daily sync (each source uses its own reporting lag)
POST /run-sync?date=YYYY-MM-DD    re-run one day for GA4 / Search Console / Business Profile
POST /backfill?start=...&end=...  re-run a date range (max 31 days per call)
GET  /health                      config check, no Google calls
"""
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import FastAPI, HTTPException, Query

from src import storage
from src.config import load_entities
from src.connectors.business_profile_client import fetch_business_profile_daily
from src.connectors.ga4_client import fetch_ga4_daily
from src.connectors.merchant_center_client import fetch_merchant_products
from src.connectors.search_console_client import fetch_search_console_daily
from src.logging_setup import configure
from src.retry import with_retry

logger = configure()
app = FastAPI(title="Lunanele Google BI & Customer Acquisition", version="2.0.0")

# connector name -> (fetch function, accepts a target date)
CONNECTORS = {
    "ga4": (fetch_ga4_daily, True),
    "search_console": (fetch_search_console_daily, True),
    "merchant_center": (fetch_merchant_products, False),
    "business_profile": (fetch_business_profile_daily, True),
}
MAX_WORKERS = int(os.getenv("SYNC_MAX_WORKERS", "6"))
MAX_BACKFILL_DAYS = 31


@app.get("/health")
def health():
    entities = load_entities()  # raises (500) if config is invalid
    return {
        "status": "healthy",
        "holding": "Lunanele Holdings (Pty) Ltd",
        "version": app.version,
        "entities": [e.slug for e in entities],
        "connectors_enabled": {e.slug: [k for k, v in e.connectors.model_dump().items() if v] for e in entities},
    }


def _fetch_one(run_id: str, entity: dict, name: str, target_date: str | None) -> list[dict]:
    fetch, dated = CONNECTORS[name]
    started = time.monotonic()
    args = (entity, target_date) if dated and target_date else (entity,)
    rows = with_retry(fetch, *args)
    logger.info("fetched", extra={"run_id": run_id, "entity": entity["slug"], "connector": name,
                                  "rows": len(rows), "duration_ms": int((time.monotonic() - started) * 1000)})
    return rows


def sync(target_date: str | None = None, include_snapshots: bool = True) -> dict:
    run_id = uuid.uuid4().hex[:12]
    started_at = datetime.now(timezone.utc)
    jobs = [
        (e.as_dict(), name)
        for e in load_entities()
        for name, (_, dated) in CONNECTORS.items()
        if getattr(e.connectors, name) and (dated or include_snapshots)
    ]
    collected: dict[str, list[dict]] = {name: [] for name in CONNECTORS}
    errors: list[dict] = []

    # Google calls are I/O-bound: run entity x connector pairs in parallel.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_one, run_id, ent, name, target_date): (ent["slug"], name) for ent, name in jobs}
        for fut, (slug, name) in futures.items():
            try:
                collected[name].extend(fut.result())
            except Exception as exc:  # one failure never stops the group
                logger.exception("fetch failed", extra={"run_id": run_id, "entity": slug, "connector": name})
                errors.append({"entity": slug, "connector": name, "error": str(exc)[:500]})

    written: dict[str, int] = {}
    for name, rows in collected.items():
        try:
            written[name] = storage.replace_rows(name, rows)
        except Exception as exc:
            logger.exception("bigquery write failed", extra={"run_id": run_id, "connector": name})
            written[name] = 0
            errors.append({"entity": "*", "connector": f"bigquery:{name}", "error": str(exc)[:500]})

    if not errors:
        status = "completed"
    elif sum(written.values()) == 0:
        status = "failed"
    else:
        status = "completed_with_errors"
    summary = {
        "run_id": run_id,
        "source": "lunanele-google-bi",
        "sync_date": date.today().isoformat(),
        "target_date": target_date,
        "status": status,
        "ga4_rows": written["ga4"],
        "gsc_rows": written["search_console"],
        "mc_rows": written["merchant_center"],
        "gbp_rows": written["business_profile"],
        "errors": errors,
    }

    _notify_lunacore(summary)
    try:
        storage.record_run({
            "run_id": run_id, "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(), "status": summary["status"],
            "target_date": target_date, "rows_written": sum(written.values()),
            "error_count": len(errors), "errors_json": str(errors)[:10000],
        })
    except Exception:
        logger.exception("could not record run", extra={"run_id": run_id})

    log = logger.error if status == "failed" else logger.info
    log("sync finished: %s", status, extra={"run_id": run_id, "rows": sum(written.values())})
    return summary


def _notify_lunacore(summary: dict) -> None:
    url, token = os.getenv("LUNACORE_WEBHOOK_URL", ""), os.getenv("LUNACORE_API_KEY", "")
    if not (url and token):
        return
    try:
        httpx.post(url, json=summary, timeout=20, headers={
            "Authorization": f"Bearer {token}", "Idempotency-Key": summary["run_id"]}).raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("LunaCore webhook failed: %s", exc)
        summary["errors"].append({"entity": "*", "connector": "lunacore_webhook", "error": str(exc)[:500]})


def _parse_date(value: str, field: str) -> date:
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, f"{field} must be YYYY-MM-DD")
    if d >= date.today():
        raise HTTPException(422, f"{field} must be in the past")
    return d


@app.post("/run-sync")
def run_sync(date_: str | None = Query(None, alias="date")):
    target = _parse_date(date_, "date").isoformat() if date_ else None
    # Product snapshots are "as of now", so they are only taken on the normal daily run.
    summary = sync(target, include_snapshots=target is None)
    return {"status": summary["status"], "summary": summary}


@app.post("/backfill")
def backfill(start: str, end: str):
    s, e = _parse_date(start, "start"), _parse_date(end, "end")
    if e < s:
        raise HTTPException(422, "end must be on or after start")
    if (e - s).days + 1 > MAX_BACKFILL_DAYS:
        raise HTTPException(422, f"at most {MAX_BACKFILL_DAYS} days per call")
    days, d = [], s
    while d <= e:
        r = sync(d.isoformat(), include_snapshots=False)
        days.append({"date": d.isoformat(), "status": r["status"], "run_id": r["run_id"]})
        d += timedelta(days=1)
    return {"status": "completed", "days": days}
