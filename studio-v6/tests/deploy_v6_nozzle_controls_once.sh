#!/bin/bash
set -Eeuo pipefail

STAGE=/var/lib/homeassistant/homeassistant/pcc-backups/v6-nozzle-layer-wall-controls-20260831-002450-host-stage/canonical-v6-bundle
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/var/lib/homeassistant/homeassistant/pcc-backups/v6-nozzle-controls-activation-$STAMP
LOG=$BACKUP/deploy.log
MISSING=$BACKUP/MISSING-BEFORE.txt
SUCCESS=0
DEPLOYED=0
TIMERS_STOPPED=0

COMPONENT=$STAGE/custom_components/ultimate_3d_studio_v6
HOST_SOURCE=$STAGE/host/3d-printer-slicing-server
FRONTEND_SOURCE=$STAGE/www/3d-studio-v6
LIVE_COMPONENT=/var/lib/homeassistant/homeassistant/custom_components/ultimate_3d_studio_v6
LIVE_HOST=/var/lib/homeassistant/3d-printer-slicing-server
LIVE_FRONTEND=/var/lib/homeassistant/homeassistant/www/3d-studio-v6

SOURCES=(
  "$COMPONENT/slicer_nozzle_profiles.py"
  "$COMPONENT/slicer_plate_views_v2.py"
  "$COMPONENT/slicer_backend_router.py"
  "$COMPONENT/dispatch-job-options.sh"
  "$COMPONENT/materialize-bambu-multimaterial.py"
  "$COMPONENT/materialize-bambu-multimaterial.py"
  "$HOST_SOURCE/server.py"
  "$HOST_SOURCE/dispatch-job.sh"
  "$FRONTEND_SOURCE/ultimate-3d-studio.js"
  "$FRONTEND_SOURCE/ultimate-3d-studio.css"
  "$FRONTEND_SOURCE/ultimate-3d-studio-build.json"
)
TARGETS=(
  "$LIVE_COMPONENT/slicer_nozzle_profiles.py"
  "$LIVE_COMPONENT/slicer_plate_views_v2.py"
  "$LIVE_COMPONENT/slicer_backend_router.py"
  "$LIVE_COMPONENT/dispatch-job-options.sh"
  "$LIVE_COMPONENT/materialize-bambu-multimaterial.py"
  "$LIVE_HOST/materialize-bambu-multimaterial.py"
  "$LIVE_HOST/server.py"
  "$LIVE_HOST/dispatch-job.sh"
  "$LIVE_FRONTEND/ultimate-3d-studio.js"
  "$LIVE_FRONTEND/ultimate-3d-studio.css"
  "$LIVE_FRONTEND/ultimate-3d-studio-build.json"
)
MODES=(0644 0644 0644 0755 0755 0755 0755 0755 0644 0644 0644)
HASHES=(
  bbe941384a719bea0bb8a844c61a4b12bf9a02a600604a1464b8e4d45c27dc59
  71d78fc6796e250fffe37b04fc9643659b8528f786f5dc8aa16e0d79be8d3e9a
  9c8f5cfca761578d639c083e4fdef80f4820ab24aa5a12e6fa3bbf6c931894c9
  fabb71bce88740f0ef48f4df8d37f584273c18360beecc639c2a53609fa7303b
  3b4072ec4972facbf9e9e973da8b58840c25cce946c0a39f40bc4f4d74f6222c
  3b4072ec4972facbf9e9e973da8b58840c25cce946c0a39f40bc4f4d74f6222c
  9318a8c9b211f5551c819ab5423bae5d498dd603fac66957b09d1b12db043d2f
  ec9c8e53911870a6ff3aec42ec2d81530395ef4bfd553e0d6249d8f6d3036d15
  43aef2104bafb83bab491b7490c2d203ea3a4b5c510029e356839e39a30be9ac
  0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
  713e3ed5bbe472324853a1c4e55ab685e59deed3c4e2bcbec787d3dd46e956ad
)

mkdir -p "$BACKUP"
: > "$MISSING"
exec > >(tee -a "$LOG") 2>&1

restore_timers() {
  if [[ $TIMERS_STOPPED -ne 1 ]]; then return 0; fi
  [[ ${DISPATCH_TIMER_WAS_ACTIVE:-inactive} == active ]] && systemctl start 3d-printer-slicing-dispatch.timer || true
  [[ ${REFRESH_TIMER_WAS_ACTIVE:-inactive} == active ]] && systemctl start 3d-printer-slicing-refresh.timer || true
  TIMERS_STOPPED=0
}

