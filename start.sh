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

exec python3 -m app.launch
