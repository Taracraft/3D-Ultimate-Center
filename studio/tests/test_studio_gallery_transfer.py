"""Safeguard first-run migration of existing galleries to the Studio-owned root.

All fixtures are local temporary directories. Historical source is NEVER altered.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packages" / "ultimate-ha-integration" / "copy_gallery_library.py"
spec = importlib.util.spec_from_file_location("studio_gallery_transfer", SCRIPT)
assert spec is not None and spec.loader is not None
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)


@pytest.fixture
def example(tmp_path):
    source = tmp_path / "previous" / "archive"
    source.mkdir(parents=True)
    (source / "old.3mf").write_bytes(b"old-model-original")
    nested = source / "owned-folder"
    nested.mkdir()
    (nested / "part.stl").write_bytes(b"binary-mesh-model")
    (source / "empty-folder").mkdir()
    (source / "metadata.json").write_text('{"source":"legacy"}', encoding="utf-8")
    parent = tmp_path / "ultimate_3d_studio"
    parent.mkdir()
    target = parent / "gallery"
    return source, target


def test_gallery_transfer_preflight_is_read_only(example):
    source, target = example
    state = {p.relative_to(source).as_posix(): p.read_bytes()
             for p in source.rglob("*") if p.is_file()}
    report = transfer.copy_gallery(source, target)
    assert report["copy_performed"] is False
    assert report["source_files"] == 3
    assert report["source_directories"] == 2
    assert report["source_read_only"] is True
    assert not target.exists()
    assert {p.relative_to(source).as_posix(): p.read_bytes()
            for p in source.rglob("*") if p.is_file()} == state


def test_gallery_transfer_copies_every_file_and_empty_folder_without_source_writes(example):
    source, target = example
    before = {p.relative_to(source).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
              for p in source.rglob("*") if p.is_file()}
    report = transfer.copy_gallery(source, target, apply=True)
    assert report["copy_performed"] is True
    assert report["integrity_verified"] is True
    for relative, (blob, mtime) in before.items():
        assert (target / relative).read_bytes() == blob
        assert (target / relative).stat().st_mtime_ns == mtime
        assert (source / relative).read_bytes() == blob
    assert (target / "empty-folder").is_dir()
    assert {p.relative_to(source).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in source.rglob("*") if p.is_file()} == before
    assert not list(target.parent.glob(".studio-gallery-transfer-*"))


def test_existing_destination_is_never_overwritten(example):
    source, target = example
    target.mkdir()
    sentinel = target / "precious-model.3mf"
    sentinel.write_bytes(b"do-not-touch")
    with pytest.raises(transfer.GalleryCopyError, match="already exists"):
        transfer.copy_gallery(source, target, apply=True)
    assert sentinel.read_bytes() == b"do-not-touch"
    assert (source / "old.3mf").read_bytes() == b"old-model-original"


def test_overlap_source_and_target_is_refused(example):
    source, _target = example
    with pytest.raises(transfer.GalleryCopyError, match="disjoint"):
        transfer.copy_gallery(source, source / "copy")


def test_symlinked_file_is_not_copied(example):
    source, target = example
    link = source / "external.stl"
    try:
        link.symlink_to(source / "old.3mf")
    except (OSError, NotImplementedError):
        pytest.skip("OS cannot create symbolic links")
    with pytest.raises(transfer.GalleryCopyError, match="linked"):
        transfer.copy_gallery(source, target, apply=True)
    assert not target.exists()


def test_source_file_changed_during_inventory_is_detected(example, monkeypatch):
    source, target = example
    real_hash = transfer._hash_file
    modified = False

    def tamper_during_read(path):
        nonlocal modified
        digest = real_hash(path)
        if path.name == "old.3mf" and not modified:
            modified = True
            path.write_bytes(path.read_bytes() + b"modified-concurrently")
        return digest

    monkeypatch.setattr(transfer, "_hash_file", tamper_during_read)
    with pytest.raises(transfer.GalleryCopyError, match="changed during inventory"):
        transfer.copy_gallery(source, target)
    assert modified
    assert not target.exists()


def test_legacy_compatibility_catalog_remains_read_only():
    catalog = (
        ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio/gallery_runtime.py"
    ).read_text(encoding="utf-8-sig")
    assert '"studio": Path(hass.config.path("ultimate_3d_studio", "gallery"))' in catalog
    assert '"v5": Path(hass.config.path("printer_control_center", "archive"))' in catalog
    assert "self._roots[\"studio\"].mkdir(" in catalog
    assert 'self._roots["v5"].mkdir(' not in catalog



def test_source_and_destination_can_be_on_different_filesystems(example, monkeypatch):
    source, target = example
    original = Path.stat

    class OtherDevice:
        def __init__(self, result):
            self._original = result

        def __getattr__(self, name):
            if name == "st_dev":
                return self._original.st_dev + 100
            return getattr(self._original, name)

    def different_device(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        return OtherDevice(info) if path == source else info

    monkeypatch.setattr(Path, "stat", different_device)
    report = transfer.copy_gallery(source, target, apply=False)
    assert report["source_files"] == 3
    assert report["copy_performed"] is False
    assert not target.exists()
    assert (source / "old.3mf").read_bytes() == b"old-model-original"
