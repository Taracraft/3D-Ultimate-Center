"""Fail-closed clean-host preflight for the Compose-only Slicer target.

The check is read-only.  It does not stop, disable, remove or migrate any native
service, process, path or container.  A non-empty or unprovable host blocks the
first Compose installation.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys

UNIT_NAMES = (
    "ultimate-slicer-server.service",
    "ultimate-slicer-dispatch.service",
    "ultimate-slicer-dispatch.timer",
    "ultimate-slicer-refresh.service",
    "ultimate-slicer-refresh.timer",
    "3d-printer-slicing-server.service",
    "3d-printer-slicing-dispatch.service",
    "3d-printer-slicing-dispatch.timer",
    "3d-printer-slicing-refresh.service",
    "3d-printer-slicing-refresh.timer",
)
MARKERS = (
    "opt/ultimate-slicer-server/server.py",
    "etc/ultimate-slicer-server/config.json",
    "etc/systemd/system/ultimate-slicer-server.service",
    "etc/systemd/system/3d-printer-slicing-server.service",
    "mnt/homeassist-data/workspaces/root-environment/3d-printer-slicing-server/server.py",
)
PROCESS_MARKERS = (
    b"/opt/ultimate-slicer-server/server.py",
    b"3d-printer-slicing-server",
    b"/3d-printer-slicing-server/server.py",
)
CONTAINER_MARKERS = (
    "ultimate-slicer",
    "3d-printer-slicing",
)
MAX_OUTPUT = 128 * 1024
MAX_PROCESSES = 32768


class HostExclusivityError(RuntimeError):
    """Stable error code without paths, process arguments or command output."""


@dataclass(frozen=True)
class Result:
    returncode: int
    stdout: bytes
    stderr: bytes


def _default_runner(argv, *, timeout):
    completed = subprocess.run(
        argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout, check=False, shell=False)
    if len(completed.stdout) > MAX_OUTPUT or len(completed.stderr) > MAX_OUTPUT:
        raise HostExclusivityError("host_inventory_output_too_large")
    return Result(completed.returncode, completed.stdout, completed.stderr)


class CleanHostPreflight:
    """Inspect fixed native/container markers and require an empty target host."""

    def __init__(self, *, root=Path("/"), process_root=Path("/proc"), runner=None):
        self.root = Path(root)
        self.process_root = Path(process_root)
        self.runner = _default_runner if runner is None else runner
        if not self.root.is_absolute() or not self.process_root.is_absolute():
            raise HostExclusivityError("invalid_inventory_root")
        if not callable(self.runner):
            raise HostExclusivityError("missing_inventory_runner")

    def _run(self, argv, allowed):
        try:
            result = self.runner(tuple(argv), timeout=15)
        except HostExclusivityError:
            raise
        except Exception as exc:
            raise HostExclusivityError("host_inventory_unknown") from exc
        if (type(result.returncode) is not int or type(result.stdout) is not bytes
                or type(result.stderr) is not bytes
                or len(result.stdout) > MAX_OUTPUT or len(result.stderr) > MAX_OUTPUT
                or result.returncode not in allowed):
            raise HostExclusivityError("host_inventory_unknown")
        return result

    def _units(self):
        found = []
        for unit in UNIT_NAMES:
            result = self._run(
                ("systemctl", "show", "--property=LoadState", "--property=ActiveState",
                 "--value", unit), (0, 4))
            values = result.stdout.decode("utf-8", "strict").splitlines()
            if result.returncode == 0 and values and values[0].strip() != "not-found":
                found.append(unit)
            elif result.returncode not in (0, 4):
                raise HostExclusivityError("host_inventory_unknown")
        return found

    def _paths(self):
        return [item for item in MARKERS if (self.root / item).exists()]

    def _processes(self):
        if not self.process_root.is_dir():
            raise HostExclusivityError("host_inventory_unknown")
        found = []
        count = 0
        for entry in self.process_root.iterdir():
            if not entry.name.isdecimal():
                continue
            count += 1
            if count > MAX_PROCESSES:
                raise HostExclusivityError("host_inventory_unknown")
            try:
                value = (entry / "cmdline").read_bytes()[:4097]
            except (FileNotFoundError, ProcessLookupError):
                continue
            except PermissionError as exc:
                raise HostExclusivityError("host_inventory_unknown") from exc
            if len(value) > 4096:
                raise HostExclusivityError("host_inventory_unknown")
            if any(marker in value for marker in PROCESS_MARKERS):
                found.append(entry.name)
        return found

    def _containers(self):
        result = self._run(
            ("docker", "container", "ls", "-a", "--format", "{{json .}}"), (0,))
        found = []
        for index, raw in enumerate(result.stdout.splitlines()):
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise HostExclusivityError("host_inventory_unknown") from exc
            if type(row) is not dict:
                raise HostExclusivityError("host_inventory_unknown")
            text = " ".join(str(row.get(key, "")) for key in
                            ("Names", "Image", "Labels")).lower()
            if any(marker in text for marker in CONTAINER_MARKERS):
                found.append(str(index))
        return found

    def inspect(self):
        if sys.platform != "linux":
            raise HostExclusivityError("linux_host_required")
        evidence = {
            "schema": 1,
            "native_units": self._units(),
            "native_paths": self._paths(),
            "native_processes": self._processes(),
            "slicer_containers": self._containers(),
        }
        evidence["clean"] = not any(evidence[key] for key in (
            "native_units", "native_paths", "native_processes", "slicer_containers"))
        return evidence

    def require_clean(self):
        evidence = self.inspect()
        if evidence["native_units"] or evidence["native_paths"] or evidence["native_processes"]:
            raise HostExclusivityError("native_slicer_present")
        if evidence["slicer_containers"]:
            raise HostExclusivityError("container_slicer_present")
        if evidence["clean"] is not True:
            raise HostExclusivityError("host_inventory_unknown")
        return True


def main():
    """CLI for the MCP-free Linux test host; output contains counts only."""
    try:
        evidence = CleanHostPreflight().inspect()
    except HostExclusivityError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2
    summary = {
        "ok": evidence["clean"] is True,
        "schema": evidence["schema"],
        "native_units": len(evidence["native_units"]),
        "native_paths": len(evidence["native_paths"]),
        "native_processes": len(evidence["native_processes"]),
        "slicer_containers": len(evidence["slicer_containers"]),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
