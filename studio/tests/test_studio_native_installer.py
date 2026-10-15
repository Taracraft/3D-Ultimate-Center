"""Offline package-installer security checks; never installs or starts a service."""
from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "ultimate-slicer-server"


def load(name: str, source: Path):
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load("native_builder_under_test", PACKAGE / "build_native_package.py")
installer = load("native_installer_under_test", PACKAGE / "install_native.py")


@pytest.fixture
def bundle(tmp_path):
    archive = tmp_path / "ultimate-slicer-server.tar.gz"
    result = builder.build(ROOT, archive)
    return archive, result["archive_sha256"]


def test_inspect_only_verifies_all_sources_without_writing_install_paths(bundle):
    archive, digest = bundle
    metadata, files = installer.inspect_bundle(archive, digest)
    assert metadata["package"] == "ultimate-slicer-server"
    assert metadata["native_deploy_ready"] is False
    assert metadata["first_install_tool_included"] is True
    assert len(files) == 26
    assert "installer/install_native.py" in files
    assert {key for key in files if key.startswith("systemd/")} == {
        "systemd/" + name for name in installer.UNITS
    }


@pytest.mark.parametrize("digest", ["", "not-a-hash", "0" * 64])
def test_missing_or_wrong_external_archive_sha_is_denied(bundle, digest):
    archive, _expected = bundle
    with pytest.raises(installer.NativeInstallError):
        installer.inspect_bundle(archive, digest)


def _rewrite_archive(original: Path, destination: Path, transform):
    with tarfile.open(original, "r:gz") as src:
        records = [(m.name, src.extractfile(m).read(), m.mode) for m in src.getmembers()]
    with tarfile.open(destination, "w:gz", format=tarfile.PAX_FORMAT) as dst:
        for name, blob, mode in records:
            name, blob = transform(name, blob)
            entry = tarfile.TarInfo(name)
            entry.mode = mode
            entry.size = len(blob)
            dst.addfile(entry, io.BytesIO(blob))


def test_tampered_payload_fails_even_when_outer_hash_is_recomputed(bundle, tmp_path):
    archive, _ = bundle
    modified = tmp_path / "tampered.tar.gz"
    def transform(name, body):
        if name.endswith("/payload/server.py"):
            return name, body + b"\n# malicious append"
        return name, body
    _rewrite_archive(archive, modified, transform)
    with pytest.raises(installer.NativeInstallError, match="untrusted"):
        installer.inspect_bundle(modified, installer.hash_file(modified))


def test_archive_path_traversal_is_refused(bundle, tmp_path):
    archive, _ = bundle
    changed = tmp_path / "traversal.tar.gz"
    def transform(name, body):
        if name.endswith("/payload/server.py"):
            return "ultimate-slicer-server/../unsafe.txt", body
        return name, body
    _rewrite_archive(archive, changed, transform)
    with pytest.raises(installer.NativeInstallError, match="unsafe"):
        installer.inspect_bundle(changed, installer.hash_file(changed))


def test_empty_or_mismatched_engine_is_denied(tmp_path):
    source = tmp_path / "engine"
    source.mkdir()
    manifest = tmp_path / "engine-SHA256SUMS"
    manifest.write_text("")
    with pytest.raises(installer.NativeInstallError):
        installer.verify_engine(source, manifest)


def test_pinned_licensed_engine_tree_checks_hashes_and_profiles(tmp_path):
    source = tmp_path / "engine"
    (source / "bin").mkdir(parents=True)
    executable = source / "bin" / "bambu-studio"
    executable.write_bytes(b"\x7fELF" + b"synthetic-executable-for-tests")
    executable.chmod(0o755)
    profiles = []
    for category in ("machine", "process", "filament"):
        folder = source / "resources" / "profiles" / "BBL" / category
        folder.mkdir(parents=True)
        filename = "0.20mm Standard @BBL A1.json" if category == "process" else "synthetic.json"
        path = folder / filename
        path.write_text('{"name":"synthetic"}')
        profiles.append(path)
    manifest = tmp_path / "engine-SHA256SUMS"
    manifest.write_text(
        installer.hash_file(executable) + "  bin/bambu-studio\n"
        + "".join(
            installer.hash_file(path) + "  " + path.relative_to(source).as_posix() + "\n"
            for path in profiles
        )
    )
    entries = installer.verify_engine(source, manifest)
    assert len(entries) == 4
    profiles[0].write_text('{"name":"tampered"}')
    with pytest.raises(installer.NativeInstallError):
        installer.verify_engine(source, manifest)


