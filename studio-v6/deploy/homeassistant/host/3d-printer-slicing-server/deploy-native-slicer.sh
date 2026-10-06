#!/bin/bash

set -u

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_BASE="/var/lib/homeassistant/3d-printer-slicing-server"
UNIT_DIR="/etc/systemd/system"
TODAY="$(date +%Y%m%d)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$TARGET_BASE/backups/$STAMP-v6-native-deploy"
LOG_DIR="$TARGET_BASE/deploy-logs"
LOG_FILE="$LOG_DIR/$STAMP-v6-native-deploy.log"
BACKUP_META="$BACKUP_DIR/BACKUP-META.txt"
MISSING_BEFORE="$BACKUP_DIR/MISSING-BEFORE.txt"
TIMERS_STOPPED=0
CHANGED=0
SERVER_RESTART_NEEDED=0
UNITS_CHANGED=0

RUNTIME_FILES=(
  bambu_lab_h2s_04.json
  server.py
  job_control.py
  dispatch-job.sh
  progress-pipe-reader.py
  refresh-state.sh
  append-slicing-journal.sh
)
UNIT_FILES=(
  3d-printer-slicing-server.service
  3d-printer-slicing-dispatch.service
  3d-printer-slicing-dispatch.timer
  3d-printer-slicing-refresh.service
  3d-printer-slicing-refresh.timer
)

mkdir -p "$LOG_DIR" || exit 1
exec > >(tee -a "$LOG_FILE") 2>&1

say() {
  printf '%s\n' "$*"
}

fail() {
  say "FEHLER: $*"
  return 1
}

