"""Isolated first-install/rollback contract.

Runs actual installer code only against temporary test directories, mocks the
Linux identity/systemd boundary; never invokes host systemctl, root or a slicer.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "ultimate-slicer-server"


def load(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


builder = load("studio_transaction_builder", PACKAGE / "build_native_package.py")
installer = load("studio_transaction_installer", PACKAGE / "install_native.py")


@pytest.fixture
def installation_inputs(tmp_path):
    archive = tmp_path / "source.tar.gz"
    built = builder.build(ROOT, archive)
    _metadata, files = installer.inspect_bundle(archive, built["archive_sha256"])
    engine = tmp_path / "external-engine"
    binary = engine / "bin" / "bambu-studio"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"\x7fELF" + b"synthetic-do-not-execute")
    binary.chmod(0o755)
    names = [binary]
    for category in ("machine", "process", "filament"):
        path = engine / "resources" / "profiles" / "BBL" / category / "synthetic.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'{"test":"synthetic"}')
        names.append(path)
    return files, built["archive_sha256"], [
        (path.relative_to(engine).as_posix(), path, installer.hash_file(path))
        for path in names
    ]


@pytest.fixture
def isolated_root(monkeypatch, tmp_path):
    roots = (
        tmp_path / "opt" / "ultimate-slicer-server",
        tmp_path / "etc" / "ultimate-slicer-server",
        tmp_path / "var" / "lib" / "ultimate-slicer-server",
        tmp_path / "etc" / "systemd" / "system",
    )
    for parent in (roots[0].parent, roots[1].parent, roots[2].parent, roots[3]):
        parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(installer, "installation_roots", lambda: roots)
    monkeypatch.setattr(installer.sys, "platform", "linux")
    monkeypatch.setattr(installer.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(installer.os, "chown", lambda *_args: None, raising=False)
    pwd = types.ModuleType("pwd")
    grp = types.ModuleType("grp")
    pwd.getpwnam = lambda _name: types.SimpleNamespace(pw_uid=1099, pw_gid=1099)
    grp.getgrnam = lambda _name: types.SimpleNamespace(gr_gid=1099)
    monkeypatch.setitem(sys.modules, "pwd", pwd)
    monkeypatch.setitem(sys.modules, "grp", grp)

    actions = []
    failure = {"daemon_reload": False, "namespace": False, "backup_owner_uid": 0}
    real_stat = Path.stat
    backup_parent = roots[0].parent / ".private-native-code-backups"

    def synthetic_owner_stat(path, *args, **kwargs):
        details = real_stat(path, *args, **kwargs)
        if path != backup_parent:
            return details
        fields = list(details)
        fields[4] = failure["backup_owner_uid"]
        return installer.os.stat_result(fields, {
            name: getattr(details, name)
            for name in ("st_atime_ns", "st_mtime_ns", "st_ctime_ns")
        })

    monkeypatch.setattr(Path, "stat", synthetic_owner_stat)

    def mock_run(command, **kwargs):
        actions.append((tuple(command), dict(kwargs)))
        if command[0] == "/usr/sbin/runuser":
            assert command[-1] == "/usr/bin/true"
            assert kwargs["check"] is True
            if failure["namespace"]:
                raise subprocess.CalledProcessError(1, command)
        elif command[:2] == ["systemctl", "is-active"]:
            assert kwargs["check"] is False
            return types.SimpleNamespace(returncode=3, stdout="inactive\n")
        elif command == ["systemctl", "daemon-reload"]:
            if kwargs.get("check") and failure["daemon_reload"]:
                raise subprocess.CalledProcessError(1, command)
        else:
            raise AssertionError("unexpected host command in isolated installation")
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(installer.subprocess, "run", mock_run)
    return roots, actions, failure


def test_first_install_creates_only_isolated_paths_and_never_starts_service(
    installation_inputs, isolated_root
):
    files, digest, engine = installation_inputs
    (code, config, data, units), calls, _ = isolated_root
    result = installer.install_first_time(files, digest, engine)
    assert result["installed"] is True
    assert result["service_activation"] == "manual_after_health_and_tls_review"
    assert (code / "server.py").is_file()
    assert (code / "profiles/printers/bambu_lab_a1_04.json").is_file()
    assert (code / "engines/bambu-studio/squashfs-root/bin/bambu-studio").is_file()
    assert (data).is_dir()
    secret_data = json.loads((config / "config.json").read_text())
    assert secret_data["host"] == "127.0.0.1"
    assert len(secret_data["token"]) >= 32
    assert secret_data["source_root"] == str(code)
    assert secret_data["base_dir"] == str(data)
    assert {item.name for item in units.iterdir()} == installer.UNITS
    assert [cmd[0][0] for cmd in calls] == ["/usr/sbin/runuser", "systemctl"]
    assert calls[-1] == (("systemctl", "daemon-reload"), {"check": True})
    assert not (data / "data/jobs").exists(), "first install never queues a job"

    sentinel = data / "preserve.txt"
    sentinel.write_bytes(b"keep-user-data")
    with pytest.raises(installer.NativeInstallError, match="already present"):
        installer.install_first_time(files, digest, engine)
    assert sentinel.read_bytes() == b"keep-user-data"
    assert len(calls) == 2


def test_existing_state_blocks_first_install_without_touching_existing_data(
    installation_inputs, isolated_root
):
    files, digest, engine = installation_inputs
    (_, _, data, _), calls, _ = isolated_root
    data.mkdir()
    (data / "saved-job.json").write_text('{"existing":true}')
    with pytest.raises(installer.NativeInstallError, match="already present"):
        installer.install_first_time(files, digest, engine)
    assert (data / "saved-job.json").read_text() == '{"existing":true}'
    assert calls == []


def test_failed_daemon_reload_rolls_back_all_created_files(
    installation_inputs, isolated_root
):
    files, digest, engine = installation_inputs
    (code, config, data, units), calls, failure = isolated_root
    failure["daemon_reload"] = True
    with pytest.raises(subprocess.CalledProcessError):
        installer.install_first_time(files, digest, engine)
    assert not code.exists()
    assert not config.exists()
    assert not data.exists()
    assert list(units.iterdir()) == []
    assert [item[1]["check"] for item in calls] == [True, True, False]
    assert calls[0][0][0] == "/usr/sbin/runuser"


def test_chmod_error_during_unit_creation_leaves_no_orphaned_service(
    installation_inputs, isolated_root, monkeypatch
):
    files, digest, engine = installation_inputs
    (code, config, data, units), calls, _ = isolated_root
    original = installer.os.chmod
    triggered = False

    def fail_once(target, mode):
        nonlocal triggered
        if not triggered and str(target).endswith(".service") and str(target).startswith(str(units)):
            triggered = True
            raise PermissionError("simulated unit mode failure")
        return original(target, mode)

    monkeypatch.setattr(installer.os, "chmod", fail_once)
    with pytest.raises(PermissionError, match="simulated"):
        installer.install_first_time(files, digest, engine)
    assert triggered
    assert not code.exists()
    assert not config.exists()
    assert not data.exists()
    assert list(units.iterdir()) == []
    assert calls[-1] == (("systemctl", "daemon-reload"), {"check": False})
    assert calls[0][0][0] == "/usr/sbin/runuser"


def test_newly_created_service_user_is_rolled_back_on_failure(
    installation_inputs, isolated_root, monkeypatch
):
    files, digest, engine = installation_inputs
    (code, config, data, units), actions, _ = isolated_root
    exists = {"user": False}
    pwd = sys.modules["pwd"]

    def getpwnam(_name):
        if not exists["user"]:
            raise KeyError("test account not yet created")
        return types.SimpleNamespace(pw_uid=1099, pw_gid=1099)

    monkeypatch.setattr(pwd, "getpwnam", getpwnam)

    def run(command, **kwargs):
        actions.append((tuple(command), dict(kwargs)))
        if command[0] == "useradd":
            assert kwargs["check"] is True
            exists["user"] = True
        elif command[0] == "userdel":
            assert kwargs["check"] is True
            exists["user"] = False
        elif command[0] == "/usr/sbin/runuser":
            assert command[-1] == "/usr/bin/true"
        elif command == ["systemctl", "daemon-reload"]:
            if kwargs.get("check"):
                raise subprocess.CalledProcessError(1, command)
        else:
            raise AssertionError("unexpected host operation in test")
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(installer.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        installer.install_first_time(files, digest, engine)
    assert not exists["user"], "new account must be removed after failed first install"
    assert not code.exists() and not config.exists() and not data.exists()
    assert list(units.iterdir()) == []
    assert [command[0][0] for command in actions] == [
        "useradd", "/usr/sbin/runuser", "systemctl", "userdel", "systemctl",
    ]


def test_raced_systemd_file_is_never_overwritten_or_removed(
    installation_inputs, isolated_root, monkeypatch
):
    files, digest, engine = installation_inputs
    (code, config, data, units), actions, _ = isolated_root
    external = units / "ultimate-slicer-dispatch.service"
    original = Path.open
    fired = False

    def competing_create(path, mode="r", *args, **kwargs):
        nonlocal fired
        if not fired and path == external and mode == "xb":
            fired = True
            with original(path, "wb") as occupied:
                occupied.write(b"unrelated external unit")
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", competing_create)
    with pytest.raises(FileExistsError):
        installer.install_first_time(files, digest, engine)
    assert fired
    assert external.read_bytes() == b"unrelated external unit"
    assert not code.exists() and not config.exists() and not data.exists()
    assert [path.name for path in units.iterdir()] == [external.name]
    assert actions[0][0][0] == "/usr/sbin/runuser"
    assert actions[-1] == (("systemctl", "daemon-reload"), {"check": False})


def test_missing_user_namespace_blocks_before_installing_any_program_or_unit(
    installation_inputs, isolated_root
):
    files, digest, engine = installation_inputs
    (code, config, data, units), calls, failure = isolated_root
    failure["namespace"] = True
    with pytest.raises(installer.NativeInstallError, match="network namespace"):
        installer.install_first_time(files, digest, engine)
    assert not code.exists() and not config.exists() and not data.exists()
    assert list(units.iterdir()) == []
    assert calls[0][0][0] == "/usr/sbin/runuser"
    assert calls[-1] == (("systemctl", "daemon-reload"), {"check": False})
    assert not any(item[0][0] == "useradd" for item in calls)


def test_upgrade_preserves_secret_and_job_history_and_keeps_old_program_backup(
    installation_inputs, isolated_root, monkeypatch
):
    files, digest, engine = installation_inputs
    (code, config, state, units), calls, _ = isolated_root
    installer.install_first_time(files, digest, engine)
    original_program = (code / "server.py").read_bytes()
    original_secret_config = (config / "config.json").read_bytes()
    original_units = {name: (units / name).read_bytes() for name in installer.UNITS}
    jobdir = state / "data" / "jobs"
    jobdir.mkdir(parents=True)
    (jobdir / "old.completed.json").write_text('{"status":"completed"}')
    backup_parent = code.parent / ".private-native-code-backups"
    monkeypatch.setattr(installer, "upgrade_backup_root", lambda: backup_parent)
    incoming = dict(files)
    incoming["payload/server.py"] = original_program + b"\n# harmless synthetic update\n"
    report = installer.upgrade_stopped_native_server(incoming, digest, engine)
    assert report["upgraded"] is True
    assert report["service_activation"] == "manual_after_health_and_tls_review"
    assert (code / "server.py").read_bytes() == incoming["payload/server.py"]
    assert (Path(report["previous_code_backup"]) / "server.py").read_bytes() == original_program
    assert (config / "config.json").read_bytes() == original_secret_config
    assert (jobdir / "old.completed.json").read_text() == '{"status":"completed"}'
    assert all((units / name).read_bytes() == value for name, value in original_units.items())
    active_calls = [cmd for cmd, _ in calls if cmd[:2] == ("systemctl", "is-active")]
    assert len(active_calls) == 10
    assert not any(cmd[:2] in (("systemctl", "start"), ("systemctl", "enable")) for cmd, _ in calls)


def test_upgrade_refuses_nonterminal_jobs_without_replacing_code(
    installation_inputs, isolated_root, monkeypatch
):
    files, digest, engine = installation_inputs
    (code, config, state, units), calls, _ = isolated_root
    installer.install_first_time(files, digest, engine)
    before = (code / "server.py").read_bytes()
    jobdir = state / "data" / "jobs"
    jobdir.mkdir(parents=True)
    (jobdir / "pending.queued.json").write_text('{"status":"queued"}')
    with pytest.raises(installer.NativeInstallError, match="jobs pending"):
        installer.upgrade_stopped_native_server(files, digest, engine)
    assert (code / "server.py").read_bytes() == before
    assert (jobdir / "pending.queued.json").is_file()


def test_upgrade_refuses_active_service_and_modified_systemd_units(
    installation_inputs, isolated_root, monkeypatch
):
    files, digest, engine = installation_inputs
    (code, config, state, units), _, _ = isolated_root
    installer.install_first_time(files, digest, engine)
    before = (code / "server.py").read_bytes()
    original = installer.subprocess.run

    def service_running(command, **kwargs):
        if command[:2] == ["systemctl", "is-active"]:
            return types.SimpleNamespace(returncode=0, stdout="active\n")
        return original(command, **kwargs)

    monkeypatch.setattr(installer.subprocess, "run", service_running)
    with pytest.raises(installer.NativeInstallError, match="inactive"):
        installer.upgrade_stopped_native_server(files, digest, engine)
    assert (code / "server.py").read_bytes() == before
    monkeypatch.setattr(installer.subprocess, "run", original)
    unit = units / "ultimate-slicer-dispatch.service"
    unit.write_bytes(unit.read_bytes() + b"\n# altered locally")
    with pytest.raises(installer.NativeInstallError, match="separate review"):
        installer.upgrade_stopped_native_server(files, digest, engine)
    assert (code / "server.py").read_bytes() == before


def test_failed_atomic_upgrade_restores_previous_program_and_user_state(
    installation_inputs, isolated_root, monkeypatch
):
    files, digest, engine = installation_inputs
    (code, config, state, units), _, _ = isolated_root
    installer.install_first_time(files, digest, engine)
    original_program = (code / "server.py").read_bytes()
    original_config = (config / "config.json").read_bytes()
    user_job = state / "persistent-user-job.json"
    user_job.write_text('{"do_not_change":true}')
    monkeypatch.setattr(
        installer, "upgrade_backup_root",
        lambda: code.parent / ".private-native-code-backups",
    )
    real_rename = Path.rename
    failed = {"done": False}

    def fail_new_code_publish(source, target):
        if (
            not failed["done"]
            and source.name.startswith(".ultimate-slicer-upgrade-")
            and target == code
        ):
            failed["done"] = True
            raise OSError("simulated atomic publication failure")
        return real_rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_new_code_publish)
    changed = dict(files)
    changed["payload/server.py"] = original_program + b"\n# synthetic changed code"
    with pytest.raises(OSError, match="simulated atomic"):
        installer.upgrade_stopped_native_server(changed, digest, engine)
    assert failed["done"]
    assert (code / "server.py").read_bytes() == original_program
    assert (config / "config.json").read_bytes() == original_config
    assert user_job.read_text() == '{"do_not_change":true}'
    assert {path.name for path in units.iterdir()} == installer.UNITS


def test_protected_native_rollback_restores_original_program(
    installation_inputs, isolated_root, monkeypatch
):
    files, sha, engine = installation_inputs
    (code, config, state, units), calls, _ = isolated_root
    installer.install_first_time(files, sha, engine)
    original = (code / "server.py").read_bytes()
    secret = (config / "config.json").read_bytes()
    saved_job = state / "old-job.completed.json"
    saved_job.write_text('{"preserve":true}')
    monkeypatch.setattr(
        installer, "upgrade_backup_root",
        lambda: code.parent / ".private-native-code-backups",
    )
    changed = dict(files)
    changed["payload/server.py"] = original + b"\n# synthetic program change\n"
    upgrade = installer.upgrade_stopped_native_server(changed, sha, engine)
    backup = Path(upgrade["previous_code_backup"])
    result = installer.restore_stopped_native_code(backup)
    assert result["restored"] is True
    assert (code / "server.py").read_bytes() == original
    assert (Path(result["replaced_code_backup"]) / "server.py").read_bytes() == changed["payload/server.py"]
    assert (config / "config.json").read_bytes() == secret
    assert saved_job.read_text() == '{"preserve":true}'
    assert {unit.name for unit in units.iterdir()} == installer.UNITS
    assert not any(cmd[:2] in (("systemctl", "start"), ("systemctl", "enable")) for cmd, _ in calls)


def test_native_rollback_rejects_unrelated_user_directory(
    installation_inputs, isolated_root, monkeypatch
):
    files, sha, engine = installation_inputs
    (code, config, state, units), _, _ = isolated_root
    installer.install_first_time(files, sha, engine)
    before = (code / "server.py").read_bytes()
    monkeypatch.setattr(
        installer, "upgrade_backup_root",
        lambda: code.parent / ".private-native-code-backups",
    )
    other = code.parent / "unrelated-user-directory" / "code"
    other.mkdir(parents=True)
    (other / "server.py").write_bytes(b"untrusted")
    with pytest.raises(installer.NativeInstallError, match="backup"):
        installer.restore_stopped_native_code(other)
    assert (code / "server.py").read_bytes() == before


def test_native_rollback_rejects_queued_job_and_restores_no_files(
    installation_inputs, isolated_root, monkeypatch
):
    files, sha, engine = installation_inputs
    (code, config, state, units), _, _ = isolated_root
    installer.install_first_time(files, sha, engine)
    monkeypatch.setattr(
        installer, "upgrade_backup_root",
        lambda: code.parent / ".private-native-code-backups",
    )
    update = dict(files)
    update["payload/server.py"] += b"\n# newer code"
    report = installer.upgrade_stopped_native_server(update, sha, engine)
    previous = Path(report["previous_code_backup"])
    queue = state / "data" / "jobs"
    queue.mkdir(parents=True)
    (queue / "job.queued.json").write_text('{"queued":true}')
    with pytest.raises(installer.NativeInstallError, match="jobs pending"):
        installer.restore_stopped_native_code(previous)
    assert (code / "server.py").read_bytes() == update["payload/server.py"]
    assert previous.exists()
    assert (queue / "job.queued.json").is_file()


def test_failed_rollback_publication_restores_newer_code(
    installation_inputs, isolated_root, monkeypatch
):
    files, sha, engine = installation_inputs
    (code, config, state, units), _, _ = isolated_root
    installer.install_first_time(files, sha, engine)
    original = (code / "server.py").read_bytes()
    monkeypatch.setattr(
        installer, "upgrade_backup_root",
        lambda: code.parent / ".private-native-code-backups",
    )
    incoming = dict(files)
    incoming["payload/server.py"] += b"\n# replacement"
    report = installer.upgrade_stopped_native_server(incoming, sha, engine)
    backup = Path(report["previous_code_backup"])
    real_rename = Path.rename
    tripped = False

    def fail_backup_publish(path, target):
        nonlocal tripped
        if not tripped and path == backup and target == code:
            tripped = True
            raise OSError("synthetic restore rename failure")
        return real_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_backup_publish)
    with pytest.raises(OSError, match="synthetic restore"):
        installer.restore_stopped_native_code(backup)
    assert tripped
    assert (code / "server.py").read_bytes() == incoming["payload/server.py"]
    assert (backup / "server.py").read_bytes() == original


def test_repeating_identical_upgrade_is_read_only(
    installation_inputs, isolated_root, monkeypatch
):
    files, sha, engine = installation_inputs
    (code, config, state, units), actions, _ = isolated_root
    installer.install_first_time(files, sha, engine)
    before = (code / "server.py").read_bytes()
    secret = (config / "config.json").read_bytes()
    backup_parent = code.parent / ".private-native-code-backups"
    monkeypatch.setattr(installer, "upgrade_backup_root", lambda: backup_parent)
    result = installer.upgrade_stopped_native_server(files, sha, engine)
    assert result["upgraded"] is False
    assert result["unchanged"] is True
    assert result["backup_created"] is False
    assert (code / "server.py").read_bytes() == before
    assert (config / "config.json").read_bytes() == secret
    assert not backup_parent.exists()
    assert not any(cmd[:2] in (("systemctl", "start"), ("systemctl", "enable")) for cmd, _ in actions)


def test_repeating_already_completed_program_upgrade_adds_no_second_backup(
    installation_inputs, isolated_root, monkeypatch
):
    files, sha, engine = installation_inputs
    (code, config, state, units), _, _ = isolated_root
    installer.install_first_time(files, sha, engine)
    backups = code.parent / ".private-native-code-backups"
    monkeypatch.setattr(installer, "upgrade_backup_root", lambda: backups)
    changed = dict(files)
    changed["payload/server.py"] = files["payload/server.py"] + b"\n# program changed"
    first = installer.upgrade_stopped_native_server(changed, sha, engine)
    assert first["upgraded"] is True
    before = sorted(p.name for p in backups.iterdir())
    second = installer.upgrade_stopped_native_server(changed, sha, engine)
    assert second["upgraded"] is False
    assert second["unchanged"] is True
    assert sorted(p.name for p in backups.iterdir()) == before
    assert (code / "server.py").read_bytes() == changed["payload/server.py"]


def test_upgrade_refuses_backup_root_owned_by_unprivileged_user(
    installation_inputs, isolated_root, monkeypatch
):
    files, digest, engine = installation_inputs
    (code, config, _state, _units), _calls, failure = isolated_root
    installer.install_first_time(files, digest, engine)
    original_program = (code / "server.py").read_bytes()
    original_config = (config / "config.json").read_bytes()
    backup_parent = code.parent / ".private-native-code-backups"
    monkeypatch.setattr(installer, "upgrade_backup_root", lambda: backup_parent)
    failure["backup_owner_uid"] = 1099
    incoming = dict(files)
    incoming["payload/server.py"] += b"\n# synthetic rejected upgrade\n"

    with pytest.raises(installer.NativeInstallError, match="not owned by root"):
        installer.upgrade_stopped_native_server(incoming, digest, engine)

    assert (code / "server.py").read_bytes() == original_program
    assert (config / "config.json").read_bytes() == original_config
    assert list(backup_parent.iterdir()) == []
