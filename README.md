# EpicFiber Maps — Proximity Mesh Address Map

Interactive Leaflet maps that pull every address from the **BURIED MASTER LIST**
Google Sheet and plot them on a live map. Click any address node to instantly
recolor all others by geographic proximity — green (5 closest), yellow (6–15),
red (16+). Ideal for route planning and crew scheduling.

Hosted via **GitHub Pages** and auto-updated every morning at 6 AM.

---

## Live Maps

> Replace `YOUR-ORG` with your GitHub username or organization after setup.

| Map | URL |
|-----|-----|
| Temporary Locates | `https://YOUR-ORG.github.io/epicfiber-maps/map-temporary-locates.html` |
| Bury / DWB | `https://YOUR-ORG.github.io/epicfiber-maps/map-bury--dwb.html` |
| Landing Page | `https://YOUR-ORG.github.io/epicfiber-maps/` |

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| macOS (or Linux) | Windows not tested |
| Python 3.9+ | Ships with macOS |
| Git | `xcode-select --install` |
| Google Service Account JSON | See setup below |

---

## Quick Install (new machine)

```bash
git clone https://github.com/YOUR-ORG/epicfiber-maps.git
cd epicfiber-maps
bash install.sh
```

`install.sh` will:
- Install Python dependencies (`gspread`, `google-auth`)
- Create `docs/` and `cache/` directories
- Pre-fill `config.json` with your local paths
- Register a **daily 6 AM launchd job** to regenerate and auto-push maps

---

## Configuration

After running `install.sh`, edit `config.json`:

```json
{
  "spreadsheet_id": "YOUR_GOOGLE_SHEET_ID",
  "service_account_path": "/path/to/service_account.json",
  "docs_dir": "/path/to/epicfiber-maps/docs",
  "cache_dir": "/path/to/epicfiber-maps/cache",
  "repo_path": "/path/to/epicfiber-maps",
  "auto_push": true,
  "tabs": {
    "TEMPORARY LOCATES": "1043159223",
    "BURY / DWB": "1898822134"
  }
}
```

| Field | Description |
|-------|-------------|
| `spreadsheet_id` | The long ID from your Google Sheet URL |
| `service_account_path` | Absolute path to your Google service account `.json` key |
| `docs_dir` | Where generated maps are written (should be `<repo>/docs`) |
| `cache_dir` | Geocode cache location (gitignored, persists between runs) |
| `repo_path` | Root of this repo (for `git push`) |
| `auto_push` | `true` = automatically push to GitHub after each sync |
| `tabs` | Tab name → sheet GID pairs (GID is in the URL: `…#gid=XXXXX`) |

> `config.json` is gitignored — your credentials and local paths are never committed.

---

## Google Service Account Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable the **Google Sheets API** and **Google Drive API**
4. Create a Service Account → download the JSON key
5. Place the JSON file at the path in `config.json → service_account_path`
6. Share your Google Sheet with the service account email (Viewer access is enough)

---

## GitHub Pages Setup

1. Push the repo to GitHub
2. Go to **Settings → Pages**
3. Source: **Deploy from a branch**
4. Branch: `main` — Folder: `/docs`
5. Save — GitHub will publish within a minute

---

## Running Manually

```bash
python3 src/generate_map.py
```

This will geocode any new addresses, write updated HTML to `docs/`, update
`docs/metadata.json`, and push to GitHub if `auto_push` is `true`.

---

## File Structure

```
epicfiber-maps/
├── docs/                        ← Published to GitHub Pages
│   ├── index.html               ← Landing page (links to both maps)
│   ├── map-temporary-locates.html
│   ├── map-bury--dwb.html
│   └── metadata.json            ← Last sync time + address counts
├── src/
│   ├── generate_map.py          ← Main sync script
│   └── map_template.html        ← Leaflet HTML template
├── cache/
│   └── geocode_cache.json       ← Local geocode cache (gitignored)
├── config.json                  ← Your local config (gitignored)
├── config.template.json         ← Committed template for new installs
├── requirements.txt
├── install.sh
└── README.md
```

---

## Adding New Sheet Tabs

Edit the `tabs` section in `config.json`:

```json
"tabs": {
  "TEMPORARY LOCATES": "1043159223",
  "BURY / DWB": "1898822134",
  "NEW TAB NAME": "YOUR_GID_HERE"
}
```

Then add a link card to `docs/index.html` and run `python3 src/generate_map.py`.

---

## Viewing Sync Logs

```bash
tail -f ~/Library/Logs/epicfiber_mapsync.log
```

---

## Uninstalling the Daily Sync

```bash
launchctl unload ~/Library/LaunchAgents/com.epicfiber.mapsync.plist
rm ~/Library/LaunchAgents/com.epicfiber.mapsync.plist
```
