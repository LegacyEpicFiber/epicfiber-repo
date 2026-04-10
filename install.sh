#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
#  EpicFiber Maps — One-Command Installer
#  Usage: bash install.sh
# ══════════════════════════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_LABEL="com.epicfiber.mapsync"
PLIST_DEST="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Legacy Epic Fiber — Map Sync Installer  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Check Python 3 ────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌  Python 3 is required but not found."
  echo "    Install it from https://python.org and re-run this script."
  exit 1
fi
PY_VERSION=$(python3 --version 2>&1)
echo "✅  Python found: $PY_VERSION"

# ── 2. Install Python dependencies ───────────────────────────────────────────
echo ""
echo "📦  Installing Python dependencies…"
pip3 install --break-system-packages -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null \
  || pip3 install -r "$SCRIPT_DIR/requirements.txt"
echo "✅  Dependencies installed."

# ── 3. Create directories ─────────────────────────────────────────────────────
mkdir -p "$SCRIPT_DIR/docs"
mkdir -p "$SCRIPT_DIR/cache"
echo "✅  Output directories ready."

# ── 4. Set up config.json ─────────────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/config.json" ]; then
  cp "$SCRIPT_DIR/config.template.json" "$SCRIPT_DIR/config.json"
  # Auto-fill paths for this machine
  ESCAPED_DIR=$(echo "$SCRIPT_DIR" | sed 's/[\/&]/\\&/g')
  sed -i '' "s|~/path/to/epicfiber-maps/docs|$SCRIPT_DIR/docs|g" "$SCRIPT_DIR/config.json"
  sed -i '' "s|~/path/to/epicfiber-maps/cache|$SCRIPT_DIR/cache|g" "$SCRIPT_DIR/config.json"
  sed -i '' "s|~/path/to/epicfiber-maps|$SCRIPT_DIR|g" "$SCRIPT_DIR/config.json"
  sed -i '' "s|~/path/to/service_account.json|$SCRIPT_DIR/service_account.json|g" "$SCRIPT_DIR/config.json"
  echo "✅  config.json created with your local paths pre-filled."
  echo ""
  echo "  ⚠️  ACTION REQUIRED:"
  echo "      Edit config.json and set your spreadsheet_id."
  echo "      Place service_account.json at: $SCRIPT_DIR/service_account.json"
else
  echo "✅  config.json already exists (skipped)."
fi

# ── 5. Install launchd plist (daily 6 AM sync) ───────────────────────────────
echo ""
echo "🕕  Installing daily 6 AM auto-sync via launchd…"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HOME/Library/Logs"

cat > "$PLIST_DEST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>-u</string>
    <string>${SCRIPT_DIR}/src/generate_map.py</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>    <integer>6</integer>
    <key>Minute</key>  <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${HOME}/Library/Logs/epicfiber_mapsync.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/Library/Logs/epicfiber_mapsync.log</string>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
PLIST

launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load   "$PLIST_DEST"
echo "✅  Daily sync scheduled. Logs: ~/Library/Logs/epicfiber_mapsync.log"

# ── 6. Initialize git if needed ───────────────────────────────────────────────
if [ ! -d "$SCRIPT_DIR/.git" ]; then
  echo ""
  echo "🔧  Initializing git repository…"
  git -C "$SCRIPT_DIR" init
  git -C "$SCRIPT_DIR" add .
  git -C "$SCRIPT_DIR" commit -m "Initial commit — EpicFiber Maps"
  echo "✅  Git repo initialized."
  echo ""
  echo "  Next: add your GitHub remote and push:"
  echo "    git remote add origin https://github.com/YOUR-ORG/epicfiber-maps.git"
  echo "    git push -u origin main"
else
  echo "✅  Git repo already initialized."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║          Installation complete! 🎉        ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  NEXT STEPS:"
echo "  1. Edit config.json → set spreadsheet_id and verify all paths"
echo "  2. Place service_account.json in this directory"
echo "  3. Run the map generator once:"
echo "       python3 src/generate_map.py"
echo "  4. Create a GitHub repo and push:"
echo "       git remote add origin https://github.com/YOUR-ORG/epicfiber-maps.git"
echo "       git push -u origin main"
echo "  5. In GitHub → Settings → Pages → Source: Deploy from branch → /docs"
echo "  6. Your maps will be live at:"
echo "       https://YOUR-ORG.github.io/epicfiber-maps/"
echo ""
