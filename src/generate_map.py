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
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

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
#  LOAD CONFIG
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

cfg              = load_config()
SPREADSHEET_ID   = cfg["spreadsheet_id"]
SERVICE_ACCT     = Path(cfg["service_account_path"]).expanduser()
OUTPUT_DIR       = Path(cfg["docs_dir"]).expanduser()
CACHE_DIR        = Path(cfg.get("cache_dir", str(REPO_ROOT / "cache"))).expanduser()
CACHE_FILE           = CACHE_DIR / "geocode_cache.json"
CITY_META_CACHE_FILE = CACHE_DIR / "city_meta_cache.json"
TEMPLATE_FILE    = Path(__file__).parent / "map_template.html"
TABS             = cfg.get("tabs", {})
AUTO_PUSH        = cfg.get("auto_push", False)
REPO_PATH        = Path(cfg.get("repo_path", str(REPO_ROOT))).expanduser()

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

NOMINATIM_UA  = "LegacyEpicFiber-AddressMap/1.0 (legacy.buryandbore@gmail.com)"
GEOCODE_DELAY = 1.2   # seconds between Nominatim requests (respect rate limit)

# Google Maps API key — env var takes precedence (set in GitHub Actions via Secret),
# falls back to value in config.json for local runs.
GOOGLE_MAPS_KEY = (
    os.environ.get("GOOGLE_MAPS_API_KEY")
    or cfg.get("google_maps_api_key", "")
)

# Detect GitHub Actions environment so we skip the local git-push step
# (Actions handles the commit/push itself via the workflow file).
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"

# Cities in Michigan — everything else defaults to Indiana
MICHIGAN_CITIES = {
    "BARODA", "BRIDGMAN", "BYRON CENTER", "CASSOPOLIS",
    "CORUNNA", "DECATUR", "DOWAGIAC", "FENNVILLE",
    "GRAND HAVEN", "MOLINE", "PLAINWELL", "SAWYER",
    "VICKSBURG", "WATERVLIET", "WAYLAND", "WYOMING",
}

# City → (County, Township) for the service area
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

def open_spreadsheet():
    if not SERVICE_ACCT.exists():
        sys.exit(
            f"\n❌  Service account key not found:\n      {SERVICE_ACCT}\n"
            "    Set the correct path in config.json → service_account_path.\n"
        )
    creds = Credentials.from_service_account_file(str(SERVICE_ACCT), scopes=SCOPES)
    gc    = gspread.authorize(creds)
    try:
        return gc.open_by_key(SPREADSHEET_ID)
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