restore_files() {
  local index target saved temporary
  for index in "${!TARGETS[@]}"; do
    target=${TARGETS[$index]}
    saved=$BACKUP/live$target
    if [[ -f $saved ]]; then
      temporary=$target.v6-rollback.$$
      install -m "${MODES[$index]}" "$saved" "$temporary"
      mv -f "$temporary" "$target"
    elif grep -Fxq "$target" "$MISSING"; then
      rm -f "$target"
    fi
  done
}

finish_archive() {
  python3 - "$BACKUP" <<'PY' || true
import sys
import zipfile
from pathlib import Path
root = Path(sys.argv[1])
target = root.with_suffix(".zip")
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in root.rglob("*"):
        if path.is_file():
            archive.write(path, path.relative_to(root.parent))
print(target)
PY
  sha256sum "$BACKUP.zip" 2>/dev/null || true
}

rollback() {
  echo 'ROLLBACK: Wiederherstellung aus dem aktuellen Backup.'
  restore_files || true
  systemctl restart 3d-printer-slicing-server.service || true
  restore_timers
}

on_exit() {
  local code=$?
  trap - EXIT
  if [[ $SUCCESS -ne 1 && $DEPLOYED -eq 1 ]]; then rollback; fi
  restore_timers
  finish_archive
  exit "$code"
}
trap on_exit EXIT

echo 'V6 Düsen-/Schicht-/Wandsteuerung: kontrollierte Aktivierung'
echo "Quelle: $STAGE"
echo "Backup: $BACKUP"

