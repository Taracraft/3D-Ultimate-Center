"""Isolated native Linux filesystem acceptance: no systemd or printer side effects.

Run only in a disposable Linux context as root:
  python3 tests/native_linux_install_sandbox.py

All program/config/data/systemd targets are monkeypatched to a freshly
created temporary directory. Actual Unix modes, ownership and renames are
exercised. Service-management and OS-account calls are intercepted.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / "packages" / "ultimate-slicer-server" / "install_native.py"


def ensure(condition: bool, detail: str) -> None:
    if not condition:
        raise AssertionError(detail)


def run() -> None:
    if sys.platform != "linux" or os.geteuid() != 0:
        raise SystemExit("isolated native test requires Linux root")
    spec = importlib.util.spec_from_file_location("isolated_native_installer", SOURCE)
    ensure(spec is not None and spec.loader is not None, "native installer missing")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)

    with tempfile.TemporaryDirectory(prefix="studio-native-fs-check-") as work:
        scope = Path(work)
        roots = (
            scope / "opt" / "ultimate-slicer-server",
            scope / "etc" / "ultimate-slicer-server",
            scope / "var" / "lib" / "ultimate-slicer-server",
            scope / "etc" / "systemd" / "system",
        )
        for parent in (roots[0].parent, roots[1].parent, roots[2].parent, roots[3]):
            parent.mkdir(parents=True, exist_ok=True)
        backups = scope / "opt" / ".ultimate-slicer-server-backups"
        installer.installation_roots = lambda: roots
        installer.upgrade_backup_root = lambda: backups
        installer.require_unprivileged_network_namespace = lambda: None

        # Only the two service-manager actions used by install/upgrade are allowed.
        # No host systemctl, useradd, userdel, print or slicing process is invoked.
        calls: list[tuple[str, ...]] = []
        original_run = subprocess.run
        import pwd
        import grp
        original_user = pwd.getpwnam
        original_group = grp.getgrnam
        def fake_run(command: list[str], **kwargs):
            values = tuple(command)
            calls.append(values)
            if values == ("systemctl", "daemon-reload"):
                return SimpleNamespace(returncode=0)
            if values[:2] == ("systemctl", "is-active"):
                return SimpleNamespace(returncode=3, stdout="inactive\n")
            raise AssertionError("UNEXPECTED HOST OPERATION BLOCKED")

        try:
            subprocess.run = fake_run
            pwd.getpwnam = lambda _name: SimpleNamespace(pw_uid=65534, pw_gid=65534)
            grp.getgrnam = lambda _name: SimpleNamespace(gr_gid=65534)

            engine = scope / "external-engine"
            binary = engine / "bin" / "bambu-studio"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"\x7fELF" + b"only-mock-executable-never-run")
            binary.chmod(0o755)
            engine_paths = [binary]
            for group in ("machine", "process", "filament"):
                target = engine / "resources" / "profiles" / "BBL" / group / "synthetic.json"
                target.parent.mkdir(parents=True)
                target.write_text('{"fixture":"do-not-print"}', encoding="utf-8")
                engine_paths.append(target)
            engine_manifest = scope / "engine-SHA256SUMS"
            engine_manifest.write_text(
                "".join(
                    installer.hash_file(p) + "  " + p.relative_to(engine).as_posix() + "\n"
                    for p in engine_paths
                ),
                encoding="utf-8",
            )
            engine_files = installer.verify_engine(engine, engine_manifest)

            checked_files = {
                "payload/server.py": b"synthetic-native-server-no-runtime-actions",
                "payload/job_control.py": b"synthetic-native-job-supervisor",
                "payload/dispatch-job.sh": b"#!/bin/sh\nexit 0\n",
            }
            for unit in installer.UNITS:
                checked_files[f"systemd/{unit}"] = (
                    "User=ultimate-slicer\nProtectSystem=strict\nNoNewPrivileges=yes\n"
                ).encode("ascii")
            old_archive = hashlib.sha256(b"old-source-fixture").hexdigest()
            installed = installer.install_first_time(checked_files, old_archive, engine_files)
            code, config, state, systemd_dir = roots
            ensure(installed["installed"], "first install did not complete")
            secret_path = config / "config.json"
            ensure(stat.S_IMODE(secret_path.stat().st_mode) == 0o640, "secret file not mode 0640")
            ensure(secret_path.stat().st_uid == 0, "secret not root-owned")
            ensure(secret_path.stat().st_gid == 65534, "secret has wrong dedicated group")
            ensure(stat.S_IMODE(config.stat().st_mode) == 0o750, "config directory mode unsafe")
            ensure(stat.S_IMODE(state.stat().st_mode) == 0o750, "state directory mode unsafe")
            ensure(state.stat().st_uid == 65534, "state not dedicated-service-owned")
            ensure((code / "server.py").read_bytes() == checked_files["payload/server.py"], "installed payload wrong")
            ensure((code / "engines" / "bambu-studio" / "squashfs-root" / "bin" / "bambu-studio").is_file(), "engine not copied")
            ensure({p.name for p in systemd_dir.iterdir()} == installer.UNITS, "unexpected installed units")

            # Persisted job and secret must be bit-for-bit unchanged.
            queued = state / "data" / "jobs"
            queued.mkdir(parents=True)
            history = queued / "historical.completed.json"
            history.write_bytes(b'{"status":"completed","keep":"yes"}')
            secret_before = secret_path.read_bytes()

            same = installer.upgrade_stopped_native_server(checked_files, old_archive, engine_files)
            ensure(same["unchanged"] and not same["backup_created"], "identical code upgrade is not no-op")
            ensure(not backups.exists(), "no-op created unwanted backup")
            replacement = dict(checked_files)
            replacement["payload/server.py"] = b"synthetic-changed-native-server"
            changed = installer.upgrade_stopped_native_server(replacement, old_archive, engine_files)
            ensure(changed["upgraded"], "code-only upgrade failed")
            previous = Path(changed["previous_code_backup"])
            ensure(previous.read_bytes() if previous.is_file() else (previous / "server.py").read_bytes() == checked_files["payload/server.py"], "previous code backup invalid")
            ensure(stat.S_IMODE(previous.parent.stat().st_mode) == 0o700, "backup directory not private")
            ensure(secret_path.read_bytes() == secret_before, "code-only upgrade modified secret")
            ensure(history.read_bytes() == b'{"status":"completed","keep":"yes"}', "upgrade modified job history")
            restored = installer.restore_stopped_native_code(previous)
            ensure(restored["restored"], "rollback refused valid private backup")
            ensure((code / "server.py").read_bytes() == checked_files["payload/server.py"], "rollback not byte-identical")
            ensure((Path(restored["replaced_code_backup"]) / "server.py").read_bytes() == replacement["payload/server.py"], "new code not retained")
            ensure(secret_path.read_bytes() == secret_before, "restore modified credentials")
            ensure(history.read_bytes() == b'{"status":"completed","keep":"yes"}', "restore modified history")
            ensure({p.name for p in systemd_dir.iterdir()} == installer.UNITS, "restore modified systemd units")
            ensure(all(op[0] == "systemctl" and op[1] in {"daemon-reload", "is-active"} for op in calls), "unexpected service action")
            print("NATIVE_LINUX_ISOLATED_FIRST_INSTALL=PASS")
            print("NATIVE_LINUX_POSIX_FILE_MODES=PASS")
            print("NATIVE_LINUX_IDEMPOTENT_UPGRADE=PASS")
            print("NATIVE_LINUX_ATOMIC_UPGRADE_AND_RESTORE=PASS")
            print("NATIVE_LINUX_SECRET_AND_HISTORY_PRESERVED=PASS")
            print("NO_REAL_SYSTEMD_PRINTER_OR_SLICING_ACTIONS=true")
        finally:
            subprocess.run = original_run
            pwd.getpwnam = original_user
            grp.getgrnam = original_group


if __name__ == "__main__":
    run()
