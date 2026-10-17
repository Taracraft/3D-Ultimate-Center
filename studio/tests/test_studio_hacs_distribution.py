"""Private HACS package closure tests; never publishes or modifies live HA."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "packages" / "ultimate-ha-integration" / "build_hacs_preview.py"
spec = importlib.util.spec_from_file_location("studio_hacs_distribution_builder", BUILDER)
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_hacs_root_contains_only_one_integration_and_built_frontend(tmp_path):
    dest = tmp_path / "private-preview"
    result = builder.build(ROOT, dest)
    assert result["publication_approved"] is False
    assert result["security_review_complete"] is False
    assert result["fresh_HA_install_verified"] is False
    assert result["native_slicer_bundled"] is False
    assert result["frontend_assets"] == 3
    assert result["noop_modules_excluded"] >= 1
    assert result["relative_imports_verified"] >= 200
    assert {p.name for p in (dest / "custom_components").iterdir()} == {"ultimate_3d_studio"}
    manifest = json.loads(
        (dest / "custom_components/ultimate_3d_studio/manifest.json").read_text()
    )
    assert manifest["domain"] == "ultimate_3d_studio"
    assert manifest["version"] == result["version"]
    assert manifest["documentation"].startswith("https://github.com/")
    assert manifest["issue_tracker"].endswith("/issues")
    hacs = json.loads((dest / "hacs.json").read_text())
    assert hacs["name"] == "Ultimate 3D Studio"
    assert hacs["render_readme"] is True
    assets = dest / "custom_components/ultimate_3d_studio/assets"
    assert {x.name for x in assets.iterdir()} == set(builder.ASSETS)
    build = json.loads((assets / builder.ASSETS[2]).read_text())
    assert build["build_id"] == result["build_id"]
    assert builder.file_hash(assets / builder.ASSETS[0]) == build["sha256"]
    assert builder.file_hash(assets / builder.ASSETS[1]) == build["css"]["sha256"]
    assert not (dest / "packages").exists()
    assert all(not name.endswith((".bak", ".pyc", ".sh")) for name in result["file_sha256"])


def test_built_hacs_frontend_preserves_complete_earcut_isc_notice():
    license_text = (ROOT / "frontend/vendor/earcut/LICENSE").read_text(
        encoding="utf-8",
    ).strip("\r\n")
    bundle = (ROOT / "deploy/homeassistant/www/3d-studio/ultimate-3d-studio.js").read_text(
        encoding="utf-8",
    )
    assert license_text, "The original Earcut license must not be empty"
    assert license_text in bundle, "The built HACS frontend must retain the complete original Earcut ISC notice"


def test_build_is_reproducible_and_preserves_static_resource_route(tmp_path):
    a = builder.build(ROOT, tmp_path / "first")
    b = builder.build(ROOT, tmp_path / "second")
    assert a["file_sha256"] == b["file_sha256"]
    assert a["build_id"] == b["build_id"]
    first = tmp_path / "first"
    init = (first / "custom_components/ultimate_3d_studio/__init__.py").read_text()
    assert "async_register_static_paths" in init
    assert 'StaticPathConfig("/ultimate-3d-studio/assets"' in init
    assert "Installed Studio frontend assets are incomplete" in init
    js = (
        first / "custom_components/ultimate_3d_studio/assets/ultimate-3d-studio.js"
    ).read_text(encoding="utf-8")
    assert a["build_id"] in js
    assert a["version"] in js
    assert "customElements.define" in js


def test_no_existing_private_hacs_preview_is_overwritten(tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    sentinel = target / "keep"
    sentinel.write_text("never overwrite")
    with pytest.raises(FileExistsError):
        builder.build(ROOT, target)
    assert sentinel.read_text() == "never overwrite"


def test_mismatched_frontend_manifest_blocks_distribution_before_writing(
    monkeypatch, tmp_path,
):
    original = builder.file_hash
    frontend_js = (
        ROOT / "deploy/homeassistant/www/3d-studio/ultimate-3d-studio.js"
    ).resolve()

    def fake_hash(path):
        if path.resolve() == frontend_js:
            return "0" * 64
        return original(path)

    monkeypatch.setattr(builder, "file_hash", fake_hash)
    target = tmp_path / "incomplete"
    with pytest.raises(builder.HacsPreviewError, match="frontend assets differ"):
        builder.build(ROOT, target)
    assert not target.exists()


def test_version_is_derived_from_package_build_and_component_manifest():
    package = json.loads((ROOT / "package.json").read_text())
    integration = json.loads((
        ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio/manifest.json"
    ).read_text())
    build = json.loads((
        ROOT / "deploy/homeassistant/www/3d-studio/ultimate-3d-studio-build.json"
    ).read_text())
    assert package["version"] == integration["version"] == build["version"]
    assert re.fullmatch("[a-f0-9]{10}", build["build_id"])
    frontend = (ROOT / "frontend/studio-entry.ts").read_text()
    assert "Version " + "$" + "{__STUDIO_VERSION__}" in frontend
    assert "Build " + "$" + "{__STUDIO_BUILD_ID__}" in frontend
    const = (
        ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio/const.py"
    ).read_text()
    assert 'Path(__file__).with_name("manifest.json")' in const
    assert "VERSION = str(json.loads" in const


def test_hacs_source_closure_blocks_missing_relative_import(tmp_path):
    module = tmp_path / "entry.py"
    module.write_text("from .absent_backend import run\n", encoding="utf-8")
    with pytest.raises(builder.HacsPreviewError, match="missing relative Python module"):
        builder.validate_import_closure([(module, Path("entry.py"))])


def test_hacs_source_closure_accepts_existing_internal_import(tmp_path):
    root = tmp_path / "component"
    root.mkdir()
    backend = root / "backend.py"
    backend.write_text("def run(): return True\n", encoding="utf-8")
    caller = root / "main.py"
    caller.write_text("from .backend import run\n", encoding="utf-8")
    assert builder.validate_import_closure(
        [(backend, Path("backend.py")), (caller, Path("main.py"))]
    ) == 1


def test_noop_python_stub_is_excluded_only_if_no_behavior(tmp_path):
    noop = tmp_path / "legacy_stub.py"
    noop.write_text('"""Removed compatibility shell. No runtime behavior."""\n')
    active = tmp_path / "active.py"
    active.write_text('"""Active component."""\nFEATURE_ENABLED = True\n')
    assert builder._is_noop_module(noop) is True
    assert builder._is_noop_module(active) is False


def test_private_hacs_preview_contains_no_docstring_only_python_modules(tmp_path):
    preview = tmp_path / "private-preview"
    outcome = builder.build(ROOT, preview)
    integration = preview / "custom_components" / "ultimate_3d_studio"
    assert outcome["noop_modules_excluded"] >= 1
    assert all(
        not builder._is_noop_module(path)
        for path in integration.rglob("*.py")
    )


def test_output_created_concurrently_is_never_removed_by_failure_cleanup(monkeypatch, tmp_path):
    target = tmp_path / "concurrent-preview"
    sentinel = target / "keep-original"
    original_exists = Path.exists
    armed = True
    def raced_exists(path):
        nonlocal armed
        if path == target and armed:
            armed = False
            (target / "custom_components" / "ultimate_3d_studio").mkdir(parents=True)
            sentinel.write_bytes(b"unrelated original bytes")
            return False
        return original_exists(path)
    monkeypatch.setattr(Path, "exists", raced_exists)
    with pytest.raises(FileExistsError):
        builder.build(ROOT, target)
    assert sentinel.read_bytes() == b"unrelated original bytes"


@pytest.mark.parametrize("changed", ["source", "asset", "buildmanifest"])
def test_input_drift_after_import_review_is_rejected_before_output(monkeypatch, tmp_path, changed):
    target = tmp_path / ("drift-" + changed)
    paths = {
        "source": ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio/const.py",
        "asset": ROOT / "deploy/homeassistant/www/3d-studio/ultimate-3d-studio.js",
        "buildmanifest": ROOT / "deploy/homeassistant/www/3d-studio/ultimate-3d-studio-build.json",
    }
    victim = paths[changed]
    original_review = builder.validate_import_closure
    original_read = Path.read_bytes
    reviewed = False
    def review(sources):
        nonlocal reviewed
        result = original_review(sources)
        reviewed = True
        return result
    def read(path):
        raw = original_read(path)
        if path == victim and reviewed:
            return raw + (b" " if changed == "buildmanifest" else b"\n; synthetic changed bytes\n")
        return raw
    monkeypatch.setattr(builder, "validate_import_closure", review)
    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(builder.HacsPreviewError):
        builder.build(ROOT, target)
    assert not target.exists()
