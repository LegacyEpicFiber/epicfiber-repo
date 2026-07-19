#!/usr/bin/env python3
"""
Proximity Mesh Address Map — Sync Script
────────────────────────────────────────
Reads config.json, authenticates via Google service account, geocodes every
address from the configured Google Sheet tabs, writes self-contained Leaflet
HTML maps into docs/, writes a metadata.json summary, and optionally pushes
to GitHub Pages automatically.

FIRST-TIME SETUP
-----------------
  pip install -r requirements.txt
  cp config.template.json config.json   # then fill in your values

HOW TO RUN
-----------
  python3 src/generate_map.py

GitHub Pages URL (after first push):
  https://YOUR-ORG.github.io/epicfiber-maps/
"""

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import addresslib

# ── dependency check ──────────────────────────────────────────────────────────
try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    sys.exit(
        "\n❌  Missing dependencies. Run:\n"
        "      pip install -r requirements.txt\n"
        "   Then re-run the script.\n"
    )

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

REPO_ROOT   = Path(__file__).parent.parent   # epicfiber-maps/
CONFIG_FILE = REPO_ROOT / "config.json"

def load_config():
    if not CONFIG_FILE.exists():
        sys.exit(
            f"\n❌  config.json not found at {CONFIG_FILE}\n"
            "    Copy config.template.json → config.json and fill in your values.\n"
        )
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)

def load_settings():
    """Build the runtime settings from config.json + environment.

    Called only from main() — importing this module has no side effects, so
    the pure logic below can be unit-tested without a config file.
    """
    cfg = load_config()
    cache_dir = Path(cfg.get("cache_dir", str(REPO_ROOT / "cache"))).expanduser()
    return {
        "spreadsheet_id":       cfg["spreadsheet_id"],
        "service_acct":         Path(cfg["service_account_path"]).expanduser(),
        "output_dir":           Path(cfg["docs_dir"]).expanduser(),
        "cache_dir":            cache_dir,
        "cache_file":           cache_dir / "geocode_cache.json",
        "city_meta_cache_file": cache_dir / "city_meta_cache.json",
        "tabs":                 cfg.get("tabs", {}),
        "auto_push":            cfg.get("auto_push", False),
        "repo_path":            Path(cfg.get("repo_path", str(REPO_ROOT))).expanduser(),
        # env var takes precedence (GitHub Actions Secret); falls back to config.
        "google_key":           os.environ.get("GOOGLE_MAPS_API_KEY") or cfg.get("google_maps_api_key", ""),
    }

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

NOMINATIM_UA  = "LegacyEpicFiber-AddressMap/1.0 (legacy.buryandbore@gmail.com)"
GEOCODE_DELAY = 1.2   # seconds between Nominatim requests (respect rate limit)
TEMPLATE_FILE = Path(__file__).parent / "map_template.html"

# Detect GitHub Actions environment so we skip the local git-push step
# (Actions handles the commit/push itself via the workflow file).
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"

