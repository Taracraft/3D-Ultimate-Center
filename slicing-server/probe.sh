#!/bin/sh
OUT=/var/lib/homeassistant/3d-printer-slicing-server/probe-result.txt
{
  echo "DATE=$(date -Iseconds)"
  echo "HOST=$(hostname)"
  echo "ARCH=$(uname -m)"
  echo "PYTHON=$(command -v python3 || true)"
  echo "PRUSA=$(command -v prusa-slicer || command -v PrusaSlicer || true)"
  echo "ORCA=$(command -v orca-slicer || command -v OrcaSlicer || true)"
  echo "CURA=$(command -v CuraEngine || true)"
  echo "APT_PRUSA=$(apt-cache policy prusa-slicer 2>/dev/null | tr "\n" " " || true)"
  echo "APT_CURA=$(apt-cache policy cura-engine 2>/dev/null | tr "\n" " " || true)"
} > "$OUT"