import generate_map


def _geo(fixture):
    def fn(clean, city, state):
        return fixture.get((clean, city.upper()))
    return fn


def _meta(city, lat, lng):
    return ("Test County", "Test Township")


def test_build_pins_attaches_state_and_unit_and_destacks():
    records = [
        {"address": "500 N Coldwater St / 19", "city": "FREMONT", "row_num": 2},
        {"address": "500 N Coldwater St / 22", "city": "FREMONT", "row_num": 3},
        {"address": "999 Nowhere Rd", "city": "GOSHEN", "row_num": 4},
    ]
    fixture = {
        # both units share the base -> same coordinate before destack
        ("500 N Coldwater St", "FREMONT"): {"lat": 41.7308, "lng": -84.9375},
    }
    pins, unplaced = generate_map.build_pins(
        records, _geo(fixture), lambda c, la, ln: ("Steuben County", "Fremont Township"))

    assert len(pins) == 2
    assert {p["state"] for p in pins} == {"IN"}          # Fremont IN
    assert {p["unit"] for p in pins} == {"19", "22"}
    coords = {(round(p["lat"], 6), round(p["lng"], 6)) for p in pins}
    assert len(coords) == 2                               # destacked
    assert len(unplaced) == 1 and unplaced[0]["row_num"] == 4


def test_build_pins_skips_blank_rows():
    records = [{"address": "", "city": "GOSHEN", "row_num": 9}]
    pins, unplaced = generate_map.build_pins(records, _geo({}), _meta)
    assert pins == [] and unplaced == []


def test_generate_map_is_importable_without_config():
    # Reaching this line means `import generate_map` did not sys.exit / read config.
    assert hasattr(generate_map, "build_pins")
