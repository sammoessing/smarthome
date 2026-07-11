#!/usr/bin/env bash
# One-command start for the house you're in: sets up a venv, installs
# dependencies, and serves the app on the local WiFi.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Setting up (first run only)..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

if command -v hostname >/dev/null && hostname -I >/dev/null 2>&1; then
  IP=$(hostname -I | awk '{print $1}')
else
  IP=$(ipconfig getifaddr en0 2>/dev/null || echo "<this-machine's-ip>")
fi

echo
echo "  Connect4 Home Assistant is starting."
echo "  On your phone (same WiFi), open:  http://$IP:8000"
echo
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
