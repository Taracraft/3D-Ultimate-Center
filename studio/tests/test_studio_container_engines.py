"""Engine path checks use synthetic files; no slicer is executed."""
import importlib.util
import os
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("studio_container_engines", ROOT / "Slicer-Server/container_engines.py")
engines = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engines)

def installed(store, name):
    binary = store / name / engines.ENGINES[name][1]
    binary.parent.mkdir(parents=True)
    binary.write_text("# synthetic file; must never execute\n")
    binary.chmod(0o755)
    return binary

@pytest.mark.parametrize("name", list(engines.ENGINES))
def test_resolve_and_inventory_agree_without_execution(tmp_path, name):
    binary = installed(tmp_path, name)
    value = engines.resolve_engine(name, tmp_path)
    inventory = engines.available_engines(tmp_path)
    assert value == {"root": str(binary.parent.parent.resolve()), "binary": str(binary.resolve())}
    assert len(inventory) == 1 and inventory[0]["id"] == name
    assert inventory[0]["path"] == value["binary"]
    assert inventory[0]["version"] == "unknown"

@pytest.mark.parametrize("name", ["other", "../prusaslicer", "", None])
def test_unknown_engine_cannot_select_a_path(tmp_path, name):
    with pytest.raises(engines.EnginePathError, match="unknown_engine"):
        engines.resolve_engine(name, tmp_path)

def test_missing_engine_does_not_fall_back_to_path(tmp_path, monkeypatch):
    binary = installed(tmp_path / "outside", "prusaslicer")
    monkeypatch.setenv("PATH", str(binary.parent))
    with pytest.raises(engines.EnginePathError, match="unavailable"):
        engines.resolve_engine("prusaslicer", tmp_path / "empty")
    assert engines.available_engines(tmp_path / "empty") == []

def test_directory_is_not_an_engine(tmp_path):
    (tmp_path / "curaengine/bin/CuraEngine").mkdir(parents=True)
    with pytest.raises(engines.EnginePathError, match="not_regular"):
        engines.resolve_engine("curaengine", tmp_path)

@pytest.mark.skipif(sys.platform == "win32", reason="Windows does not preserve executable permission bits")
def test_nonexecutable_file_is_unavailable(tmp_path):
    installed(tmp_path, "curaengine").chmod(0o644)
    with pytest.raises(engines.EnginePathError, match="not_executable"):
        engines.resolve_engine("curaengine", tmp_path)
    assert engines.available_engines(tmp_path) == []

@pytest.mark.skipif(sys.platform == "win32", reason="Windows symlinks require extra privileges")
@pytest.mark.parametrize("level", ["store", "family", "bin", "binary"])
def test_linked_paths_are_rejected_even_inside_store(tmp_path, level):
    store = tmp_path / "store"
    binary = installed(store, "prusaslicer")
    path = {"store": store, "family": binary.parent.parent,
            "bin": binary.parent, "binary": binary}[level]
    moved = path.with_name(path.name + "-saved")
    path.rename(moved)
    path.symlink_to(moved, target_is_directory=moved.is_dir())
    with pytest.raises(engines.EnginePathError, match="linked_engine_path"):
        engines.resolve_engine("prusaslicer", store)
    assert engines.available_engines(store) == []

def test_invalid_one_does_not_hide_other_engines(tmp_path):
    installed(tmp_path, "prusaslicer")
    installed(tmp_path, "curaengine")
    assert [row["id"] for row in engines.available_engines(tmp_path)] == ["prusaslicer", "curaengine"]


@pytest.mark.parametrize("name", list(engines.ENGINES))
@pytest.mark.parametrize("link_kind", ["symlink", "junction"])
def test_linked_store_parent_is_rejected_before_resolving(tmp_path, monkeypatch, name, link_kind):
    store = tmp_path / "engine"
    installed(store, name)
    parent = store.parent
    method = "is_symlink" if link_kind == "symlink" else "is_junction"
    original = getattr(Path, method, lambda self: False)
    monkeypatch.setattr(Path, method, lambda self: self == parent or original(self), raising=False)
    with pytest.raises(engines.EnginePathError, match="linked_engine_path"):
        engines.resolve_engine(name, store)
    assert engines.available_engines(store) == []


@pytest.mark.skipif(sys.platform == "win32", reason="Windows symlinks require extra privileges")
@pytest.mark.parametrize("name", list(engines.ENGINES))
def test_real_linked_ancestor_cannot_redirect_to_another_store(tmp_path, name):
    actual = tmp_path / "actual"
    binary = installed(actual / "nested/engine", name)
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    # The store and its immediate parent are ordinary directories. Only the
    # grandparent is linked; the old resolver returned this foreign binary.
    store = linked / "nested/engine"
    assert not store.is_symlink() and not store.parent.is_symlink()
    with pytest.raises(engines.EnginePathError, match="linked_engine_path"):
        engines.resolve_engine(name, store)
    assert engines.available_engines(store) == []
    assert binary.read_text() == "# synthetic file; must never execute\n"
