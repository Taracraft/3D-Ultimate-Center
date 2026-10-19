"""Offline native-slicer bundle closure tests; never touches Home Assistant or systemd."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "packages" / "ultimate-slicer-server" / "build_native_package.py"
spec = importlib.util.spec_from_file_location("private_native_bundle_builder", BUILDER)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_reproducible_complete_hash_verified_payload(tmp_path):
    first = tmp_path / "bundle-first.tar.gz"
    second = tmp_path / "bundle-second.tar.gz"
    a = module.build(ROOT, first)
    b = module.build(ROOT, second)
    assert a["archive_sha256"] == b["archive_sha256"]
    assert a["payload_file_count"] == b["payload_file_count"] == 29
    assert not a["native_deploy_ready"]
    with tarfile.open(first, "r:gz") as tar:
        names = tar.getnames()
        assert len(names) == len(set(names)) == 30
        assert all(path.startswith("ultimate-slicer-server/") for path in names)
        assert all(x.uid == 0 and x.gid == 0 and x.mtime == 0 for x in tar)
        assert not any(path.endswith(("config.json", "secrets.yaml")) for path in names)
        assert not any("/engines/" in path for path in names)
        assert sum(name.endswith((".service", ".timer")) for name in names) == 5
        assert tar.getmember("ultimate-slicer-server/payload/progress-pipe-reader.py").mode & 0o111
        assert tar.getmember("ultimate-slicer-server/payload/dispatch-job.sh").mode & 0o111
        metadata = json.load(tar.extractfile("ultimate-slicer-server/source-manifest.json"))
        assert metadata["complete_source_file_count"] == 29
        identity = json.load(tar.extractfile("ultimate-slicer-server/payload/release.json"))
        assert metadata["native_version"] == identity["version"]
        assert metadata["api_protocol"] == identity["api_protocol"]
        assert "ultimate-slicer-server/payload/release.json" in names
        assert metadata["first_install_tool_included"] is True
        assert "ultimate-slicer-server/installer/install_native.py" in names
        assert metadata["native_systemd_units_ready"] is True
        assert metadata["native_deploy_ready"] is False
        for item in metadata["files"]:
            entry = tar.extractfile("ultimate-slicer-server/" + item["path"])
            assert entry is not None
            payload = entry.read()
            assert module._digest(payload) == item["sha256"]
            assert len(payload) == item["size_bytes"]


def test_existing_bundle_is_never_overwritten(tmp_path):
    destination = tmp_path / "native.tar.gz"
    destination.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        module.build(ROOT, destination)
    assert destination.read_bytes() == b"existing"


@pytest.mark.parametrize("line", [
    "../outside",
    "/absolute",
    "./hidden",
    "sub/../escape",
    "bad file name",
])
def test_unsafe_manifest_paths_are_denied(tmp_path, line):
    manifest = tmp_path / "SHA256SUMS"
    manifest.write_text("a" * 64 + "  " + line + "\n")
    with pytest.raises(ValueError):
        module._manifest(manifest, {line})


def test_hash_changed_file_does_not_enter_bundle(tmp_path):
    payload = tmp_path / "file.py"
    payload.write_text("safe content")
    with pytest.raises(ValueError, match="SHA-256"):
        module._read_pinned(tmp_path, "file.py", "0" * 64)

