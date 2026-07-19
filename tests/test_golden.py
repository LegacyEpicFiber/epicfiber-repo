import generate_map


def test_end_to_end_pins_and_html():
    records = [
        {"address": "146 N Clark St", "city": "ELKHART", "row_num": 2},
        {"address": "146 N Clark St", "city": "Elkhart", "row_num": 3},   # exact dup
        {"address": "500 N Coldwater St / 19", "city": "FREMONT", "row_num": 4},
        {"address": "500 N Coldwater St / 22", "city": "FREMONT", "row_num": 5},
        {"address": "1 Baroda Ave", "city": "BARODA", "row_num": 6},      # MI
        {"address": "999 Ghost Rd", "city": "GOSHEN", "row_num": 7},      # ungeocodable
    ]
    fixture = {
        ("146 N Clark St", "ELKHART"): {"lat": 41.68, "lng": -85.97},
        ("500 N Coldwater St", "FREMONT"): {"lat": 41.7308, "lng": -84.9375},
        ("1 Baroda Ave", "BARODA"): {"lat": 41.95, "lng": -86.49},
    }
    geo = lambda clean, city, state: fixture.get((clean, city.upper()))
    meta = lambda city, la, ln: ("X County", "Y Township")

    pins, unplaced = generate_map.build_pins(records, geo, meta)

    # dup collapsed, units kept, ghost unplaced
    assert len(pins) == 4
    assert len(unplaced) == 1 and unplaced[0]["row_num"] == 7
    clark = next(p for p in pins if p["address"] == "146 N Clark St")
    assert clark["extra_rows"] == [3]
    assert next(p for p in pins if p["city"] == "BARODA")["state"] == "MI"
    # units destacked to distinct coords
    fre = [p for p in pins if p["city"] == "FREMONT"]
    assert len({(round(p["lat"], 6), round(p["lng"], 6)) for p in fre}) == 2

    template = "{{TAB_NAME}}|{{ADDRESSES_JSON}}|{{UNPLACED_JSON}}"
    html = generate_map.generate_html("BURY / DWB", pins, unplaced, template)
    assert html.startswith("BURY / DWB|")
    assert '"state": "MI"' in html
