"""Metadata race regressions for the offline backup verifier."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "tools" / "studio_backup_verify.py"
spec = importlib.util.spec_from_file_location("studio_backup_identity", MODULE)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stat_double(record, **changes):
    from types import SimpleNamespace
    values = {name: getattr(record, name) for name in
              ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode")}
    return SimpleNamespace(**{**values, **changes})


def test_cross_api_timestamp_representation_keeps_file_identity(tmp_path, monkeypatch):
    path = tmp_path / "stable"
    path.write_bytes(b"same bytes")
    original = verifier.os.fstat
    def descriptor_stat(fd):
        item = original(fd)
        return stat_double(item, st_ctime_ns=item.st_ctime_ns + 100,
                           st_mtime_ns=item.st_mtime_ns + 100)
    monkeypatch.setattr(verifier.os, "fstat", descriptor_stat)
    assert verifier.file_record(path) == {"size": 10, "sha256": sha(b"same bytes")}


@pytest.mark.parametrize("field", ["st_ctime_ns", "st_mtime_ns", "st_ino", "st_size"])
def test_same_descriptor_metadata_changes_still_fail(tmp_path, monkeypatch, field):
    path = tmp_path / "changing"
    path.write_bytes(b"same bytes")
    original, calls = verifier.os.fstat, 0
    def descriptor_stat(fd):
        nonlocal calls
        calls += 1
        item = original(fd)
        return stat_double(item, **{field: getattr(item, field) + (calls > 1)})
    monkeypatch.setattr(verifier.os, "fstat", descriptor_stat)
    with pytest.raises(verifier.VerificationError, match="snapshot_changed"):
        verifier.file_record(path)


def test_descriptor_must_bind_to_the_inventoried_file(tmp_path, monkeypatch):
    path = tmp_path / "binding"
    path.write_bytes(b"same bytes")
    original = verifier.os.fstat
    def descriptor_stat(fd):
        item = original(fd)
        return stat_double(item, st_ino=item.st_ino + 1)
    monkeypatch.setattr(verifier.os, "fstat", descriptor_stat)
    with pytest.raises(verifier.VerificationError, match="snapshot_changed"):
        verifier.file_record(path)


def test_pathname_metadata_changes_still_fail(tmp_path, monkeypatch):
    path = tmp_path / "path-change"
    path.write_bytes(b"same bytes")
    original, calls = Path.lstat, 0
    def pathname_stat(self):
        nonlocal calls
        item = original(self)
        if self == path:
            calls += 1
            if calls > 1:
                return stat_double(item, st_mtime_ns=item.st_mtime_ns + 1)
        return item
    monkeypatch.setattr(Path, "lstat", pathname_stat)
    with pytest.raises(verifier.VerificationError, match="snapshot_changed"):
        verifier.file_record(path)
