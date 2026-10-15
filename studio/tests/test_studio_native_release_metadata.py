"""Source and runtime contract for metadata-derived native Slicer version.

This file never starts a network listener, job supervisor or printer command.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "deploy/homeassistant/host/3d-printer-slicing-server/server.py"
REFRESH = ROOT / "deploy/homeassistant/host/3d-printer-slicing-server/refresh-state.sh"
RELEASE = ROOT / "packages/ultimate-slicer-server/release.json"


def _identity(source_root: Path, config: dict | None = None):
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_native_release_identity"
    )
    namespace = {
        "SOURCE_ROOT": source_root,
        "CONFIG": config or {},
        "json": json,
        "re": re,
        "Path": Path,
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SERVER), "exec"), namespace)
    return namespace["_native_release_identity"]()


def test_native_release_version_comes_from_single_package_metadata():
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    assert isinstance(release["version"], str)
    assert re.fullmatch(r"[0-9]+[.][0-9]+[.][0-9]+(?:[-+][A-Za-z0-9.-]+)?", release["version"])
    assert type(release["api_protocol"]) is int and release["api_protocol"] >= 2
    assert _identity(RELEASE.parent) == (
        release["version"], release["api_protocol"]
    )
    server = SERVER.read_text(encoding="utf-8")
    status = REFRESH.read_text(encoding="utf-8")
    assert 'VERSION = "' not in server
    assert 'VERSION=0.' not in status
    assert '_native_release_identity()' in server
    assert 'RELEASE_FILE="$SOURCE_ROOT/release.json"' in status
    assert '"$RELEASE_FILE"' in status


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"garbage",
        b"[]",
        b'{"version":"","api_protocol":2}',
        b'{"version":"not-a-semver","api_protocol":2}',
        b'{"version":"1.2.3","api_protocol":true}',
        b'{"version":"1.2.3","api_protocol":1}',
    ],
)
def test_invalid_metadata_fails_closed(tmp_path, body: bytes):
    (tmp_path / "release.json").write_bytes(body)
    with pytest.raises(SystemExit, match="Native release metadata invalid"):
        _identity(tmp_path)


def test_legacy_source_without_metadata_does_not_invent_a_version(tmp_path):
    assert _identity(tmp_path) == ("unknown", 2)
    assert _identity(tmp_path, {"version": "1.2.3+synthetic", "api_protocol": 2}) == (
        "1.2.3+synthetic", 2
    )


def test_legacy_source_rejects_invalid_external_metadata(tmp_path):
    with pytest.raises(SystemExit, match="Native legacy release metadata invalid"):
        _identity(tmp_path, {"version": "bad\nsecret", "api_protocol": 2})
    with pytest.raises(SystemExit, match="Native legacy release metadata invalid"):
        _identity(tmp_path, {"version": "1.2.3", "api_protocol": True})
