"""Studio gallery write paths must never use the independent legacy archive.

No Home Assistant runtime, printer, existing gallery or real user files touched.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"
DOMAIN = "ultimate_3d_studio"
WRITERS = (
    "gallery_management_views.py",
    "gallery_management_views_v2.py",
    "gallery_duplicate_views.py",
)


@pytest.fixture
def storage(monkeypatch):
    package_name = "isolated_studio_gallery_path_contract"
    package = ModuleType(package_name)
    package.__path__ = [str(COMPONENT)]
    constants = ModuleType(package_name + ".const")
    constants.DOMAIN = DOMAIN
    monkeypatch.setitem(sys.modules, package_name, package)
    monkeypatch.setitem(sys.modules, constants.__name__, constants)
    name = package_name + ".gallery_storage_paths"
    spec = importlib.util.spec_from_file_location(name, COMPONENT / "gallery_storage_paths.py")
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, loaded)
    spec.loader.exec_module(loaded)
    return loaded


def _hass(root: Path):
    return SimpleNamespace(config=SimpleNamespace(path=lambda *parts: str(root.joinpath(*parts))))


def test_legacy_gallery_is_not_modified_when_writing_studio_owned_files(tmp_path, storage):
    hass = _hass(tmp_path)
    old_archive = tmp_path / "printer_control_center" / "archive"
    old_archive.mkdir(parents=True)
    old_model = old_archive / "example.3mf"
    old_model.write_bytes(b"immutable legacy model")

    current = storage.studio_gallery_root(hass)
    transfers = storage.studio_upload_session_root(hass)
    assert current == tmp_path / DOMAIN / "gallery"
    assert transfers == tmp_path / DOMAIN / "upload_sessions"
    assert not current.exists() and not transfers.exists(), "helper must remain read-only"
    current.mkdir(parents=True)
    transfers.mkdir(parents=True)
    (current / "new-model.3mf").write_bytes(b"new studio model")
    (transfers / "upload.part").write_bytes(b"new upload")
    assert old_model.read_bytes() == b"immutable legacy model"
    assert list(old_archive.iterdir()) == [old_model]


def test_gallery_paths_are_fully_portable_and_not_site_specific(tmp_path, storage):
    hass = _hass(tmp_path)
    assert storage.studio_gallery_root(hass).is_relative_to(tmp_path / DOMAIN)
    assert storage.studio_upload_session_root(hass).is_relative_to(tmp_path / DOMAIN)
    for writer in WRITERS:
        text = (COMPONENT / writer).read_text(encoding="utf-8-sig")
        assert "from .gallery_storage_paths import" in text
        assert 'hass.config.path("printer_control_center"' not in text


def test_linked_studio_root_is_rejected(storage, tmp_path):
    hass = _hass(tmp_path)
    # Deterministic cross-platform symlink simulation; no privilege required.
    original = Path.is_symlink

    def fake_link(path):
        if path == tmp_path / DOMAIN:
            return True
        return original(path)

    from unittest.mock import patch
    with patch.object(Path, "is_symlink", fake_link):
        with pytest.raises(ValueError, match="linked_studio_storage_not_allowed"):
            storage.studio_gallery_root(hass)


def test_unknown_storage_categories_are_never_accepted(tmp_path, storage):
    with pytest.raises(ValueError, match="invalid_studio_storage_category"):
        storage._studio_data_path(_hass(tmp_path), "../legacy")
