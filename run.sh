#!/usr/bin/env bash
# Linux / macOS launcher. First run creates a private Python environment
# (.venv) and installs the packages; later runs just start the app.
#
# v1.1 fix: pehle sirf ".venv folder hai ya nahi" dekhte the. Agar pehli baar
# pip install beech mein fail hua (internet gaya), folder ban chuka hota tha,
# toh agli baar install skip hota aur app kabhi nahi khulta. Ab install poora
# hone par hi .venv/.likhit-ready marker banta hai, aur usi ko check karte hain.
# requirements.txt badle (naya package aaya) toh marker purana maan ke
# dobara install hota hai.
set -e
cd "$(dirname "$0")"
PY=python3
command -v $PY >/dev/null || { echo "Python 3.10+ is needed. Install it first."; exit 1; }
MARKER=.venv/.likhit-ready
if [ ! -f "$MARKER" ] || [ requirements.txt -nt "$MARKER" ]; then
  echo "Setting things up (needs internet once)..."
  [ -x .venv/bin/python ] || $PY -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip -q
  ./.venv/bin/python -m pip install -r requirements.txt -q
  touch "$MARKER"   # sirf tab pahunchte hain jab upar sab safal hua (set -e)
fi
exec ./.venv/bin/python main.py "$@"