# Only the packaged supervisor is a deploy-owned dependency. All other
# dependencies must already match the reviewed native contract in the target.
verify_dependencies() {
  local phase="$1" expected file extra target actual seen=" " saw_supervisor=0
  if [ ! -s "$SOURCE_DIR/DEPENDENCY-SHA256SUMS" ]; then
    fail "DEPENDENCY-SHA256SUMS fehlt oder ist leer."
    return 1
  fi
  while read -r expected file extra; do
    [ -n "${expected:-}${file:-}${extra:-}" ] || continue
    if [[ ! "$expected" =~ ^[0-9a-f]{64}$ ]] ||
       [[ ! "${file:-}" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] ||
       [ -n "${extra:-}" ] || [[ "$seen" == *" $file "* ]]; then
      fail "Ungültiger oder doppelter Eintrag im Abhängigkeitsmanifest."
      return 1
    fi
    seen+="$file "
    target="$TARGET_BASE/$file"
    if [ "$file" = "job_control.py" ]; then
      saw_supervisor=1
      [ "$phase" = "source" ] && target="$SOURCE_DIR/$file"
    fi
    if [ ! -f "$target" ] || [ -L "$target" ]; then
      fail "Native-Abhängigkeit fehlt oder ist verknüpft: $file"
      return 1
    fi
    actual="$(sha256sum "$target" | awk '{print $1}')"
    if [ "$actual" != "$expected" ]; then
      fail "Native-Abhängigkeit weicht vom geprüften Stand ab: $file"
      return 1
    fi
  done < "$SOURCE_DIR/DEPENDENCY-SHA256SUMS"
  if [ "$saw_supervisor" -ne 1 ]; then
    fail "Der native Supervisor job_control.py fehlt im Abhängigkeitsmanifest."
    return 1
  fi
}

verify_live_hashes() {
  local file expected actual
  for file in "${RUNTIME_FILES[@]}"; do
    if [ ! -f "$TARGET_BASE/$file" ] || [ -L "$TARGET_BASE/$file" ]; then
      fail "Installierte Runtime-Datei fehlt oder ist verknüpft: $file"
      return 1
    fi
    expected="$(sha256sum "$SOURCE_DIR/$file" | awk '{print $1}')"
    actual="$(sha256sum "$TARGET_BASE/$file" | awk '{print $1}')"
    if [ "$expected" != "$actual" ]; then
      fail "Live-SHA-Prüfung fehlgeschlagen: runtime/$file"
      return 1
    fi
  done
  for file in "${UNIT_FILES[@]}"; do
    if [ ! -f "$UNIT_DIR/$file" ] || [ -L "$UNIT_DIR/$file" ]; then
      fail "Installierte Unit fehlt oder ist verknüpft: $file"
      return 1
    fi
    expected="$(sha256sum "$SOURCE_DIR/systemd/$file" | awk '{print $1}')"
    actual="$(sha256sum "$UNIT_DIR/$file" | awk '{print $1}')"
    if [ "$expected" != "$actual" ]; then
      fail "Live-SHA-Prüfung fehlgeschlagen: systemd/$file"
      return 1
    fi
  done
  verify_dependencies live
}

restore_timers() {
  if [ "$TIMERS_STOPPED" -ne 1 ]; then
    return 0
  fi
  if [ "${DISPATCH_TIMER_WAS_ACTIVE:-inactive}" = "active" ]; then
    systemctl start 3d-printer-slicing-dispatch.timer >/dev/null 2>&1 || true
  fi
  if [ "${REFRESH_TIMER_WAS_ACTIVE:-inactive}" = "active" ]; then
    systemctl start 3d-printer-slicing-refresh.timer >/dev/null 2>&1 || true
  fi
  TIMERS_STOPPED=0
}

rollback() {
  say "Rollback aus heutigem Backup: $BACKUP_DIR"
  if [ ! -d "$BACKUP_DIR" ] || [ "$(basename "$BACKUP_DIR" | cut -c1-8)" != "$TODAY" ]; then
    say "FEHLER: Backup ist nicht eindeutig von heute. Automatischer Rollback verweigert."
    restore_timers
    return 1
  fi
  if [ ! -s "$BACKUP_META" ] || ! grep -q "^created_date=$TODAY$" "$BACKUP_META"; then
    say "FEHLER: Backup-Metadaten sind ungültig. Automatischer Rollback verweigert."
    restore_timers
    return 1
  fi

  for file in "${RUNTIME_FILES[@]}"; do
    if [ -f "$BACKUP_DIR/runtime/$file" ]; then
      install -m 0755 "$BACKUP_DIR/runtime/$file" "$TARGET_BASE/.rollback-$file.$$" || continue
      mv -f "$TARGET_BASE/.rollback-$file.$$" "$TARGET_BASE/$file"
    elif grep -Fxq "runtime/$file" "$MISSING_BEFORE" 2>/dev/null; then
      rm -f "$TARGET_BASE/$file"
    fi
  done
  for unit in "${UNIT_FILES[@]}"; do
    if [ -f "$BACKUP_DIR/systemd/$unit" ]; then
      install -m 0644 "$BACKUP_DIR/systemd/$unit" "$UNIT_DIR/.rollback-$unit.$$" || continue
      mv -f "$UNIT_DIR/.rollback-$unit.$$" "$UNIT_DIR/$unit"
    elif grep -Fxq "systemd/$unit" "$MISSING_BEFORE" 2>/dev/null; then
      rm -f "$UNIT_DIR/$unit"
    fi
  done
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl restart 3d-printer-slicing-server.service >/dev/null 2>&1 || true
  restore_timers
  say "Rollback wurde ausgeführt."
  return 0
}

finish_log_archive() {
  local zip_path="$LOG_DIR/$STAMP-v6-native-deploy.zip"
  python3 - "$zip_path" "$LOG_FILE" "$BACKUP_META" <<'PY' >/dev/null 2>&1 || true
import sys
import zipfile
from pathlib import Path
zip_path = Path(sys.argv[1])
files = [Path(value) for value in sys.argv[2:]]
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in files:
        if path.is_file():
            archive.write(path, arcname=path.name)
PY
  if [ -f "$zip_path" ]; then
    say "Log-ZIP: $zip_path"
    sha256sum "$zip_path" || true
  fi
}

say "======================================================================"
say " V6 Native Slicer – kontrolliertes Deployment"
say "======================================================================"
say "Quelle: $SOURCE_DIR"
say "Ziel:   $TARGET_BASE"
say "Datum:  $TODAY"
say ""

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  fail "Dieses Deployment muss als root ausgeführt werden."
  finish_log_archive
  exit 1
fi

for command in sha256sum python3 jq curl systemctl install cmp find; do
  if ! command -v "$command" >/dev/null 2>&1; then
    fail "Erforderlicher Befehl fehlt: $command"
    finish_log_archive
    exit 1
  fi
done

if [ -e "$SOURCE_DIR/config.json" ] || [ -d "$SOURCE_DIR/data" ] || [ -d "$SOURCE_DIR/engines" ]; then
  fail "Das Quellpaket enthält Runtime-Daten oder Geheimnisse und wird nicht deployt."
  finish_log_archive
  exit 1
fi

if [ ! -f "$SOURCE_DIR/SHA256SUMS" ]; then
  fail "SHA256SUMS fehlt."
  finish_log_archive
  exit 1
fi

say "[1/8] Quellhashes prüfen"
if ! (cd "$SOURCE_DIR" && sha256sum -c SHA256SUMS); then
  fail "Quellhashprüfung fehlgeschlagen."
  finish_log_archive
  exit 1
fi

say "[2/8] Syntax prüfen"
if ! python3 - "$SOURCE_DIR/server.py" "$SOURCE_DIR/job_control.py" "$SOURCE_DIR/progress-pipe-reader.py" <<'PY'
import sys
from pathlib import Path
for value in sys.argv[1:]:
    path = Path(value)
    compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
PY
then
  fail "Python-Syntaxprüfung fehlgeschlagen."
  finish_log_archive
  exit 1
fi
for file in dispatch-job.sh refresh-state.sh append-slicing-journal.sh; do
  if ! /bin/sh -n "$SOURCE_DIR/$file"; then
    fail "Shell-Syntaxprüfung fehlgeschlagen: $file"
    finish_log_archive
    exit 1
  fi
done

say "[3/8] Bestehende Native-Abhängigkeiten prüfen"
if ! verify_dependencies source; then
  finish_log_archive
  exit 1
fi

say "[4/8] Änderungen ermitteln"
for file in "${RUNTIME_FILES[@]}"; do
  if [ ! -f "$TARGET_BASE/$file" ] || ! cmp -s "$SOURCE_DIR/$file" "$TARGET_BASE/$file"; then
    CHANGED=1
    if [ "$file" = "server.py" ] || [ "$file" = "job_control.py" ]; then
      SERVER_RESTART_NEEDED=1
    fi
    say "Änderung: runtime/$file"
  fi
done
for unit in "${UNIT_FILES[@]}"; do
  if [ ! -f "$UNIT_DIR/$unit" ] || ! cmp -s "$SOURCE_DIR/systemd/$unit" "$UNIT_DIR/$unit"; then
    CHANGED=1
    UNITS_CHANGED=1
    [ "$unit" = "3d-printer-slicing-server.service" ] && SERVER_RESTART_NEEDED=1
    say "Änderung: systemd/$unit"
  fi
done

if [ "$CHANGED" -eq 0 ]; then
  say "Keine Dateiänderung erforderlich. Nur Health-Verifikation wird ausgeführt."
else
  ACTIVE="$(find "$TARGET_BASE/data/jobs" -maxdepth 1 -type f -name '*.slicing.json' 2>/dev/null | wc -l | tr -d '[:space:]')"
  QUEUED="$(find "$TARGET_BASE/data/jobs" -maxdepth 1 -type f -name '*.queued.json' 2>/dev/null | wc -l | tr -d '[:space:]')"
  if [ "${ACTIVE:-0}" -ne 0 ] || [ "${QUEUED:-0}" -ne 0 ]; then
    fail "Deployment gesperrt: active=$ACTIVE queued=$QUEUED"
    finish_log_archive
    exit 1
  fi
  if [ -d "$TARGET_BASE/run/dispatcher.lock" ]; then
    fail "Deployment gesperrt: Dispatcher-Lock ist aktiv."
    finish_log_archive
    exit 1
  fi

  say "[5/8] Dispatcher-/Refresh-Timer kontrolliert anhalten"
  DISPATCH_TIMER_WAS_ACTIVE="$(systemctl is-active 3d-printer-slicing-dispatch.timer 2>/dev/null || true)"
  REFRESH_TIMER_WAS_ACTIVE="$(systemctl is-active 3d-printer-slicing-refresh.timer 2>/dev/null || true)"
  systemctl stop 3d-printer-slicing-dispatch.timer 2>/dev/null || true
  systemctl stop 3d-printer-slicing-refresh.timer 2>/dev/null || true
  TIMERS_STOPPED=1

  ACTIVE="$(find "$TARGET_BASE/data/jobs" -maxdepth 1 -type f -name '*.slicing.json' 2>/dev/null | wc -l | tr -d '[:space:]')"
  QUEUED="$(find "$TARGET_BASE/data/jobs" -maxdepth 1 -type f -name '*.queued.json' 2>/dev/null | wc -l | tr -d '[:space:]')"
  if [ "${ACTIVE:-0}" -ne 0 ] || [ "${QUEUED:-0}" -ne 0 ] || [ -d "$TARGET_BASE/run/dispatcher.lock" ]; then
    fail "Zustand änderte sich während der Sperrphase; Deployment abgebrochen."
    restore_timers
    finish_log_archive
    exit 1
  fi

  say "[6/8] Same-Day-Backup erstellen und verifizieren"
  mkdir -p "$BACKUP_DIR/runtime" "$BACKUP_DIR/systemd" || {
    fail "Backup-Verzeichnis konnte nicht erstellt werden."
    restore_timers
    finish_log_archive
    exit 1
  }
  : > "$MISSING_BEFORE"
  {
    echo "created_at=$(date --iso-8601=seconds)"
    echo "created_date=$TODAY"
    echo "source_dir=$SOURCE_DIR"
    echo "target_base=$TARGET_BASE"
  } > "$BACKUP_META"

  for file in "${RUNTIME_FILES[@]}"; do
    if [ -f "$TARGET_BASE/$file" ]; then
      cp -a "$TARGET_BASE/$file" "$BACKUP_DIR/runtime/$file" || {
        fail "Backup fehlgeschlagen: runtime/$file"
        restore_timers
        finish_log_archive
        exit 1
      }
    else
      echo "runtime/$file" >> "$MISSING_BEFORE"
    fi
  done
  for unit in "${UNIT_FILES[@]}"; do
    if [ -f "$UNIT_DIR/$unit" ]; then
      cp -a "$UNIT_DIR/$unit" "$BACKUP_DIR/systemd/$unit" || {
        fail "Backup fehlgeschlagen: systemd/$unit"
        restore_timers
        finish_log_archive
        exit 1
      }
    else
      echo "systemd/$unit" >> "$MISSING_BEFORE"
    fi
  done
  find "$BACKUP_DIR/runtime" "$BACKUP_DIR/systemd" -type f -print0 | sort -z | xargs -0 sha256sum > "$BACKUP_DIR/SHA256SUMS.before"
  if [ "$(basename "$BACKUP_DIR" | cut -c1-8)" != "$TODAY" ] || ! grep -q "^created_date=$TODAY$" "$BACKUP_META"; then
    fail "Same-Day-Backup-Verifikation fehlgeschlagen."
    restore_timers
    finish_log_archive
    exit 1
  fi
  say "Backup: $BACKUP_DIR"
  sha256sum "$BACKUP_META" "$BACKUP_DIR/SHA256SUMS.before" || true

  say "[7/8] Dateien atomar installieren"
  for file in "${RUNTIME_FILES[@]}"; do
    if [ ! -f "$TARGET_BASE/$file" ] || ! cmp -s "$SOURCE_DIR/$file" "$TARGET_BASE/$file"; then
      install -m 0755 "$SOURCE_DIR/$file" "$TARGET_BASE/.v6-new-$file.$$" || {
        fail "Installation fehlgeschlagen: $file"
        rollback
        finish_log_archive
        exit 1
      }
      mv -f "$TARGET_BASE/.v6-new-$file.$$" "$TARGET_BASE/$file" || {
        fail "Atomarer Dateitausch fehlgeschlagen: $file"
        rollback
        finish_log_archive
        exit 1
      }
    fi
  done
  for unit in "${UNIT_FILES[@]}"; do
    if [ ! -f "$UNIT_DIR/$unit" ] || ! cmp -s "$SOURCE_DIR/systemd/$unit" "$UNIT_DIR/$unit"; then
      install -m 0644 "$SOURCE_DIR/systemd/$unit" "$UNIT_DIR/.v6-new-$unit.$$" || {
        fail "Unit-Installation fehlgeschlagen: $unit"
        rollback
        finish_log_archive
        exit 1
      }
      mv -f "$UNIT_DIR/.v6-new-$unit.$$" "$UNIT_DIR/$unit" || {
        fail "Atomarer Unit-Tausch fehlgeschlagen: $unit"
        rollback
        finish_log_archive
        exit 1
      }
    fi
  done

  if ! verify_live_hashes; then
    fail "Dateiprüfung vor dem Neustart fehlgeschlagen."
    rollback
    finish_log_archive
    exit 1
  fi

  if [ "$UNITS_CHANGED" -eq 1 ]; then
    systemctl daemon-reload || {
      fail "systemd daemon-reload fehlgeschlagen."
      rollback
      finish_log_archive
      exit 1
    }
  fi
  if [ "$SERVER_RESTART_NEEDED" -eq 1 ]; then
    systemctl restart 3d-printer-slicing-server.service || {
      fail "Slicing-Server-Neustart fehlgeschlagen."
      rollback
      finish_log_archive
      exit 1
    }
  fi
  /bin/sh "$TARGET_BASE/refresh-state.sh" >/dev/null 2>&1 || {
    fail "Status-Refresh fehlgeschlagen."
    rollback
    finish_log_archive
    exit 1
  }
fi

say "[8/8] API v2 / Telemetrie read-only verifizieren"
TOKEN="$(jq -r '.token // empty' "$TARGET_BASE/config.json" 2>/dev/null || true)"
AUTH_ARGS=()
if [ -n "$TOKEN" ]; then
  AUTH_ARGS=(-H "Authorization: Bearer $TOKEN")
fi
INFO=""
for _ in $(seq 1 30); do
  INFO="$(curl -fsS "${AUTH_ARGS[@]}" http://127.0.0.1:8099/api/v1/info 2>/dev/null || true)"
  if [ -n "$INFO" ]; then
    break
  fi
  sleep 1
done
CAPS="$(curl -fsS "${AUTH_ARGS[@]}" http://127.0.0.1:8099/api/v1/capabilities 2>/dev/null || true)"
if ! printf '%s' "$INFO" | jq -e '.version == "0.1.0-alpha5" and .api_version == 2 and .status == "ready"' >/dev/null 2>&1; then
  fail "Info-/Health-Verifikation fehlgeschlagen."
  [ "$CHANGED" -eq 1 ] && rollback
  finish_log_archive
  exit 1
fi
if ! printf '%s' "$CAPS" | jq -e '.live_progress == true and .progress_source == "bambu_cli_pipe" and .progress_history == true and .progress_eta == true and .job_detail == true and .engine_result == true and .runtime_summary == true' >/dev/null 2>&1; then
  fail "Capabilities-Verifikation fehlgeschlagen."
  [ "$CHANGED" -eq 1 ] && rollback
  finish_log_archive
  exit 1
fi

if ! verify_live_hashes; then
  fail "Abschließende Live-SHA-Prüfung fehlgeschlagen."
  [ "$CHANGED" -eq 1 ] && rollback
  finish_log_archive
  exit 1
fi

restore_timers
say ""
say "Deployment/Verifikation erfolgreich."
say "Kein Slice und kein Druck wurde gestartet."
say "Aktive/wartende Jobs vor Änderung: 0/0."
[ -d "$BACKUP_DIR" ] && say "Rollback-Backup: $BACKUP_DIR"
finish_log_archive
say "Terminal bleibt offen."
if [ -t 0 ] && [ "${V6_KEEP_SHELL_OPEN:-0}" = "1" ]; then
  exec /bin/bash
fi
exit 0
