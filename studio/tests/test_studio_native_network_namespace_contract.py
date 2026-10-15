"""Network-isolation guard for native unprivileged slicing.

Offline source-contract tests only. Never launches a slicing engine or systemd.
An isolated Debian kernel/user-namespace integration test remains mandatory.
"""
from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WORKER = (
    ROOT / "deploy" / "homeassistant" / "host"
    / "3d-printer-slicing-server" / "dispatch-job.sh"
)
NATIVE_DISPATCH = (
    ROOT / "packages" / "ultimate-slicer-server" / "systemd"
    / "ultimate-slicer-dispatch.service"
)


def test_rootless_dispatch_uses_separate_user_and_network_namespaces():
    shell = WORKER.read_text(encoding="utf-8")
    assert "CODE_ROOT=${STUDIO_WORKER_SOURCE_ROOT:-$BASE}" in shell
    assert "studio_slicer_network_isolated() {" in shell
    assert "STUDIO_EFFECTIVE_UID=$(/usr/bin/id -u) || return 126" in shell
    assert '0) unshare --net -- "$@" ;;' in shell
    assert '*) unshare --user --map-root-user --net -- "$@" ;;' in shell
    assert "''|*[!0-9]*) return 126 ;;" in shell
    # No retry without network isolation is permissible when userns is denied.
    function = shell.split("studio_slicer_network_isolated() {", 1)[1].split("\n}", 1)[0]
    assert "|| true" not in function
    assert "--map-root-user --net --" in function
    assert "STUDIO_DISPATCH_MANAGED" in shell


def test_all_five_engine_execution_paths_use_isolation_wrapper():
    shell = WORKER.read_text(encoding="utf-8")
    calls = re.findall(r"(?m)^\s+studio_slicer_network_isolated\s+(.*)$", shell)
    assert len(calls) == 5, "each supported slicer execution path must be guarded"
    assert sum(item.startswith("env \\") for item in calls) == 2
    assert sum(item.startswith('"$BINARY" ') for item in calls) == 3
    assert not re.search(r"(?m)^\s+(?:unshare\s+--net\s+--|\"\$BINARY\"\s+--slice)", shell)
    assert "unshare --net -- \"$@\"" in shell  # privileged legacy invocation retained


def test_native_dispatcher_has_no_sandbox_privilege_escalation_fallback():
    unit = NATIVE_DISPATCH.read_text(encoding="utf-8")
    assert "User=ultimate-slicer" in unit
    assert "Group=ultimate-slicer" in unit
    assert "NoNewPrivileges=yes" in unit
    assert "ProtectSystem=strict" in unit
    assert "STUDIO_WORKER_SOURCE_ROOT=/opt/ultimate-slicer-server" in unit
    assert "STUDIO_WORKER_BASE=/var/lib/ultimate-slicer-server" in unit
    assert "User=root" not in unit
