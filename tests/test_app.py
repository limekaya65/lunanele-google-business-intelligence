from unittest import mock
import pytest
from fastapi.testclient import TestClient
import src.main as m
from src import config, storage, retry

client = TestClient(m.app)

def test_health_lists_entities_and_connectors():
    r = client.get("/health").json()
    assert r["entities"] == ["holdings", "agribusiness", "capital", "fx-trades", "infrastructure", "technology"]
    assert r["connectors_enabled"]["fx-trades"] == []

def _patched(fail_on=None):
    def fake(entity, *a):
        if fail_on and entity["slug"] == fail_on:
            raise RuntimeError("403 no access")
        return [{"entity_slug": entity["slug"], "event_date": "2026-11-20"}]
    return {k: (fake, d) for k, (_, d) in m.CONNECTORS.items()}

def test_one_entity_failing_does_not_stop_the_rest():
    with mock.patch.dict(m.CONNECTORS, _patched(fail_on="technology")), \
         mock.patch.object(storage, "replace_rows", side_effect=lambda n, rows: len(rows)), \
         mock.patch.object(storage, "record_run") as rec:
        r = client.post("/run-sync").json()
    assert r["status"] == "completed_with_errors"
    assert {e["entity"] for e in r["summary"]["errors"]} == {"technology"}
    assert r["summary"]["ga4_rows"] > 0
    rec.assert_called_once()

def test_dated_run_skips_snapshots():
    calls = []
    with mock.patch.dict(m.CONNECTORS, {k: ((lambda e, *a, k=k: calls.append(k) or []), d) for k, (_, d) in m.CONNECTORS.items()}), \
         mock.patch.object(storage, "replace_rows", return_value=0), mock.patch.object(storage, "record_run"):
        assert client.post("/run-sync?date=2026-11-01").status_code == 200
    assert "merchant_center" not in calls and "ga4" in calls

def test_date_validation_and_backfill_limit():
    assert client.post("/run-sync?date=2099-01-01").status_code == 422
    assert client.post("/run-sync?date=bad").status_code == 422
    assert client.post("/backfill?start=2026-01-01&end=2026-03-01").status_code == 422

def test_replace_rows_deletes_slice_then_loads():
    bq = mock.Mock()
    with mock.patch.dict("os.environ", {"GCP_PROJECT_ID": "p"}), mock.patch.object(storage, "_client", return_value=bq):
        n = storage.replace_rows("ga4", [{"event_date": "2026-11-20", "entity_slug": "holdings"},
                                         {"event_date": "2026-11-20", "entity_slug": "technology"}])
    assert n == 2
    sql = bq.query.call_args[0][0]
    assert sql.startswith("DELETE FROM `p.lunanele_bi_raw.ga4_daily_metrics`") and "entity_slug IN UNNEST(@slugs)" in sql
    bq.load_table_from_json.assert_called_once()
    assert not hasattr(bq.insert_rows_json, "assert_called") or not bq.insert_rows_json.called

def test_retry_transient_then_succeed_and_fail_fast_on_permanent():
    class E(Exception):
        def __init__(s, code): s.code = code
    calls = {"n": 0}
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3: raise E(503)
        return "ok"
    with mock.patch.object(retry.time, "sleep"):
        assert retry.with_retry(flaky) == "ok" and calls["n"] == 3
        calls["n"] = 0
        def denied(): calls["n"] += 1; raise E(403)
        with pytest.raises(E): retry.with_retry(denied)
        assert calls["n"] == 1

def test_config_rejects_typos(tmp_path):
    bad = tmp_path / "x.yaml"
    bad.write_text("entity:\n  name: X\n  slug: x\n  entity_type: subsidiary\n  conectors: {}\n")
    with pytest.raises(Exception):
        config._read(bad)