def test_root_installer_denies_non_linux_context_before_any_side_effects(monkeypatch):
    monkeypatch.setattr(installer.sys, "platform", "win32")
    with pytest.raises(installer.NativeInstallError, match="Linux root"):
        installer.install_first_time({}, "0" * 64, [])


def test_cli_inspection_is_read_only_and_install_without_engine_is_refused(
    bundle, monkeypatch, capsys,
):
    archive, digest = bundle
    monkeypatch.setattr(sys, "argv", [
        "install_native.py", "--archive", str(archive), "--archive-sha256", digest,
    ])
    assert installer.main() == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["bundle_verified"] is True
    assert inspected["installation_performed"] is False
    monkeypatch.setattr(sys, "argv", [
        "install_native.py", "--archive", str(archive), "--archive-sha256", digest,
        "--install",
    ])
    assert installer.main() == 1
    assert "Native installer refused" in capsys.readouterr().err


def test_explicit_code_rollback_cli_requires_protected_path(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["install_native.py", "--rollback"])
    assert installer.main() == 1
    assert "Native installer refused" in capsys.readouterr().err


def test_rollback_cli_cannot_combine_external_bundle(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "install_native.py", "--rollback", "--code-backup", "/tmp/code",
        "--archive", "/tmp/extra.tar.gz", "--archive-sha256", "a" * 64,
    ])
    assert installer.main() == 1
    assert "Native installer refused" in capsys.readouterr().err


def test_code_rollback_cli_uses_explicit_trusted_restore_function(monkeypatch, capsys):
    chosen = Path("/opt/.ultimate-slicer-server-backups/example/code")
    invoked = []
    def restore(path):
        invoked.append(path)
        return {"restored": True, "service_activation": "manual_after_health_and_tls_review"}
    monkeypatch.setattr(installer, "restore_stopped_native_code", restore)
    monkeypatch.setattr(sys, "argv", [
        "install_native.py", "--rollback", "--code-backup", str(chosen),
    ])
    assert installer.main() == 0
    assert invoked == [chosen]
    result = json.loads(capsys.readouterr().out)
    assert result["restored"] is True


def test_install_and_upgrade_cli_are_mutually_exclusive(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "install_native.py", "--archive", "/tmp/slicer.tar.gz",
        "--archive-sha256", "b" * 64, "--install", "--upgrade",
    ])
    with pytest.raises(SystemExit) as exc:
        installer.main()
    assert exc.value.code == 2


def _synthetic_engine_with_desktop_icon(tmp_path):
    source = tmp_path / "engine"
    elf = source / "bin" / "bambu-studio"
    elf.parent.mkdir(parents=True)
    elf.write_bytes(b"\x7fELF" + b"safe-test-fixture-not-executed")
    elf.chmod(0o755)
    icon = source / "BambuStudio.png"
    icon.write_bytes(b"synthetic-icon")
    real_files = [elf, icon]
    for category in ("machine", "process", "filament"):
        file = source / "resources" / "profiles" / "BBL" / category / "sample.json"
        file.parent.mkdir(parents=True)
        file.write_bytes(b'{"name":"synthetic"}')
        real_files.append(file)
    checksum_file = tmp_path / "engine-SHA256SUMS"
    checksum_file.write_text("".join(
        installer.hash_file(file) + "  " + file.relative_to(source).as_posix() + "\n"
        for file in real_files
    ))
    return source, checksum_file, real_files


def test_verified_desktop_icon_link_can_be_ignored_for_headless_engine(tmp_path):
    source, checksum_file, real_files = _synthetic_engine_with_desktop_icon(tmp_path)
    desktop_link = source / ".DirIcon"
    try:
        desktop_link.symlink_to("BambuStudio.png")
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links unavailable in this test environment")
    entries = installer.verify_engine(source, checksum_file)
    assert len(entries) == len(real_files)
    assert {name for name, _, _ in entries} == {
        file.relative_to(source).as_posix() for file in real_files
    }
    assert ".DirIcon" not in {name for name, _, _ in entries}
    # Desktop aliases must never appear as paths to copy into system binaries.


