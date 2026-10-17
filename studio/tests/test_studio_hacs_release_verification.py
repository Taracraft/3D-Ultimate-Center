"""Artifact-bound read-only HACS checks; no installed HA or release production."""
import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import stat
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "studio_hacs_release_verifier",
    ROOT / "packages/ultimate-ha-integration/verify_hacs_release.py",
)
assert spec and spec.loader
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def fixture_files():
    js, css = b"customElements.define('test-card', class {});", b":host{display:block}"
    build = {"version": "6.0.0", "build_id": "0123456789",
             "sha256": sha256(js).hexdigest(), "size_bytes": len(js),
             "css": {"sha256": sha256(css).hexdigest(), "size_bytes": len(css)}}
    return {"__init__.py": b"from .backend import ready\n",
            "backend.py": b"ready = True\n", "config_flow.py": b"CONFIG = True\n",
            "manifest.json": json.dumps({"domain": v.DOMAIN, "version": "6.0.0", "config_flow": True,
                "name": "Ultimate 3D Studio", "codeowners": ["@Taracraft"],
                "documentation": "https://github.com/Taracraft/3D-Ultimate-Center",
                "issue_tracker": "https://github.com/Taracraft/3D-Ultimate-Center/issues"}).encode(),
            "strings.json": b"{}", "translations/de.json": b"{}", "translations/en.json": b"{}",
            "assets/" + v.ASSETS[0]: js, "assets/" + v.ASSETS[1]: css,
            "assets/" + v.ASSETS[2]: json.dumps(build).encode()}


def artifact(tmp_path, files=None, *, prefix="", extra=(), mode=None):
    files = fixture_files() if files is None else files
    target = tmp_path / "ultimate-studio.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for name, raw in files.items():
            info = zipfile.ZipInfo(prefix + name)
            if mode is not None:
                info.create_system = 3
                info.external_attr = mode << 16
            z.writestr(info, raw)
        for name, raw in extra:
            z.writestr(name, raw)
    return target, {name: sha256(raw).hexdigest() for name, raw in files.items()}


def check(target, expected, **kwargs):
    return v.verify_release(target, kwargs.pop("hacs", {"name": "Ultimate 3D Studio", "zip_release": True, "filename": target.name}),
                            expected, expected_version=kwargs.pop("version", "6.0.0"),
                            expected_build_id="0123456789",
                            expected_archive_sha256=kwargs.pop("pin", sha256(target.read_bytes()).hexdigest()), **kwargs)


@pytest.mark.parametrize("prefix", ["", "./"])
def test_exact_root_and_official_dot_root_are_read_only(tmp_path, monkeypatch, prefix):
    target, expected = artifact(tmp_path, prefix=prefix)
    before = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    def forbidden(*_args, **_kwargs):
        raise AssertionError("must never extract or execute")
    monkeypatch.setattr(zipfile.ZipFile, "extractall", forbidden)
    monkeypatch.setattr(zipfile.ZipFile, "extract", forbidden)
    outcome = check(target, expected)
    assert outcome["artifact_contract_verified"] is True
    assert outcome["relative_imports_verified"] == 1
    assert outcome["publication_approved"] is False
    assert outcome["installation_verified"] is False
    assert outcome["product_release_complete"] is False
    after = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert after == before


@pytest.mark.parametrize("prefix", ["custom_components/ultimate_3d_studio/", "ultimate_3d_studio/"])
def test_private_preview_wrapper_is_not_a_release_zip(tmp_path, prefix):
    target, expected = artifact(tmp_path, prefix=prefix)
    with pytest.raises(v.HacsReleaseError, match="integration-root"):
        check(target, expected)


@pytest.mark.parametrize("name", ["../escape.py", "/absolute.py", "C:/drive.py", "a\\b.py", "a/../b.py", "a//b.py", "a./file.py", "a /file.py", "bad\x00.py"])
def test_unsafe_names_rejected_without_extracting(tmp_path, name):
    target, expected = artifact(tmp_path, extra=[(name, b"X")])
    with pytest.raises(v.HacsReleaseError):
        check(target, expected)
    assert {x.name for x in tmp_path.iterdir()} == {target.name}


@pytest.mark.parametrize("name", ["/", ".//"])
def test_absolute_root_directory_is_rejected(tmp_path, name):
    target, expected = artifact(tmp_path, extra=[(name, b"")])
    with pytest.raises(v.HacsReleaseError, match="unsafe"):
        check(target, expected)


@pytest.mark.parametrize("source", [b"from . import FLAG\n", b"from . import *\n"])
def test_package_attribute_import_is_not_a_missing_module(tmp_path, source):
    files = fixture_files()
    files["__init__.py"] = b"FLAG = True\n"
    files["consumer.py"] = source
    target, expected = artifact(tmp_path, files)
    assert check(target, expected)["artifact_contract_verified"]


def test_large_json_integer_is_normalized():
    with pytest.raises(v.HacsReleaseError):
        v._json(b'{"n":' + b'9' * 10000 + b'}')


def test_exponent_overflow_is_not_finite_json():
    with pytest.raises(v.HacsReleaseError, match="non-finite"):
        v._json(b'{"n":1e9999}')


