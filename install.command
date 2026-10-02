#!/bin/bash
# First-time installer for CC Pipeline (AI Centric). Double-click to run.
# First time on mac: run  chmod +x install.command  once so it is double-clickable.
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
    python3 install.py
elif command -v python >/dev/null 2>&1; then
    python install.py
else
    echo
    echo "Python 3 not found. Install it (xcode-select --install, or python.org), then re-run."
fi

echo
read -n 1 -s -r -p "Press any key to close..."
