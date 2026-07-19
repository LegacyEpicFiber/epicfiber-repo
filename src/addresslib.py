"""Pure address/geocoding helpers for the EpicFiber map generator.

No I/O, no config, no network — safe to import and unit-test in isolation.
"""
import math
import re

# Cities in Michigan — everything else in the service area defaults to Indiana.
MICHIGAN_CITIES = frozenset({
    "BARODA", "BRIDGMAN", "BYRON CENTER", "CASSOPOLIS", "CORUNNA", "DECATUR",
    "DOWAGIAC", "FENNVILLE", "GRAND HAVEN", "MOLINE", "PLAINWELL", "SAWYER",
    "VICKSBURG", "WATERVLIET", "WAYLAND", "WYOMING",
})


def state_for(city, michigan_cities=MICHIGAN_CITIES):
    """Return 'MI' if the city is in the Michigan set, else 'IN'."""
    return "MI" if city.upper().strip() in michigan_cities else "IN"


# A trailing unit/lot is split off the base (what gets geocoded); the full
# string stays as the display address. A whitespace-delimited '/' is required,
# so fractions like "123 1/2 MAIN ST" (no space before '/') are preserved.
_SLASH_UNIT_RE = re.compile(r"\s+/\s*(.+?)\s*$")
_HASH_UNIT_RE = re.compile(r"\s+#\s*([\w.\-]+)\s*$")


def parse_unit(address):
    """Split a trailing unit/lot designator off the address.

    Returns (base_address, unit_or_None). A space-delimited '/ ...' (or a
    trailing '# ...') is the unit; fractions ("1/2") are preserved.
    """
    address = address.strip()
    for rx in (_SLASH_UNIT_RE, _HASH_UNIT_RE):
        m = rx.search(address)
        if m:
            return address[:m.start()].strip(), m.group(1).strip()
    return address, None


def clean_address_for_geocoding(base):
    """Normalize route abbreviations so the geocoder matches rural routes.

    Does NOT strip units (see parse_unit) and does NOT touch fractions.
    """
    out = re.sub(r"\bIN-(\d+)\b", r"Indiana Route \1", base, flags=re.IGNORECASE)
    out = re.sub(r"\bUS-(\d+)\b", r"US Route \1", out, flags=re.IGNORECASE)
    out = re.sub(r"\bCO\.?\s*R(?:OA)?D\.?\b", "County Road", out, flags=re.IGNORECASE)
    return out.strip()


def destack(pins, radius_m=20.0, precision=4):
    """Fan out pins that share a rounded coordinate so they don't stack.

    Deterministic: within a colliding group, pins are ordered by
    (address, unit) and placed evenly on a circle of radius_m meters.
    Returns a new list; input is not mutated.
    """
    from collections import defaultdict

    out = [dict(p) for p in pins]
    for p in out:
        p["offset_applied"] = False

    groups = defaultdict(list)
    for i, p in enumerate(out):
        groups[(round(p["lat"], precision), round(p["lng"], precision))].append(i)

    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        idxs.sort(key=lambda i: (out[i]["address"].upper(), out[i].get("unit") or ""))
        n = len(idxs)
        for j, i in enumerate(idxs):
            angle = 2 * math.pi * j / n
            lat = out[i]["lat"]
            dlat = (radius_m / 111_320.0) * math.cos(angle)
            dlng = (radius_m / (111_320.0 * math.cos(math.radians(lat)))) * math.sin(angle)
            out[i]["lat"] = lat + dlat
            out[i]["lng"] = out[i]["lng"] + dlng
            out[i]["offset_applied"] = True
    return out


def dedupe(pins):
    """Collapse exact (address, city) duplicates, preserving first-seen order.

    The kept pin records other rows' numbers in 'extra_rows'. Distinct units
    (different display address) are NOT merged.
    """
    kept = {}
    order = []
    for p in pins:
        key = (p["address"].upper().strip(), p["city"].upper().strip())
        if key in kept:
            other = p.get("row_num")
            if other is not None:
                kept[key].setdefault("extra_rows", []).append(other)
        else:
            kept[key] = dict(p)
            order.append(key)
    return [kept[k] for k in order]


def escape_json_for_html(json_str):
    """Escape a JSON string for safe embedding inside an HTML <script> block.

    Prevents </script> breakout and the U+2028/U+2029 line/paragraph
    separators that are invalid raw in JS string literals. chr(0x2028/9)
    is used rather than a raw literal to keep this source ASCII-clean.
    """
    return (json_str
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace(chr(0x2028), "\\u2028")
            .replace(chr(0x2029), "\\u2029"))


def parse_census_geographies(data):
    """Parse a Census geographies/coordinates response into (county, township)."""
    geos = data.get("result", {}).get("geographies", {})
    counties = geos.get("Counties", [])
    subdivs = geos.get("County Subdivisions", [])
    county = counties[0]["NAME"].strip() if counties else ""
    township = subdivs[0]["NAME"].strip() if subdivs else ""
    if county and "County" not in county:
        county = f"{county} County"
    if township:
        township = township.title()
    return county, township
