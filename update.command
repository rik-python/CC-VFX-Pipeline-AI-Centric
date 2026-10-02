#!/bin/bash
# One-click updater for CC Pipeline (AI Centric). Double-click to get the latest pipeline.
# First time on mac: run  chmod +x update.command  once so it is double-clickable.
cd "$(dirname "$0")" || exit 1

if ! command -v git >/dev/null 2>&1; then
    echo
    echo "Git is not installed. Install it with:  xcode-select --install"
    echo
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

echo "============================================"
echo "  Updating CC Pipeline (AI Centric)..."
echo "============================================"
echo
if ! git pull; then
    echo
    echo "Update FAILED. If it mentions 'local changes', you edited a repo file."
    echo "Do not edit files inside this folder. Ask Rikin for help."
    echo
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

echo
if command -v python3 >/dev/null 2>&1; then
    echo "Syncing folder structure to existing shots..."
    python3 pipeline_core.py sync
elif command -v python >/dev/null 2>&1; then
    echo "Syncing folder structure to existing shots..."
    python pipeline_core.py sync
else
    echo "Python not found - skipping folder sync. Install Python 3 to auto-add new folders."
fi

echo
echo "============================================"
echo "  Done. RESTART NUKE to load the update."
echo "============================================"
echo
read -n 1 -s -r -p "Press any key to close..."