def test_unreviewed_engine_symlink_is_still_rejected(tmp_path):
    source, checksum_file, _ = _synthetic_engine_with_desktop_icon(tmp_path)
    extra = source / "unsafe-file-link"
    try:
        extra.symlink_to("BambuStudio.png")
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links unavailable in this test environment")
    with pytest.raises(installer.NativeInstallError, match="unsafe engine symbolic link"):
        installer.verify_engine(source, checksum_file)


def test_desktop_icon_alias_cannot_leave_the_engine_tree(tmp_path):
    source, checksum_file, _ = _synthetic_engine_with_desktop_icon(tmp_path)
    icon = source / ".DirIcon"
    try:
        icon.symlink_to("../outside.png")
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links unavailable in this test environment")
    with pytest.raises(installer.NativeInstallError, match="unsafe engine symbolic link"):
        installer.verify_engine(source, checksum_file)


def test_only_known_headless_tooltip_index_files_are_excluded(tmp_path):
    source, checksum_file, real_files = _synthetic_engine_with_desktop_icon(tmp_path)
    for name in ("resources/tooltip/.md", "resources/tooltip/zh_CN/.md"):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"temporary-desktop-tooltip-not-runtime")
    entries = installer.verify_engine(source, checksum_file)
    assert len(entries) == len(real_files)
    assert not any(name in installer.ENGINE_TOOLTIPS_EXCLUDED for name, _, _ in entries)


def test_other_hidden_engine_file_still_fails_closed(tmp_path):
    source, checksum_file, _ = _synthetic_engine_with_desktop_icon(tmp_path)
    hidden = source / "resources" / "tooltip" / ".unexpected"
    hidden.parent.mkdir(parents=True, exist_ok=True)
    hidden.write_bytes(b"synthetic-unreviewed-metadata")
    with pytest.raises(installer.NativeInstallError, match="unreviewed"):
        installer.verify_engine(source, checksum_file)



def test_excluded_tooltip_metadata_cannot_hide_large_payload(tmp_path):
    source, checksum_file, _ = _synthetic_engine_with_desktop_icon(tmp_path)
    tooltip = source / "resources" / "tooltip" / ".md"
    tooltip.parent.mkdir(parents=True)
    tooltip.write_bytes(b"X" * 4097)
    with pytest.raises(installer.NativeInstallError, match="unsafe excluded engine metadata"):
        installer.verify_engine(source, checksum_file)


def test_excluded_tooltip_metadata_symlink_is_still_refused(tmp_path):
    source, checksum_file, _ = _synthetic_engine_with_desktop_icon(tmp_path)
    tooltip = source / "resources" / "tooltip" / ".md"
    tooltip.parent.mkdir(parents=True)
    try:
        tooltip.symlink_to(source / "BambuStudio.png")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable in this test environment")
    with pytest.raises(installer.NativeInstallError, match="unsafe engine symbolic link"):
        installer.verify_engine(source, checksum_file)



@pytest.mark.parametrize("operation", ("--install", "--upgrade"))
def test_unapproved_bundles_cannot_install_or_upgrade_even_with_engine(
    bundle, operation, monkeypatch, capsys, tmp_path,
):
    """An independently pinned but unapproved source bundle remains read-only."""
    archive, external_sha = bundle
    calls = []

    def unexpectedly_verify_engine(*args, **kwargs):
        calls.append("engine_verified")
        raise AssertionError("unapproved artifact must never reach engine verification")

    monkeypatch.setattr(installer, "verify_engine", unexpectedly_verify_engine)
    monkeypatch.setattr(sys, "argv", [
        "install_native.py", "--archive", str(archive),
        "--archive-sha256", external_sha, operation,
        "--engine-root", str(tmp_path / "example-engine"),
        "--engine-sha256-manifest", str(tmp_path / "engine-manifest"),
        "--accept-engine-license",
    ])
    assert installer.main() == 1
    assert "Native installer refused" in capsys.readouterr().err
    assert calls == []


def test_inspect_mode_reports_not_approved_without_installation(bundle, monkeypatch, capsys):
    archive, external_sha = bundle
    monkeypatch.setattr(sys, "argv", [
        "install_native.py", "--archive", str(archive),
        "--archive-sha256", external_sha,
    ])
    assert installer.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["bundle_verified"] is True
    assert result["native_deploy_ready"] is False
    assert result["installation_performed"] is False


