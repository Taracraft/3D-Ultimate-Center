"""Static source/sandbox contract for rootless native engine execution.

No user namespace, engine binary, service or real slicing task is launched here.
Linux acceptance must independently test namespace support under the service user.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / "deploy/homeassistant/host/3d-printer-slicing-server/dispatch-job.sh"
NATIVE_UNIT = (
    ROOT / "packages/ultimate-slicer-server/systemd/ultimate-slicer-dispatch.service"
)


def test_privileged_legacy_and_rootless_native_paths_both_isolate_network():
    body = DISPATCH.read_text(encoding="utf-8")
    assert body.count("studio_slicer_network_isolated") == 6
    assert body.count("unshare --net --") == 1
    assert body.count("unshare --user --map-root-user --net --") == 1
    assert 'STUDIO_EFFECTIVE_UID=$(/usr/bin/id -u) || return 126' in body
    assert '0) unshare --net -- "$@" ;;' in body
    assert '*) unshare --user --map-root-user --net -- "$@" ;;' in body
    assert "STUDIO_WORKER_ROOTLESS" not in body
    assert "|| unshare" not in body
    assert "unshare --net -- env" not in body
    assert re.search(r"(?m)^\s+studio_slicer_network_isolated\s", body)
    assert "STUDIO_WORKER_SOURCE_ROOT:-$BASE" in body


def test_independent_dispatch_unit_drops_host_root_privileges():
    unit = NATIVE_UNIT.read_text(encoding="utf-8")
    assert "User=ultimate-slicer" in unit
    assert "Group=ultimate-slicer" in unit
    assert "NoNewPrivileges=yes" in unit
    assert "ExecStartPre=/usr/bin/unshare --user --map-root-user --net -- /usr/bin/true" in unit
    assert "ProtectSystem=strict" in unit
    assert "STUDIO_WORKER_SOURCE_ROOT=/opt/ultimate-slicer-server" in unit
    assert "STUDIO_WORKER_BASE=/var/lib/ultimate-slicer-server" in unit
    assert "User=root" not in unit
