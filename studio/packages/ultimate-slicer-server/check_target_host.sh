#!/usr/bin/env bash
# Read-only acceptance on an independent Linux machine.
# NO apt, useradd, systemctl start/enable, installations, printer or slicing jobs.
set -euo pipefail
umask 077
cd -- "$(dirname -- "$0")"

if [ "$(id -u)" -eq 0 ]; then
  printf 'STOP: run this first-pass preflight as a normal SSH user, not root.\n' >&2
  exit 2
fi
for program in python3 sha256sum systemd-analyze stat uname; do
  if ! command -v "$program" >/dev/null 2>&1; then
    printf 'STOP: required diagnostic tool missing: %s\n' "$program" >&2
    exit 3
  fi
done
test -f SHA256SUMS || { printf 'STOP: kit SHA256SUMS missing\n' >&2; exit 4; }
test -f native-source.tar.gz || { printf 'STOP: native source archive missing\n' >&2; exit 4; }
test -f packages/ultimate-slicer-server/install_native.py || { printf 'STOP: inspector missing\n' >&2; exit 4; }
printf '===== Native Slicer isolated work-host preflight =====\n'
printf 'INSTALLATION_PERFORMED=false\n'
printf 'SERVICE_CHANGES=false\n'
printf 'ENGINE_OR_PRINTER_COMMANDS=false\n'
printf 'SYSTEM_ARCH=%s\n' "$(uname -m)"
if [ -r /etc/os-release ]; then
  os_id="$(grep -E '^ID=' /etc/os-release | head -n1 | cut -d= -f2- | tr -d '"')" || true
  version_id="$(grep -E '^VERSION_ID=' /etc/os-release | head -n1 | cut -d= -f2- | tr -d '"')" || true
  printf 'OS_ID=%s\nOS_VERSION_ID=%s\n' "$os_id" "$version_id"
fi

printf 'KIT_SHA256_CHECK='
sha256sum -c --status SHA256SUMS || { printf 'FAILED\n' >&2; exit 5; }
printf 'PASS\n'

printf 'NATIVE_COMMAND_PRESENCE_CHECK='
missing=0
for program in python3 jq awk grep find sort head tail cut tr du id unshare systemctl useradd userdel mkfifo cp chmod mkdir mv rm sleep wc date; do
  if ! command -v "$program" >/dev/null 2>&1; then
    printf '\nMISSING_NATIVE_RUNTIME_COMMAND=%s\n' "$program"
    missing=$((missing + 1))
  fi
done
if [ "$missing" -gt 0 ]; then
  printf 'FAILED (%s missing commands)\n' "$missing"
  exit 6
fi
printf 'PASS\n'

printf 'NATIVE_DEPENDENCY_CHECK='
python3 packages/ultimate-slicer-server/install_native.py --check-host || { printf 'FAILED\n' >&2; exit 6; }
printf 'PASS\n'

archive_sha="$(sha256sum native-source.tar.gz | cut -d' ' -f1)"
printf 'NATIVE_BUNDLE_CHECK='
python3 packages/ultimate-slicer-server/install_native.py \
  --archive native-source.tar.gz \
  --archive-sha256 "$archive_sha" || { printf 'FAILED\n' >&2; exit 7; }
printf 'PASS\n'

printf 'NATIVE_UNIT_STATIC_CHECK='
unit_log="$(mktemp -t studio-native-units.XXXXXX)"
trap 'rm -f -- "$unit_log"' EXIT
if systemd-analyze verify \
  units/ultimate-slicer-server.service \
  units/ultimate-slicer-dispatch.service \
  units/ultimate-slicer-dispatch.timer \
  units/ultimate-slicer-refresh.service \
  units/ultimate-slicer-refresh.timer >"$unit_log" 2>&1; then
  printf 'PASS\n'
else
  # Fresh hosts can legitimately lack /opt/ultimate-slicer-server executable
  # files. Report the warning; this never authorizes installation.
  printf 'REQUIRES_RECHECK_AFTER_INSTALL\n'
  sed -n '1,8p' "$unit_log"
fi

occupied=0
for target in \
  /opt/ultimate-slicer-server \
  /etc/ultimate-slicer-server \
  /var/lib/ultimate-slicer-server \
  /etc/systemd/system/ultimate-slicer-server.service \
  /etc/systemd/system/ultimate-slicer-dispatch.service \
  /etc/systemd/system/ultimate-slicer-dispatch.timer \
  /etc/systemd/system/ultimate-slicer-refresh.service \
  /etc/systemd/system/ultimate-slicer-refresh.timer; do
  if [ -e "$target" ] || [ -L "$target" ]; then
    occupied=$((occupied + 1))
  fi
done
printf 'NATIVE_INSTALL_TARGETS_ALREADY_OCCUPIED=%s\n' "$occupied"
printf 'BUNDLE_DEPLOY_APPROVED=false\n'
printf 'READ_ONLY_PRECHECK=PASS\n'
if [ "$occupied" -ne 0 ]; then
  printf 'STOP: native target is not empty; first-install must not run.\n' >&2
  exit 9
fi
