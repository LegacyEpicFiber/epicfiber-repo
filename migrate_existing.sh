#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
#  migrate_existing.sh
#  Run this ONCE to migrate your existing EpicFiber map install into this repo.
#  Usage: bash ~/Documents/Claude/Projects/epicfiber-maps/migrate_existing.sh
# ══════════════════════════════════════════════════════════════════════════════
set -e

REPO="$HOME/Documents/Claude/Projects/epicfiber-maps"
VAULT_HTML="$HOME/Documents/Documents - Angel's MacBook Pro/ML Obsidian/ML/Maps/html"
OLD_SCRIPT="$HOME/Documents/Claude/Projects/Address Map"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   EpicFiber Maps — Migration Script       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# 1. Create directories
mkdir -p "$REPO/docs"
mkdir -p "$REPO/cache"
echo "✅  Directories ready."

# 2. Copy existing generated HTML maps → docs/
if [ -f "$VAULT_HTML/map-temporary-locates.html" ]; then
  cp "$VAULT_HTML/map-temporary-locates.html" "$REPO/docs/"
  echo "✅  Copied map-temporary-locates.html"
fi
if [ -f "$VAULT_HTML/map-bury--dwb.html" ]; then
  cp "$VAULT_HTML/map-bury--dwb.html" "$REPO/docs/"
  echo "✅  Copied map-bury--dwb.html"
fi

# 3. Copy geocode cache → cache/
if [ -f "$VAULT_HTML/geocode_cache.json" ]; then
  cp "$VAULT_HTML/geocode_cache.json" "$REPO/cache/"
  echo "✅  Geocode cache migrated ($(python3 -c "import json; d=json.load(open('$REPO/cache/geocode_cache.json')); print(len(d))" 2>/dev/null || echo '?') entries)"
fi

# 4. Copy service account JSON if it's next to the old script
if [ -f "$OLD_SCRIPT/service_account.json" ]; then
  cp "$OLD_SCRIPT/service_account.json" "$REPO/"
  echo "✅  Copied service_account.json"
else
  echo "⚠️  service_account.json not found at $OLD_SCRIPT/"
  echo "    Copy it manually: cp /path/to/service_account.json $REPO/"
fi

# 5. Unload the old launchd plist if it exists
OLD_PLIST="$HOME/Library/LaunchAgents/com.epicfiber.mapsync.plist"
if [ -f "$OLD_PLIST" ]; then
  launchctl unload "$OLD_PLIST" 2>/dev/null || true
  echo "✅  Unloaded old launchd plist."
fi

# 6. Run install.sh to set up fresh launchd + config
echo ""
echo "Running install.sh…"
bash "$REPO/install.sh"

# 7. Write a metadata.json placeholder so the landing page loads cleanly
python3 -c "
import json, datetime
from pathlib import Path
meta = {
  'last_updated': datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
  'last_updated_display': datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p'),
  'tabs': {'TEMPORARY LOCATES': 0, 'BURY / DWB': 0}
}
Path('$REPO/docs/metadata.json').write_text(json.dumps(meta, indent=2))
print('✅  Wrote placeholder metadata.json')
"

# 8. Git init + first commit
cd "$REPO"
if [ ! -d ".git" ]; then
  git init
  git add .
  git commit -m "Initial commit — EpicFiber Proximity Mesh Maps"
  echo "✅  Git repo initialized and first commit made."
else
  git add .
  git diff --cached --quiet || git commit -m "Migrate to new repo structure"
  echo "✅  Git commit made."
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║           Migration complete! 🎉          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  REMAINING STEPS:"
echo ""
echo "  1. Create a new GitHub repo named 'epicfiber-maps' at:"
echo "       https://github.com/new"
echo "     (public, no README, no .gitignore)"
echo ""
echo "  2. Add the remote and push:"
echo "       cd $REPO"
echo "       git remote add origin https://github.com/YOUR-ORG/epicfiber-maps.git"
echo "       git branch -M main"
echo "       git push -u origin main"
echo ""
echo "  3. Enable GitHub Pages:"
echo "       GitHub repo → Settings → Pages"
echo "       Source: Deploy from branch → main → /docs → Save"
echo ""
echo "  4. Run a fresh sync to publish updated maps:"
echo "       python3 $REPO/src/generate_map.py"
echo ""
echo "  Your maps will be live at:"
echo "       https://YOUR-ORG.github.io/epicfiber-maps/"
echo ""
