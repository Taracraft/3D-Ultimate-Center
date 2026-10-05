#!/usr/bin/env bash
# Compatibility entry point: source validation/staging only, never live rebuild.
set -euo pipefail
ROOT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/studio-v6/tools/studio_linux_preflight.py" && -f "$ROOT_DIR/tools/studio_linux_preflight.py" ]]; then
  printf '%s\n' 'Mehrdeutiges Quelllayout. Kein Neuaufbau wurde ausgefuehrt.' >&2
  exit 2
elif [[ -f "$ROOT_DIR/studio-v6/tools/studio_linux_preflight.py" ]]; then
  TOOL="$ROOT_DIR/studio-v6/tools/studio_linux_preflight.py"
  LAYOUT=public
elif [[ -f "$ROOT_DIR/tools/studio_linux_preflight.py" ]]; then
  TOOL="$ROOT_DIR/tools/studio_linux_preflight.py"
  LAYOUT=canonical
else
  printf '%s\n' 'Der gepruefte Paketpruefer fehlt. Kein Neuaufbau wurde ausgefuehrt.' >&2
  exit 2
fi
if [[ $# -eq 0 ]]; then
  printf '%s\n' 'Der automatische Legacy-Neuaufbau ist stillgelegt.' \
    'Verwendung: bash scripts/rebuild-homeassist.sh --check' \
    'Oder:       bash scripts/rebuild-homeassist.sh --stage /neuer/isolierter/kandidat' \
    'Beides installiert nichts und startet keine Dienste. Live-Aktivierung bleibt ein eigener gepruefter Schritt.' >&2
  exit 2
fi
exec python3 "$TOOL" --source-root "$ROOT_DIR" --layout "$LAYOUT" "$@"
