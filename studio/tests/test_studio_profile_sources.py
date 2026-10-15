"""Offline selected-profile source delivery; no engine or worker execution."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
SLICER = ROOT / "Slicer-Server"

def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SLICER / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

@pytest.mark.parametrize("relative", ["PROFILE_SOURCE_BUNDLE.json", "verify_profile_sources.py"])
def test_real_testpackage_contains_profile_sources_and_offline_verifier(relative):
    builder = module("profile_sources_package_builder", "prepare_test_server_package.py")
    payload, manifest = builder.collect(ROOT)
    assert "context/" + relative in payload
    assert payload["context/" + relative] == (SLICER / relative).read_bytes()
    assert manifest["container_deploy_ready"] is False


import copy
import hashlib
import subprocess
import sys

verifier = module("selected_profile_source_verifier", "verify_profile_sources.py")
builder = module("selected_profile_source_builder", "prepare_test_server_package.py")
BUNDLE_BYTES = (SLICER / verifier.BUNDLE_NAME).read_bytes()
COMPONENT = ROOT / verifier.COMPONENT

def defaults():
    return (
        json.loads((COMPONENT / "native_filament_defaults.json").read_text(encoding="utf-8-sig")),
        json.loads((COMPONENT / "h2s_native_defaults.json").read_text(encoding="utf-8-sig")),
    )

def test_real_selected_sources_replay_without_source_writes():
    before = {p: p.read_bytes() for p in [
        SLICER / verifier.BUNDLE_NAME,
        COMPONENT / "native_filament_defaults.json",
        COMPONENT / "h2s_native_defaults.json",
    ]}
    result = verifier.verify(ROOT, source_tree=True)
    assert (result["source_files"], result["verified_profiles"],
            result["process_projections"], result["gcode_sound_roundtrips"]) == (118, 54, 12, 8)
    assert result["engine_executed"] is False
    assert result["worker_started"] is False
    assert result["publication_approved"] is False
    assert {p: p.read_bytes() for p in before} == before

def test_prepared_context_has_independent_offline_cli_and_source_scope(tmp_path):
    context = tmp_path / "context"
    builder.context.prepare(ROOT, context)
    manifest = json.loads((context / "context-manifest.json").read_text())
    row = next(r for r in manifest["files"] if r["path"] == verifier.BUNDLE_NAME)
    assert row["license_scope"] == "third-party-profile-source"
    result = subprocess.run(
        [sys.executable, str(context / "verify_profile_sources.py"),
         "--context-root", str(context)], capture_output=True, text=True, timeout=20
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["verified_profiles"] == 54

@pytest.mark.parametrize("mutation", ["append", "json_change"])
def test_even_self_consistent_bundle_changes_need_reviewed_digest(mutation):
    data = BUNDLE_BYTES + b"\n"
    if mutation == "json_change":
        value = json.loads(BUNDLE_BYTES)
        value["profiles"][0]["resolved_sha256"] = "0" * 64
        data = json.dumps(value).encode()
    with pytest.raises(verifier.ProfileSourceError, match="profile_source_bundle_digest_mismatch"):
        verifier.load_bundle(data)

@pytest.mark.parametrize("mutation,error", [
    ("wrong_commit", "invalid_source_revision"),
    ("wrong_license", "source_license_mismatch"),
    ("release_flag", "source_release_flag_rejected"),
    ("engine_flag", "source_release_flag_rejected"),
    ("missing_file", "source_file_set_mismatch"),
    ("duplicate_file", "duplicate_source_path"),
    ("unsafe_path", "unsafe_source_path"),
    ("changed_bytes", "upstream_source_digest_mismatch"),
    ("wrong_git_blob", "upstream_git_blob_mismatch"),
])
def test_source_inventory_checks_original_bytes_identity_and_flags(mutation, error):
    value = json.loads(BUNDLE_BYTES)
    if mutation == "wrong_commit":
        value["commit"] = "0" * 40
    elif mutation == "wrong_license":
        value["license_sha256"] = "0" * 64
    elif mutation == "release_flag":
        value["publication_approved"] = True
    elif mutation == "engine_flag":
        value["engine_included"] = True
    elif mutation == "missing_file":
        value["files"].pop()
    elif mutation == "duplicate_file":
        value["files"][-1] = copy.deepcopy(value["files"][0])
    elif mutation == "unsafe_path":
        value["files"][0]["path"] = "resources/profiles/BBL/../../outside.json"
    elif mutation == "changed_bytes":
        value["files"][0]["content"] += "\n"
    else:
        value["files"][0]["git_blob"] = "0" * 40
    with pytest.raises(verifier.ProfileSourceError, match=error):
        verifier._objects(value)

@pytest.mark.parametrize("mutation,error", [
    ("filament", "selected_value_mismatch"),
    ("process", "selected_value_mismatch"),
    ("sound", "sound_roundtrip_mismatch"),
    ("marker", "sound_marker_mismatch"),
])
def test_replay_rejects_changed_local_selections_or_sound_transforms(mutation, error):
    a1, h2s = defaults()
    if mutation == "filament":
        profile = next(iter(a1["profiles"].values()))
        field = next(iter(profile["settings"]))
        profile["settings"][field] = "synthetic-mismatch"
    elif mutation == "process":
        next(iter(h2s["processes"].values()))["outer_wall_speed"] += 1
    elif mutation == "sound":
        h2s["parts"]["start_sound"] += "\n"
    else:
        h2s["parts"]["gcode_1"] = h2s["parts"]["gcode_1"].replace(";@U3D_START_SOUND@", ";synthetic-marker")
    with pytest.raises(verifier.ProfileSourceError, match=error):
        verifier.verify_bundle(BUNDLE_BYTES, a1, h2s)

@pytest.mark.parametrize("after,expected", [(False, "own"), (True, "included")])
def test_profile_include_order_and_metadata_exclusion(after, expected):
    directory = "resources/profiles/BBL/machine"
    objects = {
        directory + "/base.json": {"setting": "parent"},
        directory + "/included.json": {"setting": "included", "name": "not-inherited"},
        directory + "/child.json": {"inherits": "base", "include": ["included"], "setting": "own", "name": "child"},
    }
    result = verifier.resolve(objects, directory + "/child.json", {"name"}, after)
    assert result["setting"] == expected
    assert result["name"] == "child"

@pytest.mark.parametrize("mutation,error", [
    ("cycle", "cyclic_or_deep_profile_inheritance"),
    ("missing", "inherited_source_missing_or_ambiguous"),
    ("ambiguous", "inherited_source_missing_or_ambiguous"),
    ("traversal", "invalid_inherited_profile_name"),
])
def test_inheritance_fails_closed(mutation, error):
    directory = "resources/profiles/BBL/filament"
    path = directory + "/child.json"
    objects = {path: {"inherits": "base"}}
    if mutation == "cycle":
        objects[path]["inherits"] = "child"
    elif mutation == "ambiguous":
        objects[directory + "/one/base.json"] = {}
        objects[directory + "/two/base.json"] = {}
    elif mutation == "traversal":
        objects[path]["inherits"] = "../base"
    with pytest.raises(verifier.ProfileSourceError, match=error):
        verifier.resolve(objects, path, set())

@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_package_rejects_unavailable_or_changed_upstream_source_before_output(tmp_path, monkeypatch, mutation):
    real_read = builder.context.read_regular
    def read(root, relative):
        if relative == "Slicer-Server/" + verifier.BUNDLE_NAME:
            if mutation == "missing":
                raise FileNotFoundError("synthetic missing source bundle")
            return real_read(root, relative) + b"\n"
        return real_read(root, relative)
    monkeypatch.setattr(builder.context, "read_regular", read)
    error = FileNotFoundError if mutation == "missing" else builder.context.ContextError
    with pytest.raises(error):
        builder.build(ROOT, tmp_path / "package")
    assert not (tmp_path / "package").exists()

def test_size_limit_rejects_oversized_source_without_reading_it(tmp_path):
    path = tmp_path / "oversized.json"
    path.write_bytes(b"x" * (verifier.MAX_BYTES + 1))
    with pytest.raises(verifier.ProfileSourceError, match="invalid_profile_source_file"):
        verifier.read_regular(tmp_path, path.name)


@pytest.mark.parametrize("change_bundle", [False, True])
def test_verified_archive_offline_cli_checks_sources_beyond_transport_hashes(tmp_path, change_bundle):
    package = tmp_path / "package"
    builder.build(ROOT, package)
    extracted = tmp_path / "extracted"
    builder.verifier.extract_verified(package / builder.ARCHIVE_NAME, extracted)
    context = extracted / "context"
    if change_bundle:
        path = context / verifier.BUNDLE_NAME
        path.chmod(0o644)
        value = json.loads(path.read_text())
        value["profiles"][0]["resolved_sha256"] = "0" * 64
        path.write_text(json.dumps(value))
        # Transport hashes alone cannot turn changed sources into reviewed sources.
        manifest_path = context / "context-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        row = next(r for r in manifest["files"] if r["path"] == verifier.BUNDLE_NAME)
        row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        row["size_bytes"] = path.stat().st_size
        manifest_path.chmod(0o644)
        manifest_path.write_text(json.dumps(manifest))
    result = subprocess.run(
        [sys.executable, str(context / "verify_profile_sources.py"),
         "--context-root", str(context)], capture_output=True, text=True, timeout=20
    )
    if change_bundle:
        assert result.returncode == 1
        assert "profile_source_bundle_digest_mismatch" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["verified_profiles"] == 54
