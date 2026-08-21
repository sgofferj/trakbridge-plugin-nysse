from plugin.nysse import NyssePlugin, COT_TYPE_BUS, NYSSE_API_URL


def make_plugin(line_filter: str = "") -> NyssePlugin:
    plugin = NyssePlugin({"nysse_line_filter": line_filter})
    return plugin


def test_matches_filter_empty_shows_all():
    plugin = make_plugin("")
    assert plugin._matches_filter("60", "") is True
    assert plugin._matches_filter("999", "") is True


def test_matches_filter_exact():
    plugin = make_plugin("60,64")
    assert plugin._matches_filter("60", "60,64") is True
    assert plugin._matches_filter("64", "60,64") is True
    assert plugin._matches_filter("61", "60,64") is False


def test_matches_filter_wildcard():
    plugin = make_plugin("6*")
    assert plugin._matches_filter("60", "6*") is True
    assert plugin._matches_filter("64", "6*") is True
    assert plugin._matches_filter("3A", "6*") is False


def test_cot_type_and_api_url():
    assert COT_TYPE_BUS == "a-f-G-E-V-C-M-H"
    assert NYSSE_API_URL == "https://data.itsfactory.fi/journeys/api/1"


def test_process_vehicle_filtered_out():
    import asyncio

    plugin = make_plugin("60")
    mvj = {
        "vehicleRef": "1234",
        "lineRef": "3A",
        "vehicleLocation": {"latitude": 61.4978, "longitude": 23.761},
        "speed": 10.0,
        "bearing": 90.0,
    }
    session = None  # not used when filtered out
    result = asyncio.run(plugin._process_vehicle(session, mvj, "60"))  # type: ignore[arg-type]
    assert result is None


def test_process_vehicle_location():
    import asyncio

    plugin = make_plugin("60")
    mvj = {
        "vehicleRef": "1234",
        "lineRef": "60",
        "vehicleLocation": {"latitude": 61.4978, "longitude": 23.761},
        "speed": 36.0,
        "bearing": 90.0,
    }
    session = None  # no onward calls / destination -> no stop lookups
    result = asyncio.run(plugin._process_vehicle(session, mvj, "60"))  # type: ignore[arg-type]
    assert result is not None
    assert result["uid"] == "nysse-1234"
    assert result["name"] == "NYSSE 60"
    assert result["lat"] == 61.4978
    assert result["lon"] == 23.761
    assert result["speed"] == 10.0
    assert result["course"] == 90.0
    assert result["cot_type"] == "a-f-G-E-V-C-M-H"
    assert "#NYSSE" in result["description"]
