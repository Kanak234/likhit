#!/usr/bin/env bash
# Linux / macOS launcher. First run creates a private Python environment
# (.venv) and installs the packages; later runs just start the app.
set -e
cd "$(dirname "$0")"
PY=python3
command -v $PY >/dev/null || { echo "Python 3.10+ is needed. Install it first."; exit 1; }
if [ ! -d .venv ]; then
  echo "First run: setting things up (needs internet once)..."
  $PY -m venv .venv
  ./.venv/bin/pip install --upgrade pip -q
  ./.venv/bin/pip install -r requirements.txt -q
fi
exec ./.venv/bin/python main.py "$@"
