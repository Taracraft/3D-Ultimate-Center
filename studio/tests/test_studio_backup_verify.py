"""Data-only recovery checks, using synthetic archives and isolated directories."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "tools" / "studio_backup_verify.py"
spec = importlib.util.spec_from_file_location("studio_backup_verify", MODULE)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def snapshot(tmp_path):
    root = tmp_path / "frozen"
    contents = {
        "config/.storage/profiles": b'{"profiles": [{"id":"pla"}]}',
        "config/.storage/projects": b'{"paint_layers": [{"plate":2,"material":4}]}',
        "config/.storage/audit": b'{"rows":[{"message":"synthetic event"}]}',
        "worker/state/job.json": b'{"status":"succeeded","output":"output/job.3mf"}',
        "worker/output/job.3mf": b"PK\x00synthetic-binary\x00\xff",
        "worker/uploads/model.stl": b"solid synthetic\nendsolid synthetic\n",
        "frontend/studio.js": b"/* synthetic build */",
        "browser/workspace.json": b'{"geometry":[1,2,3],"plate":2}',
    }
    for name, data in contents.items():
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
    (root / "gallery/empty-folder").mkdir(parents=True)
    manifest = verifier.inventory_snapshot(root, ["config", "worker", "frontend", "browser", "gallery"])
    return root, contents, manifest


def make_archive(tmp_path, snapshot, kind="tar", entries=None, name="backup"):
    root, contents, manifest = snapshot
    path = tmp_path / (name + (".zip" if kind == "zip" else ".tar.gz"))
    if entries is None:
        entries = [(d + "/", None) for d in manifest["directories"]] + list(contents.items())
    if kind == "zip":
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for entry, data in entries:
                archive.writestr(entry, b"" if data is None else data)
    else:
        with tarfile.open(path, "w:gz") as archive:
            for entry, data in entries:
                info = tarfile.TarInfo(entry)
                if data is None:
                    info.type = tarfile.DIRTYPE
                    archive.addfile(info)
                else:
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
    return path


def check(path, manifest, scratch=None):
    return verifier.verify_backup(path, manifest, sha(path.read_bytes()), scratch)


@pytest.mark.parametrize("kind", ["tar", "zip"])
def test_full_data_roundtrip_and_cleanup(snapshot, tmp_path, kind):
    root, contents, manifest = snapshot
    archive = make_archive(tmp_path, snapshot, kind)
    before = archive.read_bytes()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    result = check(archive, manifest, scratch)
    assert result["success"] and result["files_verified"] == len(contents)
    assert result["bytes_verified"] == sum(map(len, contents.values()))
    assert result["required_roots_verified"] == 5
    assert result["directories_verified"] == len(manifest["directories"])
    assert result["temporary_restore_removed"] and not list(scratch.iterdir())
    assert not result["live_restore_performed"]
    assert not result["full_system_restore_verified"]
    assert result["scope"] == "independent_manifest_only"
    assert archive.read_bytes() == before
    assert verifier.inventory_snapshot(root, manifest["required_roots"]) == manifest


@pytest.mark.parametrize("name", ["../outside", "/absolute", "a/../b", "a//b", "a/./b",
                                  "C:/secret", "a\\b", "file:stream", "NUL", "a/COM1.txt",
                                  "a/trailing.", "a/trailing ", "a/\x01bad", "e\u0301.txt"])
def test_unsafe_paths_are_refused(name):
    with pytest.raises(verifier.VerificationError):
        verifier.safe_path(name)


@pytest.mark.parametrize("kind", ["tar", "zip"])
def test_missing_archive_file_refused(snapshot, tmp_path, kind):
    _, contents, manifest = snapshot
    entries = [(d + "/", None) for d in manifest["directories"]] + list(contents.items())[:-1]
    path = make_archive(tmp_path, snapshot, kind, entries)
    with pytest.raises(verifier.VerificationError, match="missing_archive_file"):
        check(path, manifest)


@pytest.mark.parametrize("kind", ["tar", "zip"])
def test_changed_bytes_refused_and_temp_removed(snapshot, tmp_path, kind):
    _, contents, manifest = snapshot
    entries = [(d + "/", None) for d in manifest["directories"]] + list(contents.items())
    name, data = entries[-1]
    entries[-1] = name, b"x" * len(data)
    path = make_archive(tmp_path, snapshot, kind, entries)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    with pytest.raises(verifier.VerificationError, match="file_digest_mismatch"):
        check(path, manifest, scratch)
    assert not list(scratch.iterdir())


@pytest.mark.parametrize("kind", ["tar", "zip"])
def test_unlisted_file_refused(snapshot, tmp_path, kind):
    entries = [("unexpected", b"extra")]
    path = make_archive(tmp_path, snapshot, kind, entries)
    with pytest.raises(verifier.VerificationError, match="unlisted_archive_file"):
        check(path, snapshot[2])


@pytest.mark.parametrize("kind", ["tar", "zip"])
def test_duplicate_archive_paths_refused(snapshot, tmp_path, kind):
    name, data = next(iter(snapshot[1].items()))
    entries = [(name, data), (name, data)]
    if kind == "zip":
        with pytest.warns(UserWarning, match="Duplicate name"):
            path = make_archive(tmp_path, snapshot, kind, entries)
    else:
        path = make_archive(tmp_path, snapshot, kind, entries)
    with pytest.raises(verifier.VerificationError, match="duplicate_archive_path"):
        check(path, snapshot[2])


@pytest.mark.parametrize("member_type", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE,
                                        tarfile.CHRTYPE, tarfile.BLKTYPE])
def test_tar_links_and_special_files_refused(snapshot, tmp_path, member_type):
    path = tmp_path / "special.tar"
    with tarfile.open(path, "w") as archive:
        info = tarfile.TarInfo("unsafe")
        info.type, info.linkname = member_type, "../outside"
        archive.addfile(info)
    with pytest.raises(verifier.VerificationError, match="unsupported_archive_entry"):
        check(path, snapshot[2])
    assert not (tmp_path / "outside").exists()


def test_zip_symlink_refused(snapshot, tmp_path):
    path = tmp_path / "link.zip"
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "../outside")
    with pytest.raises(verifier.VerificationError, match="unsupported_archive_entry"):
        check(path, snapshot[2])


def test_missing_empty_directory_refused(snapshot, tmp_path):
    _, contents, manifest = snapshot
    dirs = [d for d in manifest["directories"] if d != "gallery/empty-folder"]
    path = make_archive(tmp_path, snapshot, entries=[(d + "/", None) for d in dirs] + list(contents.items()))
    with pytest.raises(verifier.VerificationError, match="directory_set_mismatch"):
        check(path, manifest)


def test_bad_archive_digest_refused(snapshot, tmp_path):
    path = make_archive(tmp_path, snapshot)
    with pytest.raises(verifier.VerificationError, match="archive_digest_mismatch"):
        verifier.verify_backup(path, snapshot[2], "0" * 64)


def test_nonempty_scratch_cannot_be_used(snapshot, tmp_path):
    path = make_archive(tmp_path, snapshot)
    scratch = tmp_path / "live"
    scratch.mkdir()
    (scratch / "preserve").write_bytes(b"unchanged")
    with pytest.raises(verifier.VerificationError, match="scratch_parent_not_empty"):
        check(path, snapshot[2], scratch)
    assert (scratch / "preserve").read_bytes() == b"unchanged"


def test_required_component_missing_refused(snapshot):
    manifest = copy.deepcopy(snapshot[2])
    manifest["required_roots"].append("missing-worker-config")
    with pytest.raises(verifier.VerificationError, match="required_root_missing"):
        verifier.validate_manifest(manifest)


def test_case_collision_refused(snapshot):
    manifest = copy.deepcopy(snapshot[2])
    name = next(iter(manifest["files"]))
    manifest["files"][name.upper()] = manifest["files"][name]
    with pytest.raises(verifier.VerificationError, match="path_collision"):
        verifier.validate_manifest(manifest)


def test_file_as_parent_refused(snapshot):
    manifest = copy.deepcopy(snapshot[2])
    manifest["files"]["config"] = {"size": 0, "sha256": sha(b"")}
    with pytest.raises(verifier.VerificationError, match="path_collision"):
        verifier.validate_manifest(manifest)


@pytest.mark.parametrize("change", [True, -1, 16 * 1024**3 + 1])
def test_invalid_size_refused(snapshot, change):
    manifest = copy.deepcopy(snapshot[2])
    next(iter(manifest["files"].values()))["size"] = change
    with pytest.raises(verifier.VerificationError):
        verifier.validate_manifest(manifest)


def test_duplicate_json_keys_refused(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"format":1,"format":1}')
    with pytest.raises(verifier.VerificationError, match="duplicate_json_key"):
        verifier.load_manifest(manifest)


def test_cli_error_is_machine_readable_without_contents(tmp_path):
    completed = subprocess.run([sys.executable, str(MODULE), "verify", str(tmp_path / "absent.tar"),
                                str(tmp_path / "absent.json"), "--archive-sha256", "0" * 64],
                               capture_output=True, text=True)
    assert completed.returncode == 1
    assert json.loads(completed.stdout) == {"success": False, "error": "input_io_error"}
    assert not completed.stderr


def test_insufficient_disk_space_refused(snapshot, tmp_path, monkeypatch):
    path = make_archive(tmp_path, snapshot)
    usage = type("Usage", (), {"free": 0})()
    monkeypatch.setattr(verifier.shutil, "disk_usage", lambda _: usage)
    with pytest.raises(verifier.VerificationError, match="insufficient_scratch_space"):
        check(path, snapshot[2])


def test_directory_alias_refused(snapshot):
    manifest = copy.deepcopy(snapshot[2])
    manifest["directories"].append("CONFIG")
    with pytest.raises(verifier.VerificationError, match="path_collision"):
        verifier.validate_manifest(manifest)


def test_snapshot_modification_during_inventory_refused(snapshot, monkeypatch):
    root, _, manifest = snapshot
    original = verifier.file_record
    calls = {}
    def changing(path):
        result = original(path)
        calls[path] = calls.get(path, 0) + 1
        if calls[path] > 1:
            result["sha256"] = "0" * 64
        return result
    monkeypatch.setattr(verifier, "file_record", changing)
    with pytest.raises(verifier.VerificationError, match="snapshot_changed"):
        verifier.inventory_snapshot(root, manifest["required_roots"])


def test_empty_manifest_cannot_pass(snapshot):
    manifest = copy.deepcopy(snapshot[2])
    manifest["files"] = {}
    with pytest.raises(verifier.VerificationError, match="invalid_inventory"):
        verifier.validate_manifest(manifest)


def test_total_size_limit_refused(snapshot, monkeypatch):
    monkeypatch.setattr(verifier, "MAX_BYTES", 1)
    with pytest.raises(verifier.VerificationError, match="total_size_limit"):
        verifier.validate_manifest(snapshot[2])


def test_entry_count_limit_refused(snapshot, tmp_path, monkeypatch):
    path = make_archive(tmp_path, snapshot)
    monkeypatch.setattr(verifier, "MAX_FILES", 1)
    with pytest.raises(verifier.VerificationError, match="invalid_inventory"):
        check(path, snapshot[2])


def test_archive_change_during_read_refused(snapshot, tmp_path, monkeypatch):
    path = make_archive(tmp_path, snapshot)
    original = verifier._entries
    def changed(raw):
        yield from original(raw)
        with path.open("ab") as stream:
            stream.write(b"changed-during-check")
    monkeypatch.setattr(verifier, "_entries", changed)
    with pytest.raises(verifier.VerificationError, match="archive_changed"):
        check(path, snapshot[2])


def test_nonarchive_refused(snapshot, tmp_path):
    path = tmp_path / "invalid.tar"
    path.write_bytes(b"not an archive")
    with pytest.raises(verifier.VerificationError, match="archive_io_error"):
        check(path, snapshot[2])


def test_file_size_header_mismatch_refused(snapshot, tmp_path):
    name, data = next(iter(snapshot[1].items()))
    path = make_archive(tmp_path, snapshot, entries=[(name, data + b"extra")])
    with pytest.raises(verifier.VerificationError, match="file_size_mismatch"):
        check(path, snapshot[2])


def test_zip_null_name_refused(snapshot, tmp_path):
    path = make_archive(tmp_path, snapshot, "zip", [("badXname", b"content")])
    path.write_bytes(path.read_bytes().replace(b"badXname", b"bad\x00name"))
    with pytest.raises(verifier.VerificationError, match="noncanonical_archive_name"):
        check(path, snapshot[2])


def test_cli_inventory_then_verify(snapshot, tmp_path):
    root, _, _ = snapshot
    archive = make_archive(tmp_path, snapshot)
    inventory = subprocess.run([sys.executable, str(MODULE), "inventory", str(root),
                                "--required-root", "config", "--required-root", "worker"],
                               capture_output=True, text=True, check=True)
    manifest_file = tmp_path / "independent-manifest.json"
    manifest_file.write_text(inventory.stdout, encoding="utf-8")
    completed = subprocess.run([sys.executable, str(MODULE), "verify", str(archive), str(manifest_file),
                                "--archive-sha256", sha(archive.read_bytes())],
                               capture_output=True, text=True, check=True)
    assert json.loads(completed.stdout)["success"] is True
    assert not completed.stderr


def test_standard_tar_dot_root_roundtrip(snapshot, tmp_path):
    root, contents, manifest = snapshot
    path = tmp_path / "standard.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        archive.add(root, arcname=".")
    assert check(path, manifest)["files_verified"] == len(contents)


def test_dot_alias_does_not_hide_duplicate(snapshot, tmp_path):
    name, data = next(iter(snapshot[1].items()))
    path = make_archive(tmp_path, snapshot, entries=[(name, data), ("./" + name, data)])
    with pytest.raises(verifier.VerificationError, match="duplicate_archive_path"):
        check(path, snapshot[2])
