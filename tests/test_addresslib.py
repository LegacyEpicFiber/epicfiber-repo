import addresslib


def test_state_for_michigan_city():
    assert addresslib.state_for("Baroda") == "MI"
    assert addresslib.state_for("  wyoming ") == "MI"  # case/space insensitive


def test_state_for_defaults_to_indiana():
    assert addresslib.state_for("Goshen") == "IN"
    assert addresslib.state_for("") == "IN"


def test_parse_unit_splits_slash_unit():
    assert addresslib.parse_unit("500 N Coldwater St / 19") == ("500 N Coldwater St", "19")


def test_parse_unit_splits_lot_and_apt():
    assert addresslib.parse_unit("415 N Elkhart St / Lot.63") == ("415 N Elkhart St", "Lot.63")
    assert addresslib.parse_unit("208 E Main St / Unit A") == ("208 E Main St", "Unit A")


def test_parse_unit_splits_hash_unit():
    assert addresslib.parse_unit("100 Main St # 4") == ("100 Main St", "4")


def test_parse_unit_preserves_fraction():
    assert addresslib.parse_unit("123 1/2 Main St") == ("123 1/2 Main St", None)


def test_parse_unit_no_unit():
    assert addresslib.parse_unit("100 Main St") == ("100 Main St", None)


def test_clean_address_normalizes_routes():
    assert addresslib.clean_address_for_geocoding("1234 IN-9") == "1234 Indiana Route 9"
    assert addresslib.clean_address_for_geocoding("55 US-6") == "55 US Route 6"
    assert addresslib.clean_address_for_geocoding("9 CO RD 28") == "9 County Road 28"


def test_destack_moves_colliding_pins_apart():
    pins = [
        {"address": "500 N Coldwater St / 19", "unit": "19", "lat": 41.7308, "lng": -84.9375},
        {"address": "500 N Coldwater St / 22", "unit": "22", "lat": 41.7308, "lng": -84.9375},
        {"address": "500 N Coldwater St / 23", "unit": "23", "lat": 41.7308, "lng": -84.9375},
    ]
    out = addresslib.destack(pins)
    coords = {(round(p["lat"], 6), round(p["lng"], 6)) for p in out}
    assert len(coords) == 3            # all three now distinct
    assert all(p["offset_applied"] for p in out)
    assert all(abs(p["lat"] - 41.7308) < 0.01 for p in out)


def test_destack_leaves_singletons_untouched():
    pins = [{"address": "1 A St", "unit": None, "lat": 41.5, "lng": -86.0}]
    out = addresslib.destack(pins)
    assert out[0]["lat"] == 41.5 and out[0]["lng"] == -86.0
    assert out[0]["offset_applied"] is False


def test_destack_is_deterministic():
    pins = [
        {"address": "B St", "unit": None, "lat": 41.0, "lng": -86.0},
        {"address": "A St", "unit": None, "lat": 41.0, "lng": -86.0},
    ]
    # destack preserves input order, but each address must land at the same
    # spot regardless of input order.
    r1 = {p["address"]: (round(p["lat"], 9), round(p["lng"], 9)) for p in addresslib.destack(pins)}
    r2 = {p["address"]: (round(p["lat"], 9), round(p["lng"], 9)) for p in addresslib.destack(list(reversed(pins)))}
    assert r1 == r2 and len(r1) == 2


def test_dedupe_collapses_exact_duplicates():
    pins = [
        {"address": "146 N Clark St", "city": "ELKHART", "row_num": 5, "lat": 41.1, "lng": -85.9},
        {"address": "146 N Clark St", "city": "Elkhart", "row_num": 88, "lat": 41.1, "lng": -85.9},
    ]
    out = addresslib.dedupe(pins)
    assert len(out) == 1
    assert out[0]["row_num"] == 5
    assert out[0]["extra_rows"] == [88]


def test_dedupe_keeps_distinct_units():
    pins = [
        {"address": "500 N Coldwater St / 19", "city": "FREMONT", "row_num": 1, "lat": 41.7, "lng": -84.9},
        {"address": "500 N Coldwater St / 22", "city": "FREMONT", "row_num": 2, "lat": 41.7, "lng": -84.9},
    ]
    out = addresslib.dedupe(pins)
    assert len(out) == 2
    assert "extra_rows" not in out[0]


def test_escape_json_for_html_blocks_script_breakout():
    s = '{"a": "</script>&<b>"}'
    out = addresslib.escape_json_for_html(s)
    assert "</script>" not in out
    assert "<" not in out and ">" not in out and "&" not in out


def test_escape_json_for_html_escapes_line_separators():
    s = "line" + chr(0x2028) + "sep" + chr(0x2029) + "end"
    out = addresslib.escape_json_for_html(s)
    assert chr(0x2028) not in out and chr(0x2029) not in out
    assert "\\u2028" in out and "\\u2029" in out


def test_parse_census_geographies_extracts_county_township():
    data = {"result": {"geographies": {
        "Counties": [{"NAME": "Elkhart"}],
        "County Subdivisions": [{"NAME": "goshen township"}],
    }}}
    assert addresslib.parse_census_geographies(data) == ("Elkhart County", "Goshen Township")


def test_parse_census_geographies_handles_missing():
    assert addresslib.parse_census_geographies({}) == ("", "")
    assert addresslib.parse_census_geographies({"result": {"geographies": {}}}) == ("", "")
