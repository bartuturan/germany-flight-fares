import json
from datetime import date

from tools import wizzair_probe as probe

TODAY = date(2026, 11, 10)
HOMEPAGE = (
    '<script>window.__CONFIG={envName:"production",apiTimeout:0,'
    'apiUrl:"https://be.wizzair.com/29.24.0/Api",marathonApiUrl:"https://x.example/api"}</script>'
)
ACCESS_DENIED = "<HTML><HEAD><TITLE>Access Denied</TITLE></HEAD><BODY>Access Denied</BODY></HTML>"


def test_extract_api_url_reads_the_versioned_base():
    assert probe.extract_api_url(HOMEPAGE) == "https://be.wizzair.com/29.24.0/Api"


def test_extract_api_url_ignores_the_staging_url_and_missing_config():
    assert probe.extract_api_url('marathonApiUrl:"https://wizz09-api.staging7.mito.hu/api"') is None
    assert probe.extract_api_url("") is None
    assert probe.extract_api_url(None) is None


def test_classify_good_timetable_is_ok():
    body = json.dumps({"outboundFlights": [], "returnFlights": []})
    assert probe.classify(200, body, "outboundFlights") == probe.OK


def test_classify_json_without_the_expected_key_is_our_mistake():
    assert probe.classify(200, json.dumps({"other": 1}), "outboundFlights") == probe.INVALID


def test_classify_validation_error_is_invalid_not_blocked():
    body = json.dumps({"validationCodes": ["InvalidTimeDateRange"]})
    assert probe.classify(400, body, "outboundFlights") == probe.INVALID


def test_classify_blocks():
    assert probe.classify(405, "<html>Method Not Allowed</html>", "outboundFlights") == probe.BLOCKED
    assert probe.classify(403, "", "outboundFlights") == probe.BLOCKED
    assert probe.classify(429, "{}", "outboundFlights") == probe.BLOCKED
    assert probe.classify(200, "<html>Please wait</html>", "outboundFlights") == probe.BLOCKED
    assert probe.classify(200, ACCESS_DENIED, "outboundFlights") == probe.BLOCKED


def test_classify_server_errors_and_no_response_are_errors():
    assert probe.classify(502, "Bad gateway", "outboundFlights") == probe.ERROR
    assert probe.classify(None, "", "outboundFlights") == probe.ERROR


def test_date_windows_cover_45_days_in_two_windows_the_timetable_accepts():
    first, second = probe.date_windows(TODAY)
    assert first[0] == date(2026, 11, 11)
    assert second[1] == date(2026, 12, 25)
    assert (second[0] - first[1]).days == 1
    assert all((end - start).days <= 38 for start, end in (first, second))


MAP = {
    "cities": [
        {"iata": "BER", "countryCode": "DE", "connections": [{"iata": "BUD"}, {"iata": "KTW"}]},
        {"iata": "BUD", "countryCode": "HU", "connections": [{"iata": "BER"}]},
        {"iata": "DTM", "countryCode": "DE", "connections": [{"iata": "KTW"}, {"iata": "SOF"}]},
        {"iata": "HAM", "countryCode": "DE", "connections": [{"iata": "VIE"}]},
    ]
}


def test_german_routes_only_lists_departures_from_germany():
    assert probe.german_routes(MAP) == [
        ("BER", "BUD"), ("BER", "KTW"), ("DTM", "KTW"), ("DTM", "SOF"), ("HAM", "VIE"),
    ]


def test_spread_sample_takes_one_route_per_station_before_a_second():
    routes = probe.german_routes(MAP)
    assert probe.spread_sample(routes, count=3) == [("BER", "BUD"), ("DTM", "KTW"), ("HAM", "VIE")]
    assert probe.spread_sample(routes, count=4) == [
        ("BER", "BUD"), ("DTM", "KTW"), ("HAM", "VIE"), ("BER", "KTW"),
    ]
    assert len(probe.spread_sample(routes, count=99)) == 5


def test_blocked_share_counts_only_honest_timetable_calls():
    rows = [
        {"step": "timetable", "ua": "honest", "result": probe.OK},
        {"step": "timetable", "ua": "honest", "result": probe.BLOCKED},
        {"step": "timetable", "ua": "browser", "result": probe.OK},
        {"step": "homepage", "ua": "honest", "result": probe.BLOCKED},
    ]
    assert probe.blocked_share(rows) == 0.5
    assert probe.blocked_share([]) == 1.0
