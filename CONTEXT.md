# EpicFiber Maps — Operational Context

> This file is the authoritative reference for anyone (or any AI session) picking up this project.
> Keep it updated when credentials, secrets, or architecture change.

---

## What This Project Does

Pulls every address from the **BURIAL MASTER LIST** Google Sheet (two tabs: TEMPORARY LOCATES and BURY / DWB), geocodes them, and generates interactive Leaflet HTML maps hosted on GitHub Pages. Maps update automatically every morning at 6 AM CST via GitHub Actions — no laptop required.

**Live URLs**
| Page | URL |
|---|---|
| Landing Page | https://legacyepicfiber.github.io/epicfiber-repo/ |
| Temporary Locates Map | https://legacyepicfiber.github.io/epicfiber-repo/map-temporary-locates.html |
| Bury / DWB Map | https://legacyepicfiber.github.io/epicfiber-repo/map-bury--dwb.html |

---

## Architecture

```
Google Sheets (BURIAL MASTER LIST)
  ↓  gspread + Service Account
generate_map.py  (GitHub Actions — cron 0 11 * * * = 6 AM CST + manual dispatch)
  ↓  Geocoder waterfall: Google Maps API → Census → Nominatim
  ↓  cache/geocode_cache.json  (persisted across runs via actions/cache@v4)
docs/map-*.html + docs/index.html + docs/metadata.json
  ↓  git commit + push to main
GitHub Pages → legacyepicfiber.github.io/epicfiber-repo/
```

---

## Repository

- **GitHub repo:** https://github.com/LegacyEpicFiber/epicfiber-repo
- **Branch:** `main`
- **GitHub Pages source:** `main` branch, `/docs` folder
- **Local clone:** `~/Documents/Claude/Projects/epicfiber-maps`

---

## GitHub Actions Secrets

These must be set at **Settings → Secrets and variables → Actions** in the repo.

| Secret name | What it contains | Notes |
|---|---|---|
| `SERVICE_ACCOUNT_JSON` | Full JSON of the Google service account key | Must have Sheets + Drive API access |
| `SPREADSHEET_ID` | `1LsAbzp9tka4riOeS64osJDPUyYHeZppSV3V3c76xKCc` | The BURIAL MASTER LIST sheet ID |
| `GOOGLE_MAPS_API_KEY` | `AIzaSyB6e2Jiv-JJKlReNxsU8t708-XegKsIMPo` | **Capital N** — a prior typo (lowercase n) caused REQUEST_DENIED on every geocode request |

> ⚠️ **Known gotcha:** The API key has an uppercase `N` at position ~20 (`...JJKlRe**N**xsU8t...`). A single-character typo (lowercase `n`) was the root cause of all geocoding failures during initial setup. If geocoding breaks again, verify this character first.

---

## Google Cloud Platform

- **Project:** My First Project (`project-a68d8b40-08fa-4a78-b7b`)
- **Maps Platform API Key:** Application restrictions = **None** (required for server-side use in GitHub Actions)
- **APIs enabled on key:** Geocoding API (among 33 others)
- **Billing:** Must remain on a fully-activated **Paid account** — free trial does not allow Maps Platform geocoding

---

## Local Config (gitignored)

`~/Documents/Claude/Projects/epicfiber-maps/config.json` — never committed.

```json
{
  "spreadsheet_id": "1LsAbzp9tka4riOeS64osJDPUyYHeZppSV3V3c76xKCc",
  "service_account_path": "~/Documents/Claude/Projects/epicfiber-maps/service_account.json",
  "docs_dir": "~/Documents/Claude/Projects/epicfiber-maps/docs",
  "cache_dir": "~/Documents/Claude/Projects/epicfiber-maps/cache",
  "repo_path": "~/Documents/Claude/Projects/epicfiber-maps",
  "auto_push": true,
  "google_maps_api_key": "AIzaSyB6e2Jiv-JJKlReNxsU8t708-XegKsIMPo",
  "tabs": {
    "TEMPORARY LOCATES": "1043159223",
    "BURY / DWB": "1898822134"
  }
}
```

---

## Sheet Tabs

| Tab name | Sheet GID | Map file |
|---|---|---|
| TEMPORARY LOCATES | `1043159223` | `docs/map-temporary-locates.html` |
| BURY / DWB | `1898822134` | `docs/map-bury--dwb.html` |

> Note: the BURY / DWB tab name contains ` / ` which becomes `--` in the filename → `map-bury--dwb.html` (double dash). This trips up manual URL guessing.

---

## Geocode Cache

- Location: `cache/geocode_cache.json` (gitignored locally, persisted in GitHub Actions via `actions/cache@v4`)
- Key format: `"address|||city"` → `{lat, lng}` or `null`
- `null` entries are retried on every run — they are NOT permanently skipped
- Cache size as of v1.0.0: ~633 entries
- **No eviction policy** — stale entries for removed addresses persist indefinitely (not harmful, just accumulates)

---

## Map Features (v1.0.0)

- **Hover** over any dot → tooltip shows address + city; dashed lines draw to nearest 5 neighbors
- **Click** any dot → full proximity coloring (green = 5 closest, yellow = 6–15, red = 16+), solid lines to nearest 15, popup with address + Google Maps link
- **Click again** or click map background → reset
- **Dark theme** throughout; CARTO Voyager base tiles

---

## Known Risks / Maintenance Notes

| Risk | Impact | Mitigation |
|---|---|---|
| GCP billing lapses | Google geocoding fails; fallback to Census/Nominatim (lower match rate) | Keep billing active; check GCP console if geocode quality drops |
| GitHub Actions run fails silently | Map goes stale | Check Actions tab periodically or set up email notifications |
| Service account key rotated/revoked | Script cannot read Google Sheet | Update `SERVICE_ACCOUNT_JSON` secret with new key |
| Local launchd job still present | Redundant double-run at 6 AM | Remove: `launchctl unload ~/Library/LaunchAgents/com.epicfiber.mapsync.plist && rm ~/Library/LaunchAgents/com.epicfiber.mapsync.plist` |

---

## Running Manually

**Trigger via GitHub Actions (preferred):**
Go to https://github.com/LegacyEpicFiber/epicfiber-repo/actions → "Sync Maps" → "Run workflow"

**Run locally:**
```bash
cd ~/Documents/Claude/Projects/epicfiber-maps
python3 src/generate_map.py
```

---

## Version History

| Version | Date | Notes |
|---|---|---|
| v1.0.0 | 2026-04-10 | Production release. GitHub Actions pipeline, Google geocoding (633-entry cache), Leaflet proximity maps, hover address tooltips |
