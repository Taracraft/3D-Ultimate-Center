"""Gallery transfer guards preserve source files before any destructive overwrite."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

from tests.test_v6_gallery_repository import repository_module

_spec = importlib.util.spec_from_file_location(
    repository_module.__package__ + ".gallery_repository_v2",
    Path(repository_module.__file__).with_name("gallery_repository_v2.py"),
)
assert _spec and _spec.loader
repository_v2 = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = repository_v2
_spec.loader.exec_module(repository_v2)


def _repository(tmp_path: Path):
    repo = repository_v2.V6GalleryRepositoryV2(tmp_path / "gallery")
    repo.create_folder("", "part")
    repo.create_folder("part", "part")
    repo.upload("model.stl", b"original bytes", "part/part")
    return repo


def _deny_destructive_calls(monkeypatch):
    def deny(*_args, **_kwargs):
        raise AssertionError("Unsafe transfer reached a filesystem mutation")

    monkeypatch.setattr(repository_module.shutil, "rmtree", deny)
    monkeypatch.setattr(repository_module.shutil, "copytree", deny)
    monkeypatch.setattr(repository_module.shutil, "copy2", deny)
    monkeypatch.setattr(Path, "rename", deny)
    monkeypatch.setattr(Path, "unlink", deny)


@pytest.mark.parametrize("path", [".", "./", "/./", "././", "path:Lg", "path:Li8", "path:Ly4v", "path:"])
def test_gallery_root_cannot_be_resolved_as_a_mutable_item(tmp_path, path):
    repo = _repository(tmp_path)
    with pytest.raises(ValueError):
        repo.resolve(path)
    assert (repo.root / "part/part/model.stl").read_bytes() == b"original bytes"


def test_gallery_root_symlink_cannot_be_resolved_as_a_mutable_item(tmp_path):
    repo = _repository(tmp_path)
    (repo.root / "root-alias").symlink_to(repo.root, target_is_directory=True)
    with pytest.raises(ValueError):
        repo.resolve("root-alias")


@pytest.mark.parametrize("operation", ["copy", "move"])
@pytest.mark.parametrize("destination", ["part", "part/part", "./part/", "path:ignored"])
def test_folder_transfer_cannot_target_itself_or_a_descendant(tmp_path, monkeypatch, operation, destination):
    repo = _repository(tmp_path)
    if destination == "path:ignored":
        # The source accepts an encoded asset id; destination paths remain paths.
        source = repo.asset_id("part")
        destination = "part"
    else:
        source = "part"
    _deny_destructive_calls(monkeypatch)
    with pytest.raises(ValueError):
        getattr(repo, operation)(source, destination, overwrite=True)


@pytest.mark.parametrize("operation", ["copy", "move"])
@pytest.mark.parametrize("source", ["part/part", "path:cGFydC9wYXJ0"])
def test_overwrite_never_removes_an_ancestor_containing_the_source(tmp_path, monkeypatch, operation, source):
    repo = _repository(tmp_path)
    _deny_destructive_calls(monkeypatch)
    with pytest.raises(ValueError):
        getattr(repo, operation)(source, "", overwrite=True)


@pytest.mark.parametrize("operation", ["copy", "move"])
def test_overwrite_file_cannot_replace_its_own_parent_directory(tmp_path, monkeypatch, operation):
    repo = _repository(tmp_path)
    repo.create_folder("", "same.stl")
    repo.upload("same.stl", b"original bytes", "same.stl")
    _deny_destructive_calls(monkeypatch)
    with pytest.raises(ValueError):
        getattr(repo, operation)("same.stl/same.stl", "", overwrite=True)


@pytest.mark.parametrize("operation", ["copy", "move"])
@pytest.mark.parametrize("kind", ["file", "folder"])
def test_unrelated_destination_still_accepts_explicit_overwrite(tmp_path, operation, kind):
    repo = _repository(tmp_path)
    repo.create_folder("", "target")
    if kind == "folder":
        source = "part/part"
        repo.create_folder("target", "part")
        repo.upload("old.stl", b"old bytes", "target/part")
        expected = repo.root / "target/part/model.stl"
    else:
        source = "part/part/model.stl"
        repo.upload("model.stl", b"old bytes", "target")
        expected = repo.root / "target/model.stl"
    result = getattr(repo, operation)(source, "target", overwrite=True)
    assert expected.read_bytes() == b"original bytes"
    assert result["path"] == (expected.parent.relative_to(repo.root).as_posix() if kind == "folder" else expected.relative_to(repo.root).as_posix())
    assert (repo.root / source).exists() is (operation == "copy")


def test_move_to_current_parent_still_preserves_existing_noop_semantics(tmp_path):
    repo = _repository(tmp_path)
    result = repo.move("part/part/model.stl", "part/part", overwrite=True)
    assert result["path"] == "part/part/model.stl"
    assert (repo.root / result["path"]).read_bytes() == b"original bytes"


def test_copy_to_current_parent_is_rejected_before_any_overwrite(tmp_path, monkeypatch):
    repo = _repository(tmp_path)
    _deny_destructive_calls(monkeypatch)
    with pytest.raises(ValueError):
        repo.copy("part/part/model.stl", "part/part", overwrite=True)
