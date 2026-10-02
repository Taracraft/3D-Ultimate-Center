#!/bin/sh
ROOT=/var/lib/homeassistant/3d-printer-slicing-server/engines/bambu-studio/squashfs-root
OUT=/var/lib/homeassistant/3d-printer-slicing-server/bambu-probe.txt
{
  echo "=== BINARY ==="
  ls -l "$ROOT/bin/bambu-studio"
  echo "=== VERSION ==="
  LD_LIBRARY_PATH="$ROOT/bin" "$ROOT/bin/bambu-studio" --version 2>&1 || true
  echo "=== HELP ==="
  LD_LIBRARY_PATH="$ROOT/bin" "$ROOT/bin/bambu-studio" --help 2>&1 | head -n 160 || true
  echo "=== A1 PROFILES ==="
  find "$ROOT/resources" -type f | grep -Ei "Bambu.*A1|A1.*0\\.[2486]|A1.*json" | head -n 200
} > "$OUT" 2>&1