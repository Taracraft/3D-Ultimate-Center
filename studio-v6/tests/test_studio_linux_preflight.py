"""Synthetic source trees only; no live configuration, services or printer jobs."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("linux_preflight_test", ROOT / "tools/studio_linux_preflight.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
WRAPPER = ROOT / "scripts/rebuild-homeassist.sh"


def digest(value): return hashlib.sha256(value).hexdigest()


def make_source(root, layout="public"):
    native = root / ("slicing-server" if layout == "public" else "deploy/homeassistant/host/3d-printer-slicing-server")
    units = root / "deployment/systemd" if layout == "public" else native / "systemd"
    component = root / ("homeassistant/custom_components/ultimate_3d_studio_v6" if layout == "public"
                        else "deploy/homeassistant/custom_components/ultimate_3d_studio_v6")
    native.mkdir(parents=True)
    units.mkdir(parents=True)
    component.mkdir(parents=True)
    sources = {}
    for name in set(mod.RUNTIME) | set(mod.PROFILES) | mod.DEPENDENCIES:
        data = ("# synthetic " + name + "\n").encode()
        target = component / name if name in mod.COMPONENT_DEPENDENCIES else native / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        sources[name] = data
    for name in mod.UNITS:
        data = ("# synthetic unit " + name + "\n").encode()
        (units / name).write_bytes(data)
        sources["systemd/" + name] = data
    primary = "".join(digest(sources[name]) + "  " + name + "\n" for name in sorted(mod.PRIMARY_REQUIRED))
    deps = "".join(digest(sources[name]) + "  " + name + "\n" for name in sorted(mod.DEPENDENCIES))
    (native / "SHA256SUMS").write_text(primary, encoding="utf-8")
    (native / "DEPENDENCY-SHA256SUMS").write_text(deps, encoding="utf-8")
    script = ("#!/usr/bin/env bash\nRUNTIME_FILES=(\n" + "\n".join(mod.RUNTIME)
              + ")\nPROFILE_FILES=(\n" + "\n".join(mod.PROFILES)
              + ")\nUNIT_FILES=(\n" + "\n".join(mod.UNITS) + ")\nexit 91\n")
    (native / "deploy-native-slicer.sh").write_text(script, encoding="utf-8")
    return native, units


def bytes_in(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("layout", ["canonical", "public"])
def test_complete_source_is_read_only_and_has_no_release_authority(tmp_path, layout):
    root = tmp_path / "repo"
    make_source(root, layout)
    before = bytes_in(root)
    files, _ = mod.collect(root, layout)
    result = mod.evidence(files)
    assert result["file_count"] == 27
    assert "job_control.py" in files and set(mod.DEPENDENCIES) <= files.keys()
    assert result["source_complete"] and not result["release_approved"]
    assert not result["installation_performed"] and not result["services_started"]
    assert result["scope"] == "native_worker_source_package_only"
    assert before == bytes_in(root) and str(root) not in json.dumps(result)


def test_public_systemd_layout_reconstructs_canonical_package(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    make_source(a, "canonical")
    make_source(b, "public")
    assert mod.collect(a, "canonical")[0] == mod.collect(b, "public")[0]
    assert mod.evidence(mod.collect(a, "canonical")[0]) == mod.evidence(mod.collect(b, "public")[0])


def test_no_dependency_is_taken_from_another_directory(tmp_path):
    root = tmp_path / "repo"
    native, _ = make_source(root)
    needed = root / "homeassistant/custom_components/ultimate_3d_studio_v6/bed-temperature-contract.sh"
    (tmp_path / needed.name).write_bytes(needed.read_bytes())
    (native / needed.name).write_bytes(needed.read_bytes())
    needed.unlink()
    with pytest.raises(FileNotFoundError): mod.collect(root, "public")


@pytest.mark.parametrize("name", sorted(mod.FORBIDDEN_SOURCE_ENTRIES))
def test_runtime_state_in_source_fails_before_copy(tmp_path, name):
    root = tmp_path / "repo"
    native, _ = make_source(root)
    (native / name).mkdir()
    with pytest.raises(mod.PreflightError, match="runtime_data_in_source"):
        mod.collect(root, "public")


def test_examples_legacy_component_and_unlisted_files_are_not_packaged(tmp_path):
    root = tmp_path / "repo"
    native, _ = make_source(root)
    (native / "config.example.json").write_text('{"example":true}')
    (native / "unlisted.py").write_text("raise RuntimeError('never execute or copy')")
    old = root / "homeassistant/custom_components/printer_control_center"
    old.mkdir(parents=True)
    (old / "keep.py").write_text("legacy stays")
    before = bytes_in(root)
    result = mod.stage(root, "public", tmp_path / "candidate")
    assert result["stage_complete"] and before == bytes_in(root)
    names = {item["path"] for item in result["files"]}
    assert "config.example.json" not in names and "unlisted.py" not in names
    assert not any("printer_control_center" in name for name in names)


@pytest.mark.parametrize("name", ["server.py", "job_control.py", "bed-temperature-contract.sh"])
def test_tampered_runtime_or_dependency_rejected(tmp_path, name):
    root = tmp_path / "repo"
    native, _ = make_source(root)
    target = (root / "homeassistant/custom_components/ultimate_3d_studio_v6" / name
              if name in mod.COMPONENT_DEPENDENCIES else native / name)
    target.write_bytes(b"changed")
    with pytest.raises(mod.PreflightError, match="source_digest_mismatch"):
        mod.collect(root, "public")


def test_tampered_public_unit_is_rejected(tmp_path):
    root = tmp_path / "repo"
    _, units = make_source(root)
    (units / mod.UNITS[0]).write_bytes(b"changed")
    with pytest.raises(mod.PreflightError, match="source_digest_mismatch:systemd/"):
        mod.collect(root, "public")


@pytest.mark.parametrize("path", ["../secret", "/etc/shadow", "config.json", "systemd/../config.json", "other.py", "C:/x", "a\\b"])
def test_manifest_cannot_expand_package_scope(path):
    with pytest.raises(mod.PreflightError, match="invalid_manifest_entry"):
        mod._manifest(("0" * 64 + "  " + path).encode(), mod.PRIMARY_ALLOWED, frozenset())


@pytest.mark.parametrize("payload", [b"not a checksum", b"f" * 63 + b"  server.py", b"g" * 64 + b"  server.py", b"\xff"])
def test_invalid_manifests_are_not_silently_ignored(payload):
    with pytest.raises(mod.PreflightError): mod._manifest(payload, mod.PRIMARY_ALLOWED, frozenset())


def test_duplicates_and_missing_members_fail_closed():
    line = b"0" * 64 + b"  server.py\n"
    with pytest.raises(mod.PreflightError, match="duplicate_manifest_entry"):
        mod._manifest(line + line, mod.PRIMARY_ALLOWED, frozenset())
    with pytest.raises(mod.PreflightError, match="incomplete_manifest"):
        mod._manifest(line, mod.PRIMARY_ALLOWED, mod.PRIMARY_REQUIRED)


def test_manifest_byte_limit():
    with pytest.raises(mod.PreflightError, match="manifest_size_limit"):
        mod._manifest(b"\n" * (mod.MAX_MANIFEST_BYTES + 1), frozenset(), frozenset())


def test_crlf_bom_and_binary_hash_marker_are_supported():
    line = b"\xef\xbb\xbf" + b"0" * 64 + b" *server.py\r\n"
    assert mod._manifest(line, mod.PRIMARY_ALLOWED, frozenset()) == {"server.py": "0" * 64}


def test_conflicting_overlapping_checksum_is_rejected(tmp_path):
    root = tmp_path / "repo"
    native, _ = make_source(root)
    with (native / "SHA256SUMS").open("a") as f: f.write("0" * 64 + "  job_control.py\n")
    with pytest.raises(mod.PreflightError, match="conflicting_manifests"):
        mod.collect(root, "public")


def test_matching_overlap_is_allowed_once(tmp_path):
    root = tmp_path / "repo"
    native, _ = make_source(root)
    sha = digest((native / "job_control.py").read_bytes())
    with (native / "SHA256SUMS").open("a") as f: f.write(sha + "  job_control.py\n")
    assert len(mod.collect(root, "public")[0]) == 27


@pytest.mark.parametrize("edit", ["missing", "duplicate", "expansion", "unclosed"])
def test_deployer_must_own_the_exact_complete_package(tmp_path, edit):
    root = tmp_path / "repo"
    native, _ = make_source(root)
    script = native / "deploy-native-slicer.sh"
    text = script.read_text()
    if edit == "missing": text = text.replace("job_control.py\n", "")
    elif edit == "duplicate": text += "\nRUNTIME_FILES=(server.py)\n"
    elif edit == "expansion": text = text.replace("job_control.py", "${UNREVIEWED}")
    else: text = text.replace("job_control.py", '"job_control.py')
    script.write_text(text)
    with pytest.raises(mod.PreflightError, match="unsupported_deployer_contract"):
        mod.collect(root, "public")


@pytest.mark.parametrize("layout", ["canonical", "public"])
def test_profile_scope_is_exact_and_manifest_bound(tmp_path, layout):
    root = tmp_path / "repo"
    native, _ = make_source(root, layout)
    files, _ = mod.collect(root, layout)
    assert set(mod.PROFILES) <= files.keys()
    for name in mod.PROFILES:
        assert files[name] == (native / name).read_bytes()
        assert f"{digest(files[name])}  {name}" in (native / "SHA256SUMS").read_text()


@pytest.mark.parametrize("problem", ["missing", "changed", "extra_file", "extra_directory"])
def test_profile_scope_fails_closed(tmp_path, problem):
    root = tmp_path / "repo"
    native, _ = make_source(root)
    target = native / mod.PROFILES[0]
    if problem == "missing":
        target.unlink()
    elif problem == "changed":
        target.write_bytes(b"changed profile\n")
    elif problem == "extra_file":
        (native / "profiles/printers/unreviewed.json").write_text("{}")
    else:
        (native / "profiles/unreviewed").mkdir()
    expected = "source_digest_mismatch" if problem == "changed" else (
        "input_or_stage_io_error" if problem == "missing" else "unexpected_profile_scope"
    )
    if problem == "missing":
        with pytest.raises((FileNotFoundError, mod.PreflightError)):
            mod.collect(root, "public")
    else:
        with pytest.raises(mod.PreflightError, match=expected):
            mod.collect(root, "public")


def test_read_refuses_a_size_limit_and_directory(tmp_path):
    file = tmp_path / "file"
    file.write_bytes(b"abc")
    with pytest.raises(mod.PreflightError, match="file_size_limit"): mod._read(file, 2)
    with pytest.raises(mod.PreflightError, match="invalid_file_type"): mod._read(tmp_path)


def test_package_size_limit(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    make_source(root)
    monkeypatch.setattr(mod, "MAX_PACKAGE_BYTES", 1)
    with pytest.raises(mod.PreflightError, match="package_size_limit"):
        mod.collect(root, "public")


def test_changed_source_on_second_read_is_rejected(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    make_source(root)
    original, calls = mod._read, {}
    def read(path, *args):
        calls[path] = calls.get(path, 0) + 1
        result = original(path, *args)
        return result + b"changed" if path.name == "server.py" and calls[path] == 2 else result
    monkeypatch.setattr(mod, "_read", read)
    with pytest.raises(mod.PreflightError, match="source_changed"):
        mod.collect(root, "public")


def test_staging_readback_manifest_and_source_bytes_match(tmp_path):
    root, destination = tmp_path / "repo", tmp_path / "candidate"
    make_source(root)
    files, _ = mod.collect(root, "public")
    result = mod.stage(root, "public", destination)
    assert result["stage_complete"]
    assert json.loads((destination / "STAGING-MANIFEST.json").read_text()) == result
    for item in result["files"]:
        assert (destination / item["path"]).read_bytes() == files[item["path"]]
        assert digest(files[item["path"]]) == item["sha256"]
    assert not result["installation_performed"] and not result["release_approved"]


@pytest.mark.parametrize("populated", [False, True])
def test_existing_destination_is_never_replaced(tmp_path, populated):
    root, dest = tmp_path / "repo", tmp_path / "existing"
    make_source(root)
    dest.mkdir()
    if populated: (dest / "keep").write_bytes(b"private")
    before = bytes_in(dest)
    with pytest.raises(FileExistsError): mod.stage(root, "public", dest)
    assert bytes_in(dest) == before


def test_staging_in_source_or_live_root_is_rejected(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    make_source(root)
    live = tmp_path / "live"
    live.mkdir()
    monkeypatch.setattr(mod, "LIVE_ROOTS", (live,))
    for dest in [root / "candidate", live / "candidate"]:
        with pytest.raises(mod.PreflightError, match="unsafe_stage_destination"):
            mod.stage(root, "public", dest)
        assert not dest.exists()


def test_failed_staging_has_no_completion_record_and_preserves_sources(tmp_path, monkeypatch):
    root, dest = tmp_path / "repo", tmp_path / "candidate"
    make_source(root)
    before = bytes_in(root)
    def failed(_): raise OSError("fsync failure")
    monkeypatch.setattr(mod.os, "fsync", failed)
    with pytest.raises(OSError): mod.stage(root, "public", dest)
    assert not (dest / "STAGING-MANIFEST.json").exists()
    assert before == bytes_in(root)


def test_second_snapshot_change_prevents_stage_completion(tmp_path, monkeypatch):
    root, dest = tmp_path / "repo", tmp_path / "candidate"
    make_source(root)
    original, count = mod.collect, 0
    def changing(*args):
        nonlocal count
        result, roots = original(*args)
        count += 1
        if count == 2: result["server.py"] = b"changed"
        return result, roots
    monkeypatch.setattr(mod, "collect", changing)
    with pytest.raises(mod.PreflightError, match="source_changed"):
        mod.stage(root, "public", dest)
    assert not (dest / "STAGING-MANIFEST.json").exists()


@pytest.mark.skipif(os.name == "nt", reason="Actual symlink creation requires Windows developer mode or elevation")
@pytest.mark.parametrize("where", ["source", "source_parent", "stage_parent"])
def test_real_symlink_paths_are_not_followed(tmp_path, where):
    root = tmp_path / "repo"
    native, _ = make_source(root)
    if where == "source":
        file = native / "job_control.py"
        target = tmp_path / "outside.py"
        file.rename(target)
        file.symlink_to(target)
        with pytest.raises(mod.PreflightError, match="linked_path"): mod.collect(root, "public")
    elif where == "source_parent":
        link = tmp_path / "link"
        link.symlink_to(root, target_is_directory=True)
        with pytest.raises(mod.PreflightError, match="linked_path"): mod.collect(link, "public")
    else:
        outside, link = tmp_path / "outside", tmp_path / "link"
        outside.mkdir()
        link.symlink_to(outside, target_is_directory=True)
        with pytest.raises(mod.PreflightError, match="linked_path"): mod.stage(root, "public", link / "stage")
        assert list(outside.iterdir()) == []


def test_cli_error_does_not_expose_paths_or_fabricate_success(tmp_path, capsys):
    code = mod.main(["--source-root", str(tmp_path / "private-missing"), "--layout", "public", "--check"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1 and payload["success"] is False
    assert payload["error"] == "input_or_stage_io_error"
    assert not payload["installation_performed"]
    assert "private-missing" not in json.dumps(payload)


def wrapper_repo(root, layout="public"):
    make_source(root, layout)
    (root / "scripts").mkdir()
    shutil.copyfile(WRAPPER, root / "scripts/rebuild-homeassist.sh")
    tool = root / ("studio-v6/tools" if layout == "public" else "tools")
    tool.mkdir(parents=True)
    shutil.copyfile(ROOT / "tools/studio_linux_preflight.py", tool / "studio_linux_preflight.py")
    return root / "scripts/rebuild-homeassist.sh"


@pytest.mark.skipif(os.name == "nt", reason="The actual Bash compatibility entrypoint requires Linux")
@pytest.mark.parametrize("layout", ["canonical", "public"])
def test_real_shell_check_does_not_invoke_old_install_actions(tmp_path, layout):
    script = wrapper_repo(tmp_path / "repo", layout)
    trapdir = tmp_path / "commands"
    trapdir.mkdir()
    log = tmp_path / "must-not-exist"
    for command in ["apt-get", "cp", "find", "rm", "install", "chmod", "systemctl", "sudo"]:
        trap = trapdir / command
        trap.write_text('#!/bin/sh\nprintf "%s\\n" "called" >> "$BAD_ACTION_LOG"\nexit 97\n')
        trap.chmod(0o755)
    env = {**os.environ, "PATH": str(trapdir) + os.pathsep + os.environ["PATH"], "BAD_ACTION_LOG": str(log),
           "TARGET_HA_ROOT": str(tmp_path / "do-not-create-ha"), "TARGET_SLICER_ROOT": str(tmp_path / "do-not-create-worker"),
           "SYSTEMD_DIR": str(tmp_path / "do-not-create-systemd")}
    before = bytes_in(tmp_path / "repo")
    run = subprocess.run(["bash", str(script), "--check"], env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["source_complete"]
    assert before == bytes_in(tmp_path / "repo") and not log.exists()
    assert not (tmp_path / "do-not-create-worker").exists()
    assert not (tmp_path / "do-not-create-ha").exists()


@pytest.mark.skipif(os.name == "nt", reason="The actual Bash compatibility entrypoint requires Linux")
@pytest.mark.parametrize("args", [[], ["--apply"], ["--check", "--stage", "anywhere"]])
def test_old_or_ambiguous_shell_invocation_never_claims_rebuild(tmp_path, args):
    script = wrapper_repo(tmp_path / "repo")
    before = bytes_in(tmp_path / "repo")
    run = subprocess.run(["bash", str(script), *args], capture_output=True, text=True)
    assert run.returncode == 2
    assert before == bytes_in(tmp_path / "repo")


@pytest.mark.skipif(os.name == "nt", reason="The actual Bash compatibility entrypoint requires Linux")
def test_shell_stages_native_package_without_executing_deployer(tmp_path):
    script = wrapper_repo(tmp_path / "repo")
    dest = tmp_path / "stage"
    run = subprocess.run(["bash", str(script), "--stage", str(dest)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["stage_complete"] and not result["installation_performed"]
    assert (dest / "deploy-native-slicer.sh").read_text().endswith("exit 91\n")


def test_wrapper_contains_no_legacy_copy_deletion_or_system_change():
    source = WRAPPER.read_text()
    for text in ["rm -rf", "apt-get", "systemctl", "printer_control_center", "TARGET_SLICER_ROOT", "prusa-slicer"]:
        assert text not in source
    assert "--source-root" in source and "--layout" in source
