"""GA-09 duplicate inspection uses synthetic files, never a user's library."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import threading
from types import SimpleNamespace

import pytest

MODULE = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6/gallery_duplicate_scan.py"
spec = importlib.util.spec_from_file_location("gallery_duplicate_scan_under_test", MODULE)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


def library(tmp_path, files):
    root = tmp_path / "models"
    root.mkdir()
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def test_equal_bytes_across_folders_are_grouped_without_modification(tmp_path):
    contents = {"B/a.stl": b"model-a", "A/a.stl": b"model-a", "different.obj": b"model-b"}
    root = library(tmp_path, contents)
    before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = scanner.scan_gallery_duplicates(root)
    assert result["complete"] and result["read_only"]
    assert result["files_examined"] == result["files_hashed"] == 3
    assert result["bytes_hashed"] == 21
    assert result["groups"] == [{"sha256": hashlib.sha256(b"model-a").hexdigest(), "size_bytes": 7,
        "paths": ["A/a.stl", "B/a.stl"], "independent_copies": 2,
        "hardlink_aliases": 0, "redundant_content_bytes": 7}]
    assert result["deletion_authorized"] is False and result["disk_space_savings_verified"] is False
    assert before == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert str(root) not in str(result)


def test_only_selected_folder_is_examined(tmp_path):
    root = library(tmp_path, {"inside/a.stl": b"abc", "inside/sub/b.STL": b"abc", "outside.stl": b"abc"})
    result = scanner.scan_gallery_duplicates(root, "inside")
    assert result["files_examined"] == 2 and result["folder"] == "inside"
    assert result["groups"][0]["paths"] == ["inside/a.stl", "inside/sub/b.STL"]


def test_names_sizes_and_thumbnails_are_not_duplicate_proof(tmp_path):
    root = library(tmp_path, {"a/same.stl": b"abc", "b/same.stl": b"xyz", "image.png": b"abc", "note.txt": b"abc"})
    result = scanner.scan_gallery_duplicates(root)
    assert result["files_examined"] == 2 and result["groups"] == []


def test_unique_sizes_need_no_content_read(tmp_path, monkeypatch):
    root = library(tmp_path, {"a.stl": b"ab", "b.obj": b"abc"})
    monkeypatch.setattr(scanner.os, "open", lambda *_: pytest.fail("unique sizes must not be opened"))
    result = scanner.scan_gallery_duplicates(root)
    assert result["files_hashed"] == result["bytes_hashed"] == 0


def test_empty_library_is_a_complete_read_only_result(tmp_path):
    result = scanner.scan_gallery_duplicates(library(tmp_path, {}))
    assert result["complete"] and result["files_examined"] == 0


def test_empty_models_are_byte_equal_not_claimed_valid_meshes(tmp_path):
    result = scanner.scan_gallery_duplicates(library(tmp_path, {"a.stl": b"", "b.stl": b""}))
    assert result["groups"][0]["size_bytes"] == 0
    assert result["scope"] == "byte_identical_models_in_folder"


@pytest.mark.parametrize("folder", ["/", "/etc", "../outside", "a/../b", "a//b", "a/./b", "a/", "C:/data", "a\\b", "bad\x00name", "x" * 2049, None])
def test_unsafe_folders_fail_before_io(tmp_path, folder):
    with pytest.raises(scanner.DuplicateScanError, match="invalid_folder"):
        scanner.scan_gallery_duplicates(tmp_path / "missing", folder)


@pytest.mark.parametrize("kwargs", [{"max_entries": 0}, {"max_entries": True}, {"max_entries": 20_001},
    {"max_hash_bytes": -1}, {"max_hash_bytes": True}, {"timeout_seconds": 0},
    {"timeout_seconds": float("nan")}, {"timeout_seconds": float("inf")}, {"timeout_seconds": True}])
def test_invalid_limits_fail_before_io(tmp_path, kwargs):
    with pytest.raises(scanner.DuplicateScanError, match="invalid_limits"):
        scanner.scan_gallery_duplicates(tmp_path / "missing", **kwargs)


def test_missing_root_is_never_created(tmp_path):
    root = tmp_path / "absent"
    with pytest.raises(scanner.DuplicateScanError, match="folder_not_found"):
        scanner.scan_gallery_duplicates(root)
    assert not root.exists()


def test_entry_budget_prevents_a_false_complete_result(tmp_path):
    root = library(tmp_path, {"a.stl": b"a", "b.stl": b"a"})
    with pytest.raises(scanner.DuplicateScanError, match="scan_entry_limit"):
        scanner.scan_gallery_duplicates(root, max_entries=1)


def test_byte_budget_is_checked_before_content_read(tmp_path, monkeypatch):
    root = library(tmp_path, {"a.stl": b"abc", "b.stl": b"abc"})
    monkeypatch.setattr(scanner.os, "open", lambda *_: pytest.fail("overbudget files must not open"))
    with pytest.raises(scanner.DuplicateScanError, match="scan_byte_limit"):
        scanner.scan_gallery_duplicates(root, max_hash_bytes=5)


def test_precancelled_scan_reads_no_files(tmp_path):
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(scanner.DuplicateScanError, match="scan_cancelled"):
        scanner.scan_gallery_duplicates(tmp_path, cancel=cancel)


def test_deadline_exhaustion_does_not_return_partial_groups(tmp_path, monkeypatch):
    root = library(tmp_path, {"a.stl": b"abc", "b.stl": b"abc"})
    moments = iter([0, 0, 30])
    monkeypatch.setattr(scanner.time, "monotonic", lambda: next(moments, 30))
    with pytest.raises(scanner.DuplicateScanError, match="scan_time_limit"):
        scanner.scan_gallery_duplicates(root)


def test_reparse_name_surrogates_are_links_but_cloud_tags_are_not(tmp_path):
    assert scanner._is_link(tmp_path, SimpleNamespace(st_mode=stat.S_IFDIR, st_reparse_tag=0xA0000003))
    assert not scanner._is_link(tmp_path, SimpleNamespace(st_mode=stat.S_IFDIR, st_reparse_tag=0x9000001A))
    assert scanner._is_link(tmp_path, SimpleNamespace(st_mode=stat.S_IFLNK, st_reparse_tag=0))


def test_link_marked_models_are_skipped_not_hashed(tmp_path, monkeypatch):
    root = library(tmp_path, {"a.stl": b"abc", "b.stl": b"abc", "link.stl": b"abc"})
    original = scanner._is_link
    monkeypatch.setattr(scanner, "_is_link", lambda path, info: path.name == "link.stl" or original(path, info))
    result = scanner.scan_gallery_duplicates(root)
    assert result["skipped_links"] == 1 and result["files_examined"] == 2
    assert result["groups"][0]["paths"] == ["a.stl", "b.stl"]


def test_link_marked_selected_folder_is_rejected(tmp_path, monkeypatch):
    root = library(tmp_path, {"linked/a.stl": b"abc"})
    original = scanner._is_link
    monkeypatch.setattr(scanner, "_is_link", lambda path, info: path.name == "linked" or original(path, info))
    with pytest.raises(scanner.DuplicateScanError, match="unsafe_folder"):
        scanner.scan_gallery_duplicates(root, "linked")


def test_short_stream_reads_are_accumulated_correctly(tmp_path, monkeypatch):
    root = library(tmp_path, {"a.stl": b"abcdefghijk", "b.stl": b"abcdefghijk"})
    original = scanner.os.fdopen
    class ShortReader:
        def __init__(self, *args): self.file = original(*args)
        def __enter__(self): return self
        def __exit__(self, *args): self.file.close()
        def fileno(self): return self.file.fileno()
        def read(self, amount): return self.file.read(min(amount, 3))
    monkeypatch.setattr(scanner.os, "fdopen", ShortReader)
    result = scanner.scan_gallery_duplicates(root)
    assert result["bytes_hashed"] == 22
    assert result["groups"][0]["sha256"] == hashlib.sha256(b"abcdefghijk").hexdigest()


def test_mutated_model_during_read_fails_closed(tmp_path, monkeypatch):
    root = library(tmp_path, {"a.stl": b"abc", "b.stl": b"abc"})
    original = scanner.hashlib.sha256
    class ChangingHash:
        def __init__(self): self.value = original()
        def update(self, data):
            self.value.update(data)
            (root / "a.stl").write_bytes(b"different-size")
        def hexdigest(self): return self.value.hexdigest()
    monkeypatch.setattr(scanner.hashlib, "sha256", ChangingHash)
    with pytest.raises(scanner.DuplicateScanError, match="library_changed"):
        scanner.scan_gallery_duplicates(root)


def test_new_model_added_after_snapshot_fails_closed(tmp_path, monkeypatch):
    root = library(tmp_path, {"a.stl": b"abc", "b.stl": b"abc"})
    original = scanner.hashlib.sha256
    def adding_hash():
        (root / "new.stl").write_bytes(b"new")
        return original()
    monkeypatch.setattr(scanner.hashlib, "sha256", adding_hash)
    with pytest.raises(scanner.DuplicateScanError, match="library_changed"):
        scanner.scan_gallery_duplicates(root)


def test_read_permission_error_is_sanitized(tmp_path, monkeypatch):
    root = library(tmp_path, {"a.stl": b"abc", "b.stl": b"abc"})
    def refused(*_): raise PermissionError("private-location must not enter the API")
    monkeypatch.setattr(scanner.os, "open", refused)
    with pytest.raises(scanner.DuplicateScanError) as error:
        scanner.scan_gallery_duplicates(root)
    assert str(error.value) == "scan_io_error"


def test_hardlink_alias_is_not_an_independent_copy(tmp_path):
    root = library(tmp_path, {"a.stl": b"abc"})
    os.link(root / "a.stl", root / "linked.stl")
    group = scanner.scan_gallery_duplicates(root)["groups"][0]
    assert group["independent_copies"] == 1 and group["hardlink_aliases"] == 1
    assert group["redundant_content_bytes"] == 0


def test_streaming_never_requests_more_than_one_mebibyte(tmp_path, monkeypatch):
    payload = b"abcdefgh" * (2 * 1024 * 1024)
    root = library(tmp_path, {"a.3mf": payload, "b.3mf": payload})
    original = scanner.os.fdopen
    requests = []
    class BoundedReader:
        def __init__(self, *args): self.file = original(*args)
        def __enter__(self): return self
        def __exit__(self, *args): self.file.close()
        def fileno(self): return self.file.fileno()
        def read(self, amount):
            requests.append(amount)
            assert 0 < amount <= 1024 * 1024
            return self.file.read(amount)
    monkeypatch.setattr(scanner.os, "fdopen", BoundedReader)
    result = scanner.scan_gallery_duplicates(root)
    assert result["bytes_hashed"] == 32 * 1024 * 1024
    assert result["duplicate_groups"] == 1 and max(requests) == 1024 * 1024
