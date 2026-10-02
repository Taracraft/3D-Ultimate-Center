#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_HA_ROOT="${TARGET_HA_ROOT:-/var/lib/homeassistant/homeassistant}"
TARGET_SLICER_ROOT="${TARGET_SLICER_ROOT:-/var/lib/homeassistant/3d-printer-slicing-server}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"

echo "=== 3D Ultimate Center V6 Rebuild ==="
echo "Repo root      : $ROOT_DIR"
echo "HA root        : $TARGET_HA_ROOT"
echo "Slicer root    : $TARGET_SLICER_ROOT"
echo "Systemd dir    : $SYSTEMD_DIR"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="/root/3d-ultimate-center-backup-$STAMP"
mkdir -p "$BACKUP_ROOT"

backup_dir() {
  src="$1"
  name="$2"
  if [ -e "$src" ]; then
    cp -a "$src" "$BACKUP_ROOT/$name"
  fi
}

echo "=== Backups ==="
backup_dir "$TARGET_HA_ROOT/custom_components/ultimate_3d_studio_v6" "ultimate_3d_studio_v6"
backup_dir "$TARGET_HA_ROOT/custom_components/printer_control_center" "printer_control_center"
backup_dir "$TARGET_HA_ROOT/custom_components/printer_slicing_server" "printer_slicing_server"
backup_dir "$TARGET_SLICER_ROOT" "3d-printer-slicing-server"

echo "=== Directories ==="
mkdir -p "$TARGET_HA_ROOT/custom_components"
mkdir -p "$TARGET_SLICER_ROOT"
mkdir -p "$TARGET_SLICER_ROOT/data/uploads"
mkdir -p "$TARGET_SLICER_ROOT/data/output"
mkdir -p "$TARGET_SLICER_ROOT/run"

echo "=== Home Assistant components ==="
cp -a "$ROOT_DIR/homeassistant/custom_components/ultimate_3d_studio_v6" "$TARGET_HA_ROOT/custom_components/"
cp -a "$ROOT_DIR/homeassistant/custom_components/printer_control_center" "$TARGET_HA_ROOT/custom_components/"
cp -a "$ROOT_DIR/homeassistant/custom_components/printer_slicing_server" "$TARGET_HA_ROOT/custom_components/"

echo "=== Slicing server ==="
find "$TARGET_SLICER_ROOT" -mindepth 1 -maxdepth 1 \
  ! -name data ! -name run ! -name config.json \
  -exec rm -rf {} +
cp -a "$ROOT_DIR/slicing-server/." "$TARGET_SLICER_ROOT/"

if [ ! -f "$TARGET_SLICER_ROOT/config.json" ]; then
  cp "$ROOT_DIR/slicing-server/config.example.json" "$TARGET_SLICER_ROOT/config.json"
fi

chmod +x "$TARGET_SLICER_ROOT"/*.sh 2>/dev/null || true
chmod +x "$TARGET_SLICER_ROOT"/*.py 2>/dev/null || true

echo "=== Native packages ==="
apt-get update
apt-get install -y --no-install-recommends python3 python3-venv jq prusa-slicer

echo "=== Systemd ==="
for unit in \
  3d-printer-slicing-server.service \
  3d-printer-slicing-dispatch.service \
  3d-printer-slicing-dispatch.timer \
  3d-printer-slicing-refresh.service \
  3d-printer-slicing-refresh.timer
do
  install -m 0644 "$ROOT_DIR/deployment/systemd/$unit" "$SYSTEMD_DIR/$unit"
done

systemctl daemon-reload
systemctl enable 3d-printer-slicing-server.service
systemctl enable 3d-printer-slicing-dispatch.timer
systemctl enable 3d-printer-slicing-refresh.timer

echo "=== Start services ==="
systemctl restart 3d-printer-slicing-server.service
systemctl restart 3d-printer-slicing-dispatch.timer
systemctl restart 3d-printer-slicing-refresh.timer

echo "=== Validation ==="
python3 -m compileall -q "$TARGET_SLICER_ROOT"
python3 -m compileall -q "$TARGET_HA_ROOT/custom_components/ultimate_3d_studio_v6"
python3 -m compileall -q "$TARGET_HA_ROOT/custom_components/printer_control_center"
python3 -m compileall -q "$TARGET_HA_ROOT/custom_components/printer_slicing_server"

systemctl --no-pager --full status 3d-printer-slicing-server.service || true
systemctl --no-pager --full status 3d-printer-slicing-dispatch.timer || true
systemctl --no-pager --full status 3d-printer-slicing-refresh.timer || true

echo
echo "Rebuild base completed."
echo "Backup: $BACKUP_ROOT"
echo "NOTE: Home Assistant restart/reload and Bambu Studio engine provisioning are separate verification steps."
