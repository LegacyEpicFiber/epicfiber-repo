from pathlib import Path

import generate_map

TEMPLATE = "X{{TAB_NAME}} A={{ADDRESSES_JSON}} U={{UNPLACED_JSON}}"


def test_generate_html_injects_both_payloads_escaped():
    pins = [{"address": "1 A St", "city": "GOSHEN", "state": "IN", "lat": 41.5, "lng": -85.8}]
    unplaced = [{"address": "2 B</script> St", "city": "GOSHEN", "row_num": 7}]
    html = generate_map.generate_html("BURY / DWB", pins, unplaced, TEMPLATE)
    assert "BURY / DWB" in html
    assert "</script>" not in html            # escaped in the unplaced payload
    assert '"row_num": 7' in html


def test_template_popup_renders_extra_rows():
    """The real map template's popup must surface merged duplicate rows (extra_rows)."""
    template = (Path(__file__).resolve().parent.parent / "src" / "map_template.html").read_text(encoding="utf-8")
    assert "extra_rows" in template
