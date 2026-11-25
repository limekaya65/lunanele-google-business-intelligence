import os
from unittest import mock
from src.connectors import business_profile_client as gbp, search_console_client as sc
from src.config import load_entities
from src import storage

def test_gbp_parses_and_sums():
    payload={"multiDailyMetricTimeSeries":[{"dailyMetricTimeSeries":[
        {"dailyMetric":"CALL_CLICKS","timeSeries":{"datedValues":[{"date":{},"value":"3"}]}},
        {"dailyMetric":"BUSINESS_IMPRESSIONS_MOBILE_MAPS","timeSeries":{"datedValues":[{"date":{}}]}},
        {"dailyMetric":"WEBSITE_CLICKS","timeSeries":{"datedValues":[{"date":{},"value":"7"}]}}]}]}
    sess=mock.Mock(); sess.get.return_value.json.return_value=payload
    env={"GBP_HOLDINGS_LOCATION_ID":"locations/123","GBP_OAUTH_CLIENT_ID":"a","GBP_OAUTH_CLIENT_SECRET":"b","GBP_OAUTH_REFRESH_TOKEN":"c"}
    with mock.patch.dict(os.environ,env), mock.patch.object(gbp,"AuthorizedSession",return_value=sess):
        rows=gbp.fetch_business_profile_daily({"slug":"holdings","business_profile_location_env":"GBP_HOLDINGS_LOCATION_ID"},"2026-11-20")
    r=rows[0]; assert (r["call_clicks"],r["website_clicks"],r["impressions_maps_mobile"],r["location_id"])==(3,7,0,"123")
    assert "locations/123:fetchMultiDailyMetricsTimeSeries" in sess.get.call_args[0][0]

def test_gbp_skips_without_credentials():
    with mock.patch.dict(os.environ,{"GBP_HOLDINGS_LOCATION_ID":"1"},clear=True):
        assert gbp.fetch_business_profile_daily({"slug":"holdings","business_profile_location_env":"GBP_HOLDINGS_LOCATION_ID"})==[]

def test_search_console_page_filter():
    svc=mock.MagicMock(); svc.searchanalytics().query().execute.return_value={"rows":[]}
    with mock.patch.object(sc,"build",return_value=svc), mock.patch.object(sc.google.auth,"default",return_value=(object(),"p")):
        ent=[e for e in load_entities() if e.slug=="technology"][0].as_dict()
        sc.fetch_search_console_daily(ent,"2026-11-20")
    body=svc.searchanalytics().query.call_args.kwargs["body"]
    assert body["dimensionFilterGroups"][0]["filters"][0]=={"dimension":"page","operator":"contains","expression":"tech.lunaneleholdings.com"}