def fetch_tab(spreadsheet, gid):
    ws = spreadsheet.get_worksheet_by_id(int(gid))

    # Identify completed rows (neon green #00ff00) to exclude before geocoding
    green_indices = _get_green_row_indices(
        spreadsheet.client.auth, SPREADSHEET_ID, ws.title
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

def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(cache):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")

def _state_for(city):
    return "MI" if city.upper().strip() in MICHIGAN_CITIES else "IN"

def _clean_address(address):
    address = re.sub(r'\s*/.*$', '', address)
    address = re.sub(
        r'\s+(?:LOT\.?|UNIT|APT\.?|#|STE\.?)\s*[\w.-]*\s*$',
        '', address, flags=re.IGNORECASE
    )
    address = re.sub(r'\bIN-(\d+)\b', r'Indiana Route \1', address, flags=re.IGNORECASE)
    address = re.sub(r'\bUS-(\d+)\b', r'US Route \1', address, flags=re.IGNORECASE)
    address = re.sub(r'\bCO\.?\s*R(?:OA)?D\.?\b', 'County Road', address, flags=re.IGNORECASE)
    return address.strip()

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

def geocode(address, city, cache):
    key = f"{address}|||{city}"
    if key in cache and cache[key] is not None:
        return cache[key]
    state      = _state_for(city)
    clean_addr = _clean_address(address)

    # Geocoder waterfall: Google → Census → Nominatim
    result = None
    if GOOGLE_MAPS_KEY:
        result = _geocode_google(clean_addr, city, state, GOOGLE_MAPS_KEY)
    if not result:
        result = _geocode_census(clean_addr, city, state)
    if not result:
        result = _geocode_nominatim(clean_addr, city, state)
    if not result:
        print(f"    ⚠  No geocode result: {address}, {city}")
    cache[key] = result
    return result

# ══════════════════════════════════════════════════════════════════════════════
#  CITY META  (county + township lookup with Census fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _load_city_meta_cache():
    if CITY_META_CACHE_FILE.exists():
        try:
            with open(CITY_META_CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_city_meta_cache(cache):
    CITY_META_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CITY_META_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def _fetch_city_meta_census(city, state):
    """Query Census geographies endpoint for county + township of a city."""
    try:
        params = urllib.parse.urlencode({
            "street":    "1 Main St",
            "city":      city,
            "state":     state,
            "benchmark": "Public_AR_Current",
            "vintage":   "Current_Current",
            "layers":    "Counties,County Subdivisions",
            "format":    "json",
        })
        url = (f"https://geocoding.geo.census.gov/geocoder/geographies/address?{params}")
        req = urllib.request.Request(url, headers={"User-Agent": NOMINATIM_UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        matches = data.get("result", {}).get("addressMatches", [])
        if not matches:
            return ("", "")
        geos     = matches[0].get("geographies", {})
        counties = geos.get("Counties", [])
        subdivs  = geos.get("County Subdivisions", [])
        county   = counties[0]["NAME"].strip() if counties else ""
        township = subdivs[0]["NAME"].strip()  if subdivs  else ""
        if county and "County" not in county:
            county = f"{county} County"
        if township:
            township = township.title()  # normalize "wayne township" → "Wayne Township"
        return (county, township)
    except Exception as e:
        print(f"    ⚠  Census city-meta lookup failed for {city}: {e}")
        return ("", "")

def get_city_meta(city, city_meta_cache):
    """Return (county, township) for a city.
    Priority: runtime cache → CITY_META hardcoded table → Census API.
    """
    key = city.upper()
    if key in city_meta_cache:
        entry = city_meta_cache[key]
        return (entry[0], entry[1])
    if key in CITY_META:
        result = CITY_META[key]
        city_meta_cache[key] = list(result)
        return result
    # Unknown city — ask Census
    state  = _state_for(city)
    result = _fetch_city_meta_census(city, state)
    if result[0]:
        print(f"    ℹ  Census meta → {city}: {result[0]}, {result[1]}")
    city_meta_cache[key] = list(result)
    return result

# ══════════════════════════════════════════════════════════════════════════════
#  BUILD ADDRESS LIST
# ══════════════════════════════════════════════════════════════════════════════

def build_address_list(rows, cache):
    if not rows:
        return []
    keys     = list(rows[0].keys())
    addr_col = next((k for k in keys if k.upper().strip() == "ADDRESS"), None)
    city_col = next((k for k in keys if k.upper().strip() == "CITY"),    None)
    if not addr_col or not city_col:
        print(f"    ❌  ADDRESS or CITY column not found. Columns: {', '.join(keys)}")
        return []
    print(f"    Columns → address: {addr_col!r}   city: {city_col!r}")
    city_meta_cache = _load_city_meta_cache()
    out, new_count = [], 0
    for row in rows:
        address = str(row.get(addr_col, "")).strip()
        city    = str(row.get(city_col, "")).strip()
        if not address or not city:
            continue
        was_cached = f"{address}|||{city}" in cache
        coord = geocode(address, city, cache)
        if not coord:
            continue
        if not was_cached:
            new_count += 1
        county, township = get_city_meta(city, city_meta_cache)
        maps_url = ("https://maps.google.com/?q="
                    + urllib.parse.quote_plus(f"{address}, {city}"))
        out.append({
            "address":  address,
            "city":     city,
            "county":   county,
            "township": township,
            "lat":      coord["lat"],
            "lng":      coord["lng"],
            "maps_url": maps_url,
            "row_num":  row.get("_row_num"),
        })
    _save_city_meta_cache(city_meta_cache)
    print(f"    {len(out)} addresses ready  ({new_count} newly geocoded)")
    return out

# ══════════════════════════════════════════════════════════════════════════════
#  HTML GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_html(tab_name, addresses, template):
    html = template
    html = html.replace("{{TAB_NAME}}",       tab_name)
    html = html.replace("{{ADDRESSES_JSON}}", json.dumps(addresses, indent=2, ensure_ascii=False))
    return html

# ══════════════════════════════════════════════════════════════════════════════
#  METADATA
# ══════════════════════════════════════════════════════════════════════════════

def write_metadata(tab_counts):
    meta = {
        "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "last_updated_display": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
        "tabs": tab_counts,
    }
    meta_file = OUTPUT_DIR / "metadata.json"
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"  ✅  Wrote metadata.json")

# ══════════════════════════════════════════════════════════════════════════════
#  GITHUB PUSH
# ══════════════════════════════════════════════════════════════════════════════

def push_to_github():
    print("\n  Pushing to GitHub Pages…")
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        subprocess.run(
            ["git", "-C", str(REPO_PATH), "add", "docs/"],
            check=True, capture_output=True
        )
        result = subprocess.run(
            ["git", "-C", str(REPO_PATH), "commit", "-m", f"Auto-update maps {date_str}"],
            capture_output=True, text=True
        )
        if "nothing to commit" in result.stdout:
            print("  ℹ  No changes to push (maps unchanged).")
            return
        subprocess.run(
            ["git", "-C", str(REPO_PATH), "push"],
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

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not TEMPLATE_FILE.exists():
        sys.exit(
            f"\n❌  Template not found:\n      {TEMPLATE_FILE}\n"
            "    map_template.html must be in src/ alongside this script.\n"
        )

    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    cache    = load_cache()
    print(f"  Geocode cache: {len(cache)} entries loaded")

    print("  Connecting to Google Sheets…")
    spreadsheet = open_spreadsheet()
    print(f"  Connected: {spreadsheet.title}\n")

    tab_counts = {}

    for tab_name, gid in TABS.items():
        bar = "─" * max(1, 36 - len(tab_name))
        print(f"── {tab_name} {bar}")
        try:
            rows = fetch_tab(spreadsheet, gid)
        except Exception as e:
            print(f"    ❌  Could not read tab: {e}\n")
            continue
        print(f"    {len(rows)} rows fetched")
        addresses = build_address_list(rows, cache)
        save_cache(cache)
        if not addresses:
            print("    Skipping — no valid addresses.\n")
            continue
        tab_counts[tab_name] = len(addresses)
        safe_name = (tab_name.lower()
                     .replace(" ", "-")
                     .replace("/", "-")
                     .replace("--", "-"))
        out_file = OUTPUT_DIR / f"map-{safe_name}.html"
        out_file.write_text(generate_html(tab_name, addresses, template), encoding="utf-8")
        print(f"    ✅  Saved → docs/{out_file.name}\n")

    write_metadata(tab_counts)

    # In GitHub Actions, the workflow handles the commit/push — skip it here.
    if AUTO_PUSH and not IN_CI:
        push_to_github()

    print("\n═══════════════════════════════════════")
    print("  Done!")
    if IN_CI:
        print("  Running in CI — workflow will commit & push.")
    elif AUTO_PUSH:
        print("  Maps are live at your GitHub Pages URL.")
    else:
        print("  Run: git push   to publish to GitHub Pages.")
    print("═══════════════════════════════════════\n")

if __name__ == "__main__":
    main()