[[ $EUID -eq 0 ]]
[[ -d $STAGE && -d $LIVE_COMPONENT && -d $LIVE_HOST && -d $LIVE_FRONTEND ]]
[[ ${#SOURCES[@]} -eq ${#TARGETS[@]} && ${#TARGETS[@]} -eq ${#HASHES[@]} ]]

echo '[1/9] Quellen und Prüfsummen prüfen'
for index in "${!SOURCES[@]}"; do
  [[ -f ${SOURCES[$index]} ]]
  actual=$(sha256sum "${SOURCES[$index]}" | awk '{print $1}')
  [[ $actual == "${HASHES[$index]}" ]]
done
[[ $(awk '$2=="server.py" {print $1}' "$HOST_SOURCE/SHA256SUMS") == 9318a8c9b211f5551c819ab5423bae5d498dd603fac66957b09d1b12db043d2f ]]
[[ $(awk '$2=="dispatch-job.sh" {print $1}' "$HOST_SOURCE/SHA256SUMS") == ec9c8e53911870a6ff3aec42ec2d81530395ef4bfd553e0d6249d8f6d3036d15 ]]
expected_dependency=$(awk '$2=="materialize-bambu-multimaterial.py" {print $1}' "$HOST_SOURCE/DEPENDENCY-SHA256SUMS")
[[ $expected_dependency == 3b4072ec4972facbf9e9e973da8b58840c25cce946c0a39f40bc4f4d74f6222c ]]

echo '[2/9] Syntax und JSON prüfen'
PYTHONDONTWRITEBYTECODE=1 python3 - <<PY
from pathlib import Path
for value in (
    "$COMPONENT/slicer_nozzle_profiles.py",
    "$COMPONENT/slicer_plate_views_v2.py",
    "$COMPONENT/slicer_backend_router.py",
    "$COMPONENT/materialize-bambu-multimaterial.py",
    "$HOST_SOURCE/server.py",
):
    path = Path(value)
    compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
PY
/bin/sh -n "$COMPONENT/dispatch-job-options.sh"
/bin/sh -n "$HOST_SOURCE/dispatch-job.sh"
jq -e . "$FRONTEND_SOURCE/ultimate-3d-studio-build.json" >/dev/null

echo '[3/9] Slicer-Leerlauf verifizieren und Timer sperren'
active=$(find "$LIVE_HOST/data/jobs" -maxdepth 1 -type f -name '*.slicing.json' | wc -l)
queued=$(find "$LIVE_HOST/data/jobs" -maxdepth 1 -type f -name '*.queued.json' | wc -l)
[[ $active -eq 0 && $queued -eq 0 && ! -d $LIVE_HOST/run/dispatcher.lock ]]
DISPATCH_TIMER_WAS_ACTIVE=$(systemctl is-active 3d-printer-slicing-dispatch.timer 2>/dev/null || true)
REFRESH_TIMER_WAS_ACTIVE=$(systemctl is-active 3d-printer-slicing-refresh.timer 2>/dev/null || true)
systemctl stop 3d-printer-slicing-dispatch.timer || true
systemctl stop 3d-printer-slicing-refresh.timer || true
TIMERS_STOPPED=1
active=$(find "$LIVE_HOST/data/jobs" -maxdepth 1 -type f -name '*.slicing.json' | wc -l)
queued=$(find "$LIVE_HOST/data/jobs" -maxdepth 1 -type f -name '*.queued.json' | wc -l)
[[ $active -eq 0 && $queued -eq 0 && ! -d $LIVE_HOST/run/dispatcher.lock ]]

echo '[4/9] Exaktes Live-Backup erstellen und zurücklesen'
for index in "${!TARGETS[@]}"; do
  target=${TARGETS[$index]}
  saved=$BACKUP/live$target
  mkdir -p "$(dirname "$saved")"
  if [[ -f $target ]]; then
    cp -a "$target" "$saved"
    cmp -s "$target" "$saved"
  else
    printf '%s\n' "$target" >> "$MISSING"
  fi
done
find "$BACKUP/live" -type f -print0 | sort -z | xargs -0 sha256sum > "$BACKUP/BACKUP-SHA256SUMS.txt"

echo '[5/9] Dateien atomar installieren'
DEPLOYED=1
for index in "${!SOURCES[@]}"; do
  source_file=${SOURCES[$index]}
  target=${TARGETS[$index]}
  temporary=$target.v6-new.$$
  install -m "${MODES[$index]}" "$source_file" "$temporary"
  mv -f "$temporary" "$target"
done

echo '[6/9] Live-Prüfsummen und Syntax prüfen'
for index in "${!TARGETS[@]}"; do
  actual=$(sha256sum "${TARGETS[$index]}" | awk '{print $1}')
  [[ $actual == "${HASHES[$index]}" ]]
done
PYTHONDONTWRITEBYTECODE=1 python3 - <<PY
from pathlib import Path
for value in (
    "$LIVE_COMPONENT/slicer_nozzle_profiles.py",
    "$LIVE_COMPONENT/slicer_plate_views_v2.py",
    "$LIVE_COMPONENT/slicer_backend_router.py",
    "$LIVE_COMPONENT/materialize-bambu-multimaterial.py",
    "$LIVE_HOST/server.py",
):
    path = Path(value)
    compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
PY
/bin/sh -n "$LIVE_HOST/dispatch-job.sh"
/bin/sh -n "$LIVE_COMPONENT/dispatch-job-options.sh"
for relative in server.py dispatch-job.sh progress-pipe-reader.py refresh-state.sh append-slicing-journal.sh; do
  expected=$(awk -v name="$relative" '$2==name {print $1}' "$HOST_SOURCE/SHA256SUMS")
  [[ -n $expected ]]
  [[ $(sha256sum "$LIVE_HOST/$relative" | awk '{print $1}') == "$expected" ]]
done
(cd "$LIVE_HOST" && sha256sum -c "$HOST_SOURCE/DEPENDENCY-SHA256SUMS")

echo '[7/9] Nativen Slicer neu starten und read-only verifizieren'
systemctl restart 3d-printer-slicing-server.service
token=$(jq -r '.token // empty' "$LIVE_HOST/config.json")
info=''
for _ in $(seq 1 30); do
  info=$(curl -fsS -H "Authorization: Bearer $token" http://127.0.0.1:8099/api/v1/info 2>/dev/null || true)
  [[ -n $info ]] && break
  sleep 1
done
printf '%s' "$info" | jq -e '.version=="0.1.0-alpha5" and .api_version==2 and .status=="ready"' >/dev/null

echo '[8/9] Home Assistant Core-Vorstatus prüfen'
[[ $(docker inspect -f '{{.State.Running}}' homeassistant 2>/dev/null) == true ]]

echo '[9/9] Timer und Abschlusszustand verifizieren'
restore_timers
[[ $(systemctl is-active 3d-printer-slicing-server.service) == active ]]
active=$(find "$LIVE_HOST/data/jobs" -maxdepth 1 -type f -name '*.slicing.json' | wc -l)
queued=$(find "$LIVE_HOST/data/jobs" -maxdepth 1 -type f -name '*.queued.json' | wc -l)
[[ $active -eq 0 && $queued -eq 0 ]]

SUCCESS=1
echo 'AKTIVIERUNG ERFOLGREICH'
echo 'Kein Slice und kein Druck wurde gestartet.'
echo 'Home Assistant Core muss anschließend separat einmal neu gestartet werden.'