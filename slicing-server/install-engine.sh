#!/bin/sh
LOG=/var/lib/homeassistant/3d-printer-slicing-server/install-engine.log
{
  echo "============================================================"
  echo "3D-Printer Slicing Server - Native Engine Installation"
  echo "============================================================"
  date -Iseconds
  apt-get update
  apt-get install -y --no-install-recommends prusa-slicer
  echo ""
  echo "Engine-Prüfung:"
  command -v prusa-slicer || true
  prusa-slicer --version || true
  echo "Terminal bleibt offen."
} > "$LOG" 2>&1
