"""HACS root-source discovery is separate from artifact or install approval."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hacs_root_contract", ROOT / "packages/ultimate-ha-integration/verify_hacs_release.py")
assert spec and spec.loader
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
fixture_spec = importlib.util.spec_from_file_location("hacs_archive_contract_cases", ROOT / "tests/test_studio_hacs_release_verification.py")
assert fixture_spec and fixture_spec.loader
fixtures = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixtures)


def repository(tmp_path, files=None, *, nested=False):
    files = fixtures.fixture_files() if files is None else files
    root = tmp_path / "source"
    integration = root / ("homeassistant/custom_components" if nested else "custom_components") / v.DOMAIN
    for name, raw in files.items():
        p = integration / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    (root / "hacs.json").write_text(json.dumps({"name": "Ultimate 3D Studio", "content_in_root": False,
        "zip_release": False, "hide_default_branch": True}), encoding="utf-8")
    return root, {name: sha256(raw).hexdigest() for name, raw in files.items()}


def check(root, expected):
    return v.verify_repository(root, expected, expected_version="6.0.0", expected_build_id="0123456789")


def test_complete_root_source_is_read_only_and_not_a_release(tmp_path):
    root, expected = repository(tmp_path)
    before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = check(root, expected)
    assert result["repository_structure_verified"] is True
    assert result["release_filename"] is None
    assert result["release_asset_verified"] is False
    assert result["installation_verified"] is False
    assert result["product_release_complete"] is False
    assert result["relative_imports_verified"] == 1
    assert {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


def test_existing_nested_public_layout_is_not_discovered(tmp_path):
    root, expected = repository(tmp_path, nested=True)
    with pytest.raises(v.HacsReleaseError, match="root integration directory missing"):
        check(root, expected)


@pytest.mark.parametrize("missing", ["__init__.py", "config_flow.py", "assets/ultimate-3d-studio.js", "translations/de.json"])
def test_manifest_only_or_partial_projection_is_not_complete(tmp_path, missing):
    root, expected = repository(tmp_path)
    (root / "custom_components" / v.DOMAIN / missing).unlink()
    with pytest.raises(v.HacsReleaseError):
        check(root, expected)


@pytest.mark.parametrize("change", ["second_integration", "extra_file", "changed_bytes", "wrong_domain", "wrong_version", "missing_documentation", "invalid_hacs", "content_in_root"])
def test_repository_contract_rejects_wrong_sources(tmp_path, change):
    files = fixtures.fixture_files()
    if change in ("wrong_domain", "wrong_version", "missing_documentation"):
        manifest = json.loads(files["manifest.json"])
        if change == "wrong_domain": manifest["domain"] = "other"
        if change == "wrong_version": manifest["version"] = "9.0.0"
        if change == "missing_documentation": del manifest["documentation"]
        files["manifest.json"] = json.dumps(manifest).encode()
    root, expected = repository(tmp_path, files)
    if change == "second_integration": (root / "custom_components/other").mkdir()
    if change == "extra_file": (root / "custom_components" / v.DOMAIN / "extra.py").write_text("pass\n")
    if change == "changed_bytes": (root / "custom_components" / v.DOMAIN / "backend.py").write_text("ready=False\n")
    if change in ("invalid_hacs", "content_in_root"):
        hacs = json.loads((root / "hacs.json").read_text())
        hacs["zip_release" if change == "invalid_hacs" else "content_in_root"] = 1 if change == "invalid_hacs" else True
        (root / "hacs.json").write_text(json.dumps(hacs))
    with pytest.raises(v.HacsReleaseError):
        check(root, expected)


@pytest.mark.parametrize("limit", ["MAX_ENTRIES", "MAX_MEMBER_BYTES", "MAX_TOTAL_BYTES"])
def test_repository_reading_is_bounded(tmp_path, monkeypatch, limit):
    root, expected = repository(tmp_path)
    monkeypatch.setattr(v, limit, 1)
    with pytest.raises(v.HacsReleaseError): check(root, expected)


def test_canonical_manifest_has_required_publication_fields():
    manifest = json.loads((ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio/manifest.json").read_text())
    assert manifest["domain"] == v.DOMAIN
    assert manifest["name"] == "Ultimate 3D Studio"
    assert isinstance(manifest["codeowners"], list)
    assert manifest["documentation"] == "https://github.com/Taracraft/3D-Ultimate-Center"
    assert manifest["issue_tracker"] == "https://github.com/Taracraft/3D-Ultimate-Center/issues"
    assert manifest["version"] == json.loads((ROOT / "package.json").read_text())["version"]


def test_selected_repository_metadata_uses_normal_hacs_downloads():
    hacs = json.loads((ROOT / "packages/ultimate-ha-integration/hacs.json").read_text())
    assert hacs == {"name": "Ultimate 3D Studio", "content_in_root": False, "render_readme": True,
                   "zip_release": False, "hide_default_branch": True}


@pytest.mark.parametrize("metadata", [
    {"name": "Ultimate 3D Studio", "content_in_root": False},
    {"name": "Ultimate 3D Studio", "content_in_root": False,
     "zip_release": True, "filename": "ultimate-3d-studio.zip"},
])
def test_repository_verification_supports_default_and_legacy_zip_metadata(tmp_path, metadata):
    root, expected = repository(tmp_path)
    (root / "hacs.json").write_text(json.dumps(metadata))
    result = check(root, expected)
    assert result["repository_structure_verified"] is True
    assert result["release_filename"] == metadata.get("filename")
    assert result["release_asset_verified"] is False


@pytest.mark.parametrize("metadata", [
    {"name": "Ultimate 3D Studio", "zip_release": True},
    {"name": "Ultimate 3D Studio", "zip_release": 1},
    {"name": "Ultimate 3D Studio", "zip_release": None},
    {"name": "Ultimate 3D Studio", "zip_release": False, "filename": "unused.zip"},
])
def test_repository_metadata_rejects_ambiguous_modes(tmp_path, metadata):
    root, expected = repository(tmp_path)
    (root / "hacs.json").write_text(json.dumps(metadata))
    with pytest.raises(v.HacsReleaseError):
        check(root, expected)


@pytest.mark.parametrize("metadata", [
    {"name": "Ultimate 3D Studio", "zip_release": False},
    {"name": "Ultimate 3D Studio"},
])
def test_zip_verification_rejects_normal_metadata_before_archive_access(tmp_path, monkeypatch, metadata):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("repository metadata must not access an archive")
    monkeypatch.setattr(v, "_regular_file", forbidden)
    monkeypatch.setattr(v.zipfile, "ZipFile", forbidden)
    with pytest.raises(v.HacsReleaseError, match="zip_release must be explicitly true"):
        v.verify_release(tmp_path / "not-created.zip", metadata, {},
            expected_version="6.0.0", expected_build_id="0123456789",
            expected_archive_sha256="a" * 64)
    assert not (tmp_path / "not-created.zip").exists()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO contract")
@pytest.mark.parametrize("reader", ["metadata", "member"])
def test_special_files_are_rejected_without_blocking(tmp_path, reader):
    fifo = tmp_path / "input"
    os.mkfifo(fifo)
    module = ROOT / "packages/ultimate-ha-integration/verify_hacs_release.py"
    code = '''import importlib.util,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('fifo_contract',sys.argv[1])
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
try:
 if sys.argv[3]=='metadata': m._metadata(Path(sys.argv[2]))
 else:
  with m._regular_file(Path(sys.argv[2]),100) as f: f.read(1)
except m.HacsReleaseError:
 sys.exit(0)
sys.exit(2)
'''
    result = subprocess.run([sys.executable, "-c", code, str(module), str(fifo), reader], timeout=3, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_second_inventory_walk_has_the_same_entry_limit(tmp_path, monkeypatch):
    root, expected = repository(tmp_path)
    original = v._repository_members
    calls = 0
    def changed(integration):
        nonlocal calls
        calls += 1
        if calls == 2:
            for i in range(v.MAX_ENTRIES + 1):
                (integration / ("late" + str(i))).mkdir()
        yield from original(integration)
    monkeypatch.setattr(v, "MAX_ENTRIES", 30)
    monkeypatch.setattr(v, "_repository_members", changed)
    with pytest.raises(v.HacsReleaseError, match="too many"):
        check(root, expected)


def test_single_domain_probe_does_not_materialize_path_iterator(tmp_path, monkeypatch):
    root, expected = repository(tmp_path)
    def forbidden(_path):
        raise AssertionError("use bounded scandir instead of Path.iterdir")
    monkeypatch.setattr(Path, "iterdir", forbidden)
    assert check(root, expected)["repository_structure_verified"]