def test_corrupt_deflate_is_normalized(tmp_path):
    files = fixture_files()
    target = tmp_path / "ultimate-studio.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for name, raw in files.items(): z.writestr(name, raw)
    raw = bytearray(target.read_bytes())
    with zipfile.ZipFile(target) as z:
        entry = z.infolist()[0]
        offset = entry.header_offset + 30 + len(entry.filename.encode()) + len(entry.extra)
    raw[offset:offset + 2] = b'\xff\xff'
    target.write_bytes(raw)
    with pytest.raises(v.HacsReleaseError):
        check(target, {n: sha256(b).hexdigest() for n, b in files.items()})


def test_cli_metadata_has_a_separate_size_limit(tmp_path, monkeypatch):
    path = tmp_path / "metadata.json"
    path.write_bytes(b"{\"a\":\"" + b"x" * 100 + b"\"}")
    monkeypatch.setattr(v, "MAX_METADATA_BYTES", 20)
    with pytest.raises(v.HacsReleaseError, match="metadata exceeds"):
        v._metadata(path)


@pytest.mark.parametrize("field,value", [("documentation", 42), ("issue_tracker", True)])
def test_invalid_url_value_is_a_contract_error(tmp_path, field, value):
    files = fixture_files()
    manifest = json.loads(files["manifest.json"])
    manifest[field] = value
    files["manifest.json"] = json.dumps(manifest).encode()
    target, expected = artifact(tmp_path, files)
    with pytest.raises(v.HacsReleaseError, match="documentation URL"):
        check(target, expected)


@pytest.mark.parametrize("name", ["__init__.py", "./__init__.py", "BACKEND.py"])
def test_duplicate_and_case_aliases_are_rejected(tmp_path, name):
    with pytest.warns(UserWarning) if name == "__init__.py" else _no_warning():
        target, expected = artifact(tmp_path, extra=[(name, b"pass\n")])
    with pytest.raises(v.HacsReleaseError, match="duplicate or aliased"):
        check(target, expected)


def _no_warning():
    from contextlib import nullcontext
    return nullcontext()


@pytest.mark.parametrize("mode", [stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o600])
def test_links_and_special_entries_are_rejected(tmp_path, mode):
    target, expected = artifact(tmp_path, mode=mode)
    with pytest.raises(v.HacsReleaseError, match="special"):
        check(target, expected)


@pytest.mark.parametrize("changed", ["manifest_version", "domain", "build_version", "build_id", "js_hash", "css_size"])
def test_self_consistent_inventory_does_not_replace_release_identity(tmp_path, changed):
    files = fixture_files()
    if changed in ("manifest_version", "domain"):
        manifest = json.loads(files["manifest.json"])
        manifest["version" if changed == "manifest_version" else "domain"] = "9.0.0" if changed == "manifest_version" else "other"
        files["manifest.json"] = json.dumps(manifest).encode()
    else:
        build = json.loads(files["assets/" + v.ASSETS[2]])
        if changed == "build_version": build["version"] = "9.0.0"
        if changed == "build_id": build["build_id"] = "ffffffffff"
        if changed == "js_hash": build["sha256"] = "0" * 64
        if changed == "css_size": build["css"]["size_bytes"] = True
        files["assets/" + v.ASSETS[2]] = json.dumps(build).encode()
    target, expected = artifact(tmp_path, files)
    with pytest.raises(v.HacsReleaseError): check(target, expected)


def test_external_member_pin_detects_modified_source(tmp_path):
    original = fixture_files()
    expected = {n: sha256(b).hexdigest() for n, b in original.items()}
    original["backend.py"] = b"ready = False\n"
    target, _ = artifact(tmp_path, original)
    with pytest.raises(v.HacsReleaseError, match="reviewed source inventory"):
        check(target, expected)


def test_archive_pin_detects_modified_archive(tmp_path):
    target, expected = artifact(tmp_path)
    with pytest.raises(v.HacsReleaseError, match="external SHA-256"):
        check(target, expected, pin="0" * 64)


@pytest.mark.parametrize("change", ["missing", "extra", "import", "syntax", "json_duplicate", "json_nonfinite"])
def test_missing_content_or_invalid_source_is_rejected(tmp_path, change):
    files = fixture_files()
    if change == "missing": del files["config_flow.py"]
    if change == "extra": files["secrets.env"] = b"do-not-ship"
    if change == "import": files["__init__.py"] = b"from .absent import ready\n"
    if change == "syntax": files["__init__.py"] = b"def broken(\n"
    if change == "json_duplicate": files["strings.json"] = b'{"a":1,"a":2}'
    if change == "json_nonfinite": files["strings.json"] = b'{"a":NaN}'
    target, expected = artifact(tmp_path, files)
    with pytest.raises(v.HacsReleaseError): check(target, expected)


@pytest.mark.parametrize("limit", ["MAX_ARCHIVE_BYTES", "MAX_MEMBER_BYTES", "MAX_TOTAL_BYTES", "MAX_ENTRIES"])
def test_bounded_artifact_limits(tmp_path, monkeypatch, limit):
    target, expected = artifact(tmp_path)
    monkeypatch.setattr(v, limit, 1)
    with pytest.raises(v.HacsReleaseError): check(target, expected)


@pytest.mark.parametrize("hacs", [{}, {"zip_release": 1, "filename": "ultimate-studio.zip"}, {"zip_release": True, "filename": "../ultimate-studio.zip"}, {"zip_release": True, "filename": "other.zip"}])
def test_release_selection_is_explicit(tmp_path, hacs):
    target, expected = artifact(tmp_path)
    with pytest.raises(v.HacsReleaseError): check(target, expected, hacs=hacs)
