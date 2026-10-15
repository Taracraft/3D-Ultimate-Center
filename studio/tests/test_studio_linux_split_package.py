"""Regressions for the declared component/native source split; no live reads."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("split_source_fixture", ROOT / "tests/test_studio_linux_preflight.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
mod = fixture.mod

# Independent contract: these ten source files belong to the HA component,
# while job_control.py is owned by the native worker itself.
COMPONENT_FILES = (
    "bed-temperature-contract.sh", "materialize-bambu-machine.py",
    "materialize-bambu-multimaterial.py", "three_mf_mesh_graph.py",
    "filament_parameter_contract.py", "native_filament_defaults.json",
    "slicer_execution_contract.py", "gcode_artifact_validation.py",
    "printer_model_contract.py", "h2s_native_defaults.json",
)


def split_source(root, layout):
    native, units = fixture.make_source(root, layout)
    component = root / ("homeassistant/custom_components/ultimate_3d_studio" if layout == "public"
                        else "deploy/homeassistant/custom_components/ultimate_3d_studio")
    component.mkdir(parents=True, exist_ok=True)
    # Also exposes the original flat-fixture bug before the fix: these are
    # ordinary synthetic file moves, never patches of the product under test.
    for name in COMPONENT_FILES:
        if (native / name).exists():
            assert not (component / name).exists()
            (native / name).rename(component / name)
    return native, component, units


@pytest.mark.parametrize("layout", ["canonical", "public"])
def test_declared_split_resolves_all_dependencies_without_worker_duplicates(tmp_path, layout):
    root = tmp_path / "repo"
    native, component, _ = split_source(root, layout)
    before = fixture.bytes_in(root)
    files, _ = mod.collect(root, layout)
    for name in COMPONENT_FILES:
        assert not (native / name).exists()
        assert files[name] == (component / name).read_bytes()
    assert files["job_control.py"] == (native / "job_control.py").read_bytes()
    assert before == fixture.bytes_in(root)


@pytest.mark.parametrize("layout", ["canonical", "public"])
def test_component_source_is_authoritative_over_stale_worker_copy(tmp_path, layout):
    root = tmp_path / "repo"
    native, component, _ = split_source(root, layout)
    for name in COMPONENT_FILES:
        (native / name).write_bytes(b"obsolete duplicate must not be used\n")
    files, _ = mod.collect(root, layout)
    assert all(files[name] == (component / name).read_bytes() for name in COMPONENT_FILES)


@pytest.mark.parametrize("layout", ["canonical", "public"])
@pytest.mark.parametrize("name", COMPONENT_FILES)
def test_missing_component_file_is_not_replaced_from_worker_or_neighbor(tmp_path, layout, name):
    root = tmp_path / "repo"
    native, component, _ = split_source(root, layout)
    data = (component / name).read_bytes()
    (native / name).write_bytes(data)
    (tmp_path / name).write_bytes(data)
    (component / name).unlink()
    with pytest.raises(FileNotFoundError):
        mod.collect(root, layout)


@pytest.mark.parametrize("layout", ["canonical", "public"])
def test_native_supervisor_is_not_replaced_from_component(tmp_path, layout):
    root = tmp_path / "repo"
    native, component, _ = split_source(root, layout)
    (native / "job_control.py").rename(component / "job_control.py")
    with pytest.raises(FileNotFoundError):
        mod.collect(root, layout)


@pytest.mark.parametrize("layout", ["canonical", "public"])
def test_changed_component_bytes_fail_even_when_worker_copy_matches_manifest(tmp_path, layout):
    root = tmp_path / "repo"
    native, component, _ = split_source(root, layout)
    name = "printer_model_contract.py"
    (native / name).write_bytes((component / name).read_bytes())
    (component / name).write_bytes(b"changed model contract\n")
    with pytest.raises(mod.PreflightError, match="source_digest_mismatch:printer_model_contract.py"):
        mod.collect(root, layout)


@pytest.mark.parametrize("layout", ["canonical", "public"])
def test_split_staging_has_exact_flat_runtime_contract_without_other_components(tmp_path, layout):
    root, dest = tmp_path / "repo", tmp_path / "package"
    _, component, _ = split_source(root, layout)
    (component / "credentials.json").write_text('{"fixture_only":true}')
    before = fixture.bytes_in(root)
    report = mod.stage(root, layout, dest)
    assert report["stage_complete"] and not report["installation_performed"]
    assert not report["release_approved"]
    for name in COMPONENT_FILES:
        assert (dest / name).read_bytes() == (component / name).read_bytes()
    assert not (dest / "credentials.json").exists()
    assert not (dest / "homeassistant").exists()
    assert before == fixture.bytes_in(root)


@pytest.mark.skipif(sys.platform == "win32", reason="Symlink creation needs Windows elevation/developer mode")
@pytest.mark.parametrize("layout", ["canonical", "public"])
def test_component_directory_link_is_never_followed(tmp_path, layout):
    root = tmp_path / "repo"
    _, component, _ = split_source(root, layout)
    outside = tmp_path / "outside-component"
    component.rename(outside)
    component.symlink_to(outside, target_is_directory=True)
    with pytest.raises(mod.PreflightError, match="linked_path"):
        mod.collect(root, layout)