def test_absent_jq_fails_native_dependency_preflight(monkeypatch):
    """Do not install a supervisor which cannot read its own job/profile JSON."""
    actual = installer.shutil.which
    monkeypatch.setattr(
        installer.shutil, "which",
        lambda command: None if command == "jq" else actual(command),
    )
    with pytest.raises(installer.NativeInstallError, match="jq"):
        installer.require_native_runtime_dependencies()


def test_dependency_list_covers_native_worker_and_service_tools():
    required = {
        "python3", "jq", "awk", "grep", "find", "sort", "head", "tail",
        "cut", "tr", "du", "id", "unshare", "systemctl", "useradd", "userdel",
    }
    assert required.issubset(installer.NATIVE_RUNTIME_COMMANDS)
    assert "/usr/bin/python3" in installer.NATIVE_ABSOLUTE_EXECUTABLES
    assert "/usr/bin/unshare" in installer.NATIVE_ABSOLUTE_EXECUTABLES
    assert "/usr/sbin/runuser" in installer.NATIVE_ABSOLUTE_EXECUTABLES



def test_host_dependency_check_is_read_only(monkeypatch, capsys):
    checked = []
    monkeypatch.setattr(installer.sys, "platform", "linux")
    monkeypatch.setattr(
        installer, "require_native_runtime_dependencies",
        lambda: checked.append(True),
    )
    monkeypatch.setattr(sys, "argv", ["install_native.py", "--check-host"])
    assert installer.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {
        "host_dependencies": "ready",
        "prerequisite_commands": len(installer.NATIVE_RUNTIME_COMMANDS),
        "installation_performed": False,
    }
    assert checked == [True]


def test_host_dependency_check_disallows_installation_arguments(monkeypatch, capsys):
    checked = []
    monkeypatch.setattr(installer.sys, "platform", "linux")
    monkeypatch.setattr(
        installer, "require_native_runtime_dependencies",
        lambda: checked.append(True),
    )
    monkeypatch.setattr(sys, "argv", [
        "install_native.py", "--check-host",
        "--archive", "/tmp/synthetic-source.tar.gz",
        "--archive-sha256", "f" * 64,
    ])
    assert installer.main() == 1
    assert "Native installer refused" in capsys.readouterr().err
    assert checked == []


def test_host_dependency_check_requires_native_linux(monkeypatch, capsys):
    monkeypatch.setattr(installer.sys, "platform", "win32")
    monkeypatch.setattr(sys, "argv", ["install_native.py", "--check-host"])
    assert installer.main() == 1
    assert "Native installer refused" in capsys.readouterr().err


@pytest.mark.parametrize("missing_tool", ("jq", "cp", "chmod", "mkdir", "mv", "rm", "sleep", "wc", "date"))
def test_missing_native_worker_tool_fails_closed(monkeypatch, missing_tool):
    monkeypatch.setattr(
        installer.shutil, "which",
        lambda command: None if command == missing_tool else "/synthetic/tool",
    )
    with pytest.raises(installer.NativeInstallError, match=missing_tool):
        installer.require_native_runtime_dependencies()


def test_runtime_dependency_contract_covers_worker_shell_commands():
    required = {
        "python3", "jq", "awk", "grep", "find", "sort", "head", "tail",
        "cut", "tr", "du", "id", "unshare", "systemctl", "useradd",
        "userdel", "mkfifo", "cp", "chmod", "mkdir", "mv", "rm",
        "sleep", "wc", "date",
    }
    assert installer.NATIVE_RUNTIME_COMMANDS == frozenset(required)
    worker = (
        ROOT / "deploy/homeassistant/host/3d-printer-slicing-server/dispatch-job.sh"
    ).read_text(encoding="utf-8-sig")
    refresh = (
        ROOT / "deploy/homeassistant/host/3d-printer-slicing-server/refresh-state.sh"
    ).read_text(encoding="utf-8-sig")
    assert 'cp "$OUTPUT/$JOB_ID.result.json"' in worker
    assert 'chmod 700 "$XDG_RUNTIME"' in worker
    assert 'sleep 0.05' in worker
    assert 'mkdir -p "$API"' in refresh
    assert 'NOW=$(date -Iseconds)' in refresh
    assert ' | wc -l' in refresh
    assert 'mv "$API/$NAME.json.tmp"' in refresh
