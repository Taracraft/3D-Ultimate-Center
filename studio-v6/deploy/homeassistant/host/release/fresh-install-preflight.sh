#!/usr/bin/env bash
set -euo pipefail

TARGET_HA_ROOT="${TARGET_HA_ROOT:-/var/lib/homeassistant/homeassistant}"
TARGET_WORKER_ROOT="${TARGET_WORKER_ROOT:-/var/lib/homeassistant/3d-printer-slicing-server}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${ULTIMATE_STUDIO_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
BAMBU_APPIMAGE="${BAMBU_APPIMAGE:-}"
BAMBU_APPIMAGE_SHA256="${BAMBU_APPIMAGE_SHA256:-}"

fail() { echo "ERROR: $*" >&2; exit 1; }
need_file() { [ -f "$1" ] && [ ! -L "$1" ] || fail "Required file missing: $1"; }
need_dir() { [ -d "$1" ] && [ ! -L "$1" ] || fail "Required directory missing: $1"; }

for command in bash python3 jq curl systemctl install cmp find sha256sum awk grep unshare; do
  command -v "$command" >/dev/null 2>&1 || fail "Required command missing: $command"
done
[ "$(uname -m)" = "x86_64" ] || fail "Reviewed Bambu runtime requires x86_64."
[ "$TARGET_WORKER_ROOT" = "/var/lib/homeassistant/3d-printer-slicing-server" ] ||
  fail "Reviewed native deployer requires the default worker root."

HA_COMPONENT_SRC="$REPO_ROOT/homeassistant/custom_components/ultimate_3d_studio_v6"
BRIDGE_SRC="$REPO_ROOT/homeassistant/custom_components/printer_slicing_server"
FRONTEND_SRC="$REPO_ROOT/homeassistant/www/3d-studio-v6"
WORKER_SRC="$REPO_ROOT/slicing-server"
UNITS_SRC="$REPO_ROOT/deployment/systemd"

need_dir "$HA_COMPONENT_SRC"
need_dir "$BRIDGE_SRC"
need_dir "$FRONTEND_SRC"
need_dir "$WORKER_SRC"
need_dir "$UNITS_SRC"
need_file "$WORKER_SRC/SHA256SUMS"
need_file "$WORKER_SRC/DEPENDENCY-SHA256SUMS"
need_file "$WORKER_SRC/deploy-native-slicer.sh"
need_file "$WORKER_SRC/profiles/printers/bambu_lab_a1_04.json"

while read -r expected relative extra; do
  [ -n "${expected:-}${relative:-}${extra:-}" ] || continue
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || fail "Invalid SHA256SUMS digest."
  [ -z "${extra:-}" ] || fail "Invalid SHA256SUMS row."
  case "$relative" in
    systemd/*) source="$UNITS_SRC/${relative#systemd/}" ;;
    *) source="$WORKER_SRC/$relative" ;;
  esac
  need_file "$source"
  [ "$(sha256sum "$source" | awk '{print $1}')" = "$expected" ] ||
    fail "Worker source hash mismatch: $relative"
done < "$WORKER_SRC/SHA256SUMS"

count=0
seen=" "
while read -r expected file extra; do
  [ -n "${expected:-}${file:-}${extra:-}" ] || continue
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || fail "Invalid dependency digest."
  [[ "$file" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || fail "Unsafe dependency name."
  [ -z "${extra:-}" ] || fail "Invalid dependency row."
  [[ "$seen" != *" $file "* ]] || fail "Duplicate dependency: $file"
  seen+="$file "
  if [ "$file" = "job_control.py" ]; then source="$WORKER_SRC/$file"; else source="$HA_COMPONENT_SRC/$file"; fi
  need_file "$source"
  [ "$(sha256sum "$source" | awk '{print $1}')" = "$expected" ] ||
    fail "Dependency source hash mismatch: $file"
  count=$((count + 1))
done < "$WORKER_SRC/DEPENDENCY-SHA256SUMS"
[ "$count" -ge 11 ] || fail "Dependency manifest is incomplete."

for unit in   3d-printer-slicing-server.service   3d-printer-slicing-dispatch.service   3d-printer-slicing-dispatch.timer   3d-printer-slicing-refresh.service   3d-printer-slicing-refresh.timer
do
  need_file "$UNITS_SRC/$unit"
done

if [ -d "$TARGET_WORKER_ROOT/data/jobs" ]; then
  active="$(find "$TARGET_WORKER_ROOT/data/jobs" -maxdepth 1 -type f -name '*.slicing.json' | wc -l | tr -d '[:space:]')"
  queued="$(find "$TARGET_WORKER_ROOT/data/jobs" -maxdepth 1 -type f -name '*.queued.json' | wc -l | tr -d '[:space:]')"
  [ "$active" = "0" ] && [ "$queued" = "0" ] || fail "Worker busy: active=$active queued=$queued"
fi
[ ! -d "$TARGET_WORKER_ROOT/run/dispatcher.lock" ] || fail "Dispatcher lock is active."

ENGINE_BINARY="$TARGET_WORKER_ROOT/engines/bambu-studio/squashfs-root/bin/bambu-studio"
if [ ! -x "$ENGINE_BINARY" ]; then
  [ -n "$BAMBU_APPIMAGE" ] || fail "No installed Bambu runtime and BAMBU_APPIMAGE is unset."
  need_file "$BAMBU_APPIMAGE"
  [[ "$BAMBU_APPIMAGE_SHA256" =~ ^[0-9a-f]{64}$ ]] || fail "Pinned BAMBU_APPIMAGE_SHA256 is required."
  [ "$(sha256sum "$BAMBU_APPIMAGE" | awk '{print $1}')" = "$BAMBU_APPIMAGE_SHA256" ] ||
    fail "Bambu AppImage SHA-256 mismatch."
fi

echo "FRESH_INSTALL_PRECHECK_OK"
echo "Repository layout, source hashes, dependencies, systemd package and idle-state contract are valid."
if [ -x "$ENGINE_BINARY" ]; then
  echo "Bambu runtime: existing"
else
  echo "Bambu runtime: pinned AppImage available for later controlled extraction"
fi
echo "No files, services, jobs or printers were changed."