# City → (County, Township) for the service area (curated; authoritative)
CITY_META = {
    "ASHLEY":           ("DeKalb County",     "Ashley Township"),
    "BARODA":           ("Berrien County",     "Baroda Township"),
    "BOURBON":          ("Marshall County",    "Center Township"),
    "BREMEN":           ("Marshall County",    "Bremen Township"),
    "BRIDGMAN":         ("Berrien County",     "Weesaw Township"),
    "BRISTOL":          ("Elkhart County",     "Jefferson Township"),
    "BUTLER":           ("DeKalb County",      "Butler Township"),
    "BYRON CENTER":     ("Kent County",        "Byron Township"),
    "CASSOPOLIS":       ("Cass County",        "Cassopolis Township"),
    "CORUNNA":          ("Shiawassee County",  "Corunna Township"),
    "DECATUR":          ("Van Buren County",   "Decatur Township"),
    "DOWAGIAC":         ("Cass County",        "Pokagon Township"),
    "FENNVILLE":        ("Allegan County",     "Manlius Township"),
    "GRAND HAVEN":      ("Ottawa County",      "Grand Haven Township"),
    "MOLINE":           ("Allegan County",     "Wayland Township"),
    "WATERVLIET":       ("Berrien County",     "Watervliet Township"),
    "ORLAND":           ("Steuben County",     "Newbury Township"),
    "SAWYER":           ("Berrien County",     "Chikaming Township"),
    "SHIPSHEWANA":      ("LaGrange County",    "Emma Township"),
    "SOUTH WHITLEY":    ("Whitley County",     "Columbia Township"),
    "VICKSBURG":        ("Kalamazoo County",   "Brady Township"),
    "CHURUBUSCO":       ("Whitley County",     "Jackson Township"),
    "COLUMBIA CITY":    ("Whitley County",     "Columbia City"),
    "CULVER":           ("Marshall County",    "Culver Township"),
    "ELKHART":          ("Elkhart County",     "Elkhart Township"),
    "ETNA GREEN":       ("Kosciusko County",   "Wayne Township"),
    "GOSHEN":           ("Elkhart County",     "Goshen Township"),
    "GRANGER":          ("St. Joseph County",  "German Township"),
    "KENDALLVILLE":     ("Noble County",       "Kendallville Township"),
    "KNOX":             ("Starke County",      "Center Township"),
    "LAKEVILLE":        ("St. Joseph County",  "Penn Township"),
    "LAPAZ":            ("Marshall County",    "Green Township"),
    "LAPORTE":          ("LaPorte County",     "LaPorte Township"),
    "LIGONIER":         ("Noble County",       "Ligonier Township"),
    "LOGANSPORT":       ("Cass County",        "Clay Township"),
    "LYDICK":           ("St. Joseph County",  "German Township"),
    "MARION":           ("Grant County",       "Marion Township"),
    "MENTONE":          ("Kosciusko County",   "Tippecanoe Township"),
    "MICHIANA SHORES":  ("LaPorte County",     "Coolspring Township"),
    "MILLERSBURG":      ("Elkhart County",     "Cleveland Township"),
    "MISHAWAKA":        ("St. Joseph County",  "Mishawaka Township"),
    "NAPPANEE":         ("Elkhart County",     "Nappanee Township"),
    "NEW CARLISLE":     ("St. Joseph County",  "New Carlisle Township"),
    "NORTH LIBERTY":    ("St. Joseph County",  "Liberty Township"),
    "NOTRE DAME":       ("St. Joseph County",  "German Township"),
    "OSCEOLA":          ("St. Joseph County",  "Portage Township"),
    "PERU":             ("Miami County",       "Peru Township"),
    "PLAINWELL":        ("Allegan County",     "Plainwell Township"),
    "PLYMOUTH":         ("Marshall County",    "Plymouth Township"),
    "ROLLING PRAIRIE":  ("LaPorte County",     "Springfield Township"),
    "ROME CITY":        ("Noble County",       "Rome Township"),
    "ROSELAND":         ("St. Joseph County",  "German Township"),
    "SOUTH BEND":       ("St. Joseph County",  "South Bend Township"),
    "SYRACUSE":         ("Kosciusko County",   "Turkey Creek Township"),
    "TIPPECANOE":       ("Marshall County",    "Tippecanoe Township"),
    "TOPEKA":           ("LaGrange County",    "Newbury Township"),
    "WAKARUSA":         ("Elkhart County",     "Olive Township"),
    "WALKERTON":        ("St. Joseph County",  "Harris Township"),
    "WARSAW":           ("Kosciusko County",   "Wayne Township"),
    "WAYLAND":          ("Allegan County",     "Wayland Township"),
    "NORTH WEBSTER":    ("Kosciusko County",   "Wayne Township"),
    "WINAMAC":          ("Pulaski County",     "Beaver Township"),
    "WINONA LAKE":      ("Kosciusko County",   "Wayne Township"),
    "WOLCOTTVILLE":     ("LaGrange County",    "Wolcottville Township"),
    "WYOMING":          ("Kent County",        "Wyoming Township"),
}

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# ══════════════════════════════════════════════════════════════════════════════
#  GOOGLE SHEETS
# ══════════════════════════════════════════════════════════════════════════════

