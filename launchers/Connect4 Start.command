#!/bin/bash
# Connect4 Home Assistant — double-click launcher for macOS.
# Downloads the latest app, sets it up, starts it, and opens your browser.
# First time on a Mac: right-click this file and choose "Open".
set -e

APP_HOME="$HOME/Connect4SmartHome"
SRC="$APP_HOME/src"
REPO_TARBALL="https://github.com/sammoessing/smarthome/archive/HEAD.tar.gz"

echo
echo "  🏠 Connect4 Home Assistant"
echo

mkdir -p "$APP_HOME"

echo "  Getting the latest app..."
TMP="$(mktemp -d)"
if curl -fsSL "$REPO_TARBALL" | tar xz -C "$TMP" 2>/dev/null; then
  rm -rf "$SRC"
  mv "$TMP"/*/ "$SRC"
elif [ -d "$SRC" ]; then
  echo "  (couldn't check for updates — starting the version you already have)"
else
  echo "  ✕ No internet connection and no downloaded copy yet."
  echo "    Connect to WiFi and double-click this again."
  read -r -p "  Press Enter to close..." _
  exit 1
fi
rm -rf "$TMP"

if ! command -v python3 >/dev/null 2>&1; then
  echo "  ✕ Python 3 is needed (macOS will offer to install it — accept, then"
  echo "    double-click this file again)."
  python3 --version || true
  read -r -p "  Press Enter to close..." _
  exit 1
fi

if [ ! -d "$APP_HOME/.venv" ]; then
  echo "  Setting up (first run only, ~1 minute)..."
  python3 -m venv "$APP_HOME/.venv"
fi
# shellcheck disable=SC1091
source "$APP_HOME/.venv/bin/activate"
pip install -q -r "$SRC/requirements.txt"

IP="$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo localhost)"

echo
echo "  ✓ Starting! Your browser will open in a moment."
echo "    On your phone (same WiFi), open:  http://$IP:8000"
echo "    Leave this window open; close it (or press Ctrl+C) to stop."
echo

if command -v open >/dev/null 2>&1; then
  ( sleep 2; open "http://localhost:8000" ) &
elif command -v xdg-open >/dev/null 2>&1; then
  ( sleep 2; xdg-open "http://localhost:8000" ) &
fi

cd "$SRC"
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
