import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest import mock
from fastapi.testclient import TestClient
import src.main as m
from src.connectors import merchant_center_client as mc

def test_health():
    r = TestClient(m.app).get("/health")
    assert r.status_code == 200
    assert r.json()["entities"] == ["holdings","agribusiness","capital","fx-trades","infrastructure","technology"]

def test_sync_isolates_failures():
    with mock.patch.object(m, "fetch_search_console_daily", side_effect=RuntimeError("403")), \
         mock.patch.object(m, "write_bq", return_value=0):
        m.connectors = None
        r = TestClient(m.app).post("/run-sync").json()
    # ga4/merchant skipped (no env), GSC failed for all 6 entities but request completed
    assert r["status"] == "completed_with_errors"
    assert len(r["summary"]["errors"]) == 2  # holdings + technology have Search Console on

def test_merchant_api_parsing():
    page = {"products":[{"offerId":"maize-50kg","productAttributes":{"title":"Maize 50kg","availability":"IN_STOCK"},
            "productStatus":{"destinationStatuses":[{"approvedCountries":["ZA"]}]}}]}
    sess = mock.Mock(); sess.get.return_value.json.return_value = page
    with mock.patch.dict(os.environ, {"MERCHANT_CENTER_AGRIBUSINESS_ID":"123"}), \
         mock.patch.object(mc.google.auth, "default", return_value=(object(), "p")), \
         mock.patch.object(mc, "AuthorizedSession", return_value=sess):
        rows = mc.fetch_merchant_products({"slug":"agribusiness","ecommerce_enabled":True})
    assert rows[0]["approval_status"] == "approved" and rows[0]["availability"] == "in_stock"
    assert "merchantapi.googleapis.com/products/v1/accounts/123/products" in sess.get.call_args[0][0]