def open_spreadsheet(settings):
    service_acct = settings["service_acct"]
    if not service_acct.exists():
        sys.exit(
            f"\n❌  Service account key not found:\n      {service_acct}\n"
            "    Set the correct path in config.json → service_account_path.\n"
        )
    creds = Credentials.from_service_account_file(str(service_acct), scopes=SCOPES)
    gc    = gspread.authorize(creds)
    try:
        return gc.open_by_key(settings["spreadsheet_id"])
    except gspread.exceptions.APIError as e:
        if "403" in str(e):
            sys.exit(
                "\n❌  Permission denied (403).\n"
                "    Share the spreadsheet with the service account email\n"
                "    (Viewer access is enough), then re-run.\n"
            )
        raise

def _get_green_row_indices(creds, spreadsheet_id, sheet_name):
    """Return a set of 0-based data row indices (header excluded) where ANY cell
    has background colour #00ff00 (pure neon green = completed job)."""
    import google.auth.transport.requests
    try:
        session = google.auth.transport.requests.AuthorizedSession(creds)
        url  = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
        resp = session.get(url, params={
            "includeGridData": "true",
            "ranges":          sheet_name,
            "fields":          "sheets.data.rowData.values.userEnteredFormat.backgroundColor",
        }, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        green = set()
        row_data = (
            data.get("sheets", [{}])[0]
                .get("data",   [{}])[0]
                .get("rowData", [])
        )
        # rowData[0] = header row → skip; rowData[i+1] → data row index i
        for idx, row in enumerate(row_data[1:]):
            for cell in row.get("values", []):
                bg = cell.get("userEnteredFormat", {}).get("backgroundColor", {})
                r  = bg.get("red",   0.0)
                g  = bg.get("green", 0.0)
                b  = bg.get("blue",  0.0)
                # #00ff00 ≡ red≈0, green≈1, blue≈0
                if g >= 0.99 and r <= 0.01 and b <= 0.01:
                    green.add(idx)
                    break   # one green cell is enough to exclude the row
        return green
    except Exception as e:
        print(f"    ⚠  Could not read row colours (green filter skipped): {e}")
        return set()


def fetch_tab(spreadsheet, gid, spreadsheet_id):
    ws = spreadsheet.get_worksheet_by_id(int(gid))

    # Identify completed rows (neon green #00ff00) to exclude before geocoding
    green_indices = _get_green_row_indices(
        spreadsheet.client.auth, spreadsheet_id, ws.title
    )
    if green_indices:
        print(f"    Excluding {len(green_indices)} completed (green) row(s)")

    all_values = ws.get_all_values()
    if not all_values:
        return []
    raw_headers = all_values[0]
    headers = []
    seen = {}
    for h in raw_headers:
        key = h.strip()
        if key in seen:
            seen[key] += 1
            key = f"{key}_{seen[key]}"
        else:
            seen[key] = 1
        headers.append(key)
    rows = []
    for i, row in enumerate(all_values[1:]):
        if i in green_indices:
            continue          # skip completed jobs
        padded = row + [""] * (len(headers) - len(row))
        d = dict(zip(headers, padded))
        d["_row_num"] = i + 2  # spreadsheet row number (row 1 = header)
        rows.append(d)
    return rows

# ══════════════════════════════════════════════════════════════════════════════
#  GEOCODE CACHE
# ══════════════════════════════════════════════════════════════════════════════

def load_cache(cache_file):
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(cache, cache_file):
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")

def _geocode_google(clean_addr, city, state, api_key):
    """Primary geocoder — Google Maps Geocoding API.
    Much higher success rate than Census/Nominatim for rural routes,
    partial addresses, and non-standard formats."""
    query = urllib.parse.quote_plus(f"{clean_addr}, {city}, {state}, USA")
    url   = f"https://maps.googleapis.com/maps/api/geocode/json?address={query}&key={api_key}"
    req   = urllib.request.Request(url, headers={"User-Agent": NOMINATIM_UA})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        status = data.get("status")
        if status == "OK":
            loc = data["results"][0]["geometry"]["location"]
            return {"lat": loc["lat"], "lng": loc["lng"]}
        if status not in ("ZERO_RESULTS",):
            # Log unexpected statuses (REQUEST_DENIED, OVER_QUERY_LIMIT, etc.)
            print(f"    ℹ  Google geocoder status {status!r}: {clean_addr}, {city}")
    except Exception as e:
        if not getattr(_geocode_google, "_err_shown", False):
            print(f"    ℹ  Google geocoder unavailable ({e}), using fallbacks")
            _geocode_google._err_shown = True
    return None

def _geocode_census(clean_addr, city, state):
    params = urllib.parse.urlencode({
        "address":   f"{clean_addr}, {city}, {state}",
        "benchmark": "Public_AR_Current",
        "format":    "json",
    })
    url = f"http://geocoding.geo.census.gov/geocoder/locations/onelineaddress?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": NOMINATIM_UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        matches = data.get("result", {}).get("addressMatches", [])
        if matches:
            c = matches[0]["coordinates"]
            return {"lat": c["y"], "lng": c["x"]}
    except Exception as e:
        if not getattr(_geocode_census, "_err_shown", False):
            print(f"    ℹ  Census geocoder unavailable ({e}), using Nominatim only")
            _geocode_census._err_shown = True
    return None

def _geocode_nominatim(clean_addr, city, state):
    query = urllib.parse.quote_plus(f"{clean_addr}, {city}, {state}, USA")
    url   = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1"
    req   = urllib.request.Request(url, headers={"User-Agent": NOMINATIM_UA})
    time.sleep(GEOCODE_DELAY)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            results = json.loads(resp.read())
        if results:
            return {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])}
    except Exception:
        pass
    return None

