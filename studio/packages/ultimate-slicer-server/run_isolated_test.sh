#!/usr/bin/env bash
# Opt-in: genuine Linux filesystem semantics in temporary directories only.
# OS-account operations, systemctl calls and printer/slicer execution mocked.
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [ "$(id -u)" -ne 0 ]; then
  printf 'STOP: isolated filesystem acceptance requires explicit root.\n' >&2
  printf 'Run ONLY after inspecting the included Python test source.\n' >&2
  exit 2
fi
sha256sum -c --status SHA256SUMS || { printf 'STOP: kit checksum mismatch\n' >&2; exit 3; }
python3 tests/native_linux_install_sandbox.py
printf 'ISOLATED_FILESYSTEM_TEST=PASS\n'
printf 'PERMANENT_INSTALLATION_PERFORMED=false\n'
printf 'PRINTER_AND_SLICING_ACTIONS=false\n'