def geocode_clean(clean_addr, city, state, google_key, cache):
    """Geocoder waterfall (Google → Census → Nominatim) on an ALREADY-CLEANED
    address. Cleaning happens upstream in build_pins via addresslib, so this
    receives the base address and only geocodes + caches it."""
    key = f"{clean_addr}|||{city}"
    if key in cache and cache[key] is not None:
        return cache[key]
    result = None
    if google_key:
        result = _geocode_google(clean_addr, city, state, google_key)
    if not result:
        result = _geocode_census(clean_addr, city, state)
    if not result:
        result = _geocode_nominatim(clean_addr, city, state)
    if not result:
        print(f"    ⚠  No geocode result: {clean_addr}, {city}")
    cache[key] = result
    return result

# ══════════════════════════════════════════════════════════════════════════════
#  CITY META  (county + township: curated table → coordinate reverse-lookup)
# ══════════════════════════════════════════════════════════════════════════════

def _load_city_meta_cache(city_meta_cache_file):
    if city_meta_cache_file.exists():
        try:
            with open(city_meta_cache_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_city_meta_cache(cache, city_meta_cache_file):
    city_meta_cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(city_meta_cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def _fetch_city_meta_coords(lat, lng):
    """Reverse-lookup county + township from coordinates via the Census
    geographies/coordinates endpoint (more reliable than forward-geocoding a
    dummy street per city)."""
    try:
        params = urllib.parse.urlencode({
            "x":         lng,
            "y":         lat,
            "benchmark": "Public_AR_Current",
            "vintage":   "Current_Current",
            "layers":    "Counties,County Subdivisions",
            "format":    "json",
        })
        url = f"https://geocoding.geo.census.gov/geocoder/geographies/coordinates?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": NOMINATIM_UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return addresslib.parse_census_geographies(data)
    except Exception as e:
        print(f"    ⚠  Census coord meta lookup failed for ({lat},{lng}): {e}")
        return ("", "")

def get_city_meta(city, lat, lng, city_meta_cache):
    """Return (county, township). Priority: curated CITY_META → coordinate
    reverse-lookup (cached by rounded coord)."""
    key = city.upper()
    if key in CITY_META:
        return CITY_META[key]
    coord_key = f"{round(lat, 4)},{round(lng, 4)}"
    if coord_key in city_meta_cache:
        entry = city_meta_cache[coord_key]
        return (entry[0], entry[1])
    result = _fetch_city_meta_coords(lat, lng)
    if result[0]:
        print(f"    ℹ  Census meta → {city}: {result[0]}, {result[1]}")
    city_meta_cache[coord_key] = list(result)
    return result

# ══════════════════════════════════════════════════════════════════════════════
#  BUILD PINS  (testable seam: inject geocode_fn / meta_fn)
# ══════════════════════════════════════════════════════════════════════════════

def build_pins(records, geocode_fn, meta_fn):
    """Transform normalized sheet records into (pins, unplaced).

    records: [{address, city, row_num}]
    geocode_fn(clean_addr, city, state) -> {"lat","lng"} | None
    meta_fn(city, lat, lng) -> (county, township)

    The pin's displayed `address` is the FULL original string; only the
    geocoder receives the stripped+cleaned base. Rows that fail geocoding go
    to `unplaced` rather than being silently dropped.
    """
    pins, unplaced = [], []
    for rec in records:
        address = str(rec.get("address", "")).strip()
        city    = str(rec.get("city", "")).strip()
        if not address or not city:
            continue
        state = addresslib.state_for(city)
        base, unit = addresslib.parse_unit(address)
        clean = addresslib.clean_address_for_geocoding(base)
        coord = geocode_fn(clean, city, state)
        if not coord:
            unplaced.append({"address": address, "city": city, "row_num": rec.get("row_num")})
            continue
        county, township = meta_fn(city, coord["lat"], coord["lng"])
        pins.append({
            "address":  address,
            "city":     city,
            "state":    state,
            "unit":     unit,
            "county":   county,
            "township": township,
            "lat":      coord["lat"],
            "lng":      coord["lng"],
            "maps_url": "https://maps.google.com/?q=" + urllib.parse.quote_plus(f"{address}, {city}"),
            "row_num":  rec.get("row_num"),
        })
    pins = addresslib.dedupe(pins)
    pins = addresslib.destack(pins)
    return pins, unplaced

# ══════════════════════════════════════════════════════════════════════════════
#  HTML GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_html(tab_name, pins, unplaced, template):
    pins_json     = addresslib.escape_json_for_html(json.dumps(pins, indent=2, ensure_ascii=False))
    unplaced_json = addresslib.escape_json_for_html(json.dumps(unplaced, indent=2, ensure_ascii=False))
    html = template.replace("{{TAB_NAME}}", tab_name)
    html = html.replace("{{ADDRESSES_JSON}}", pins_json)
    html = html.replace("{{UNPLACED_JSON}}", unplaced_json)
    return html

# ══════════════════════════════════════════════════════════════════════════════
#  METADATA
# ══════════════════════════════════════════════════════════════════════════════

def write_metadata(tab_counts, tab_unplaced, output_dir):
    meta = {
        "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "last_updated_display": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
        "tabs": tab_counts,
        "unplaced": tab_unplaced,
    }
    meta_file = output_dir / "metadata.json"
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("  ✅  Wrote metadata.json")

# ══════════════════════════════════════════════════════════════════════════════
#  GITHUB PUSH
# ══════════════════════════════════════════════════════════════════════════════

def push_to_github(repo_path):
    print("\n  Pushing to GitHub Pages…")
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        subprocess.run(
            ["git", "-C", str(repo_path), "add", "docs/"],
            check=True, capture_output=True
        )
        result = subprocess.run(
            ["git", "-C", str(repo_path), "commit", "-m", f"Auto-update maps {date_str}"],
            capture_output=True, text=True
        )
        if "nothing to commit" in result.stdout:
            print("  ℹ  No changes to push (maps unchanged).")
            return
        subprocess.run(
            ["git", "-C", str(repo_path), "push"],
            check=True, capture_output=True
        )
        print("  ✅  Maps pushed to GitHub Pages.")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠  GitHub push failed: {e.stderr.decode() if e.stderr else e}")
        print("      Maps were generated locally. Push manually with: git push")

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n═══════════════════════════════════════")
    print("  Proximity Mesh Address Map — Sync")
    print("═══════════════════════════════════════\n")

    settings = load_settings()
    settings["output_dir"].mkdir(parents=True, exist_ok=True)
    settings["cache_dir"].mkdir(parents=True, exist_ok=True)

    if not TEMPLATE_FILE.exists():
        sys.exit(
            f"\n❌  Template not found:\n      {TEMPLATE_FILE}\n"
            "    map_template.html must be in src/ alongside this script.\n"
        )

    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    cache    = load_cache(settings["cache_file"])
    print(f"  Geocode cache: {len(cache)} entries loaded")

    print("  Connecting to Google Sheets…")
    spreadsheet = open_spreadsheet(settings)
    print(f"  Connected: {spreadsheet.title}\n")

    city_meta_cache = _load_city_meta_cache(settings["city_meta_cache_file"])
    tab_counts, tab_unplaced = {}, {}

    for tab_name, gid in settings["tabs"].items():
        bar = "─" * max(1, 36 - len(tab_name))
        print(f"── {tab_name} {bar}")
        try:
            rows = fetch_tab(spreadsheet, gid, settings["spreadsheet_id"])
        except Exception as e:
            print(f"    ❌  Could not read tab: {e}\n")
            continue
        print(f"    {len(rows)} rows fetched")
        if not rows:
            print("    Skipping — empty tab.\n")
            continue

        keys     = list(rows[0].keys())
        addr_col = next((k for k in keys if k.upper().strip() == "ADDRESS"), None)
        city_col = next((k for k in keys if k.upper().strip() == "CITY"),    None)
        if not addr_col or not city_col:
            print(f"    ❌  ADDRESS or CITY column not found. Columns: {', '.join(keys)}\n")
            continue
        print(f"    Columns → address: {addr_col!r}   city: {city_col!r}")
        records = [{"address": r.get(addr_col, ""), "city": r.get(city_col, ""),
                    "row_num": r.get("_row_num")} for r in rows]

        def geocode_fn(clean, city, state, _key=settings["google_key"], _cache=cache):
            return geocode_clean(clean, city, state, _key, _cache)

        def meta_fn(city, lat, lng, _cache=city_meta_cache):
            return get_city_meta(city, lat, lng, _cache)

        pins, unplaced = build_pins(records, geocode_fn, meta_fn)
        save_cache(cache, settings["cache_file"])
        _save_city_meta_cache(city_meta_cache, settings["city_meta_cache_file"])

        tab_unplaced[tab_name] = len(unplaced)
        print(f"    {len(pins)} pins ready, {len(unplaced)} unplaced")
        if not pins:
            print("    Skipping — no geocoded addresses.\n")
            continue
        tab_counts[tab_name] = len(pins)
        safe_name = (tab_name.lower()
                     .replace(" ", "-")
                     .replace("/", "-")
                     .replace("--", "-"))
        out_file = settings["output_dir"] / f"map-{safe_name}.html"
        out_file.write_text(generate_html(tab_name, pins, unplaced, template), encoding="utf-8")
        print(f"    ✅  Saved → docs/{out_file.name}\n")

    write_metadata(tab_counts, tab_unplaced, settings["output_dir"])

    # In GitHub Actions, the workflow handles the commit/push — skip it here.
    if settings["auto_push"] and not IN_CI:
        push_to_github(settings["repo_path"])

    print("\n═══════════════════════════════════════")
    print("  Done!")
    if IN_CI:
        print("  Running in CI — workflow will commit & push.")
    elif settings["auto_push"]:
        print("  Maps are live at your GitHub Pages URL.")
    else:
        print("  Run: git push   to publish to GitHub Pages.")
    print("═══════════════════════════════════════\n")

if __name__ == "__main__":
    main()
