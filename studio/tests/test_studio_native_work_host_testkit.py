"""Portable work-server testkit is reproducible, inspect-only, no MCP required."""
from __future__ import annotations

import importlib.util
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tarfile
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "packages/ultimate-slicer-server/build_target_testkit.py"
SPEC = importlib.util.spec_from_file_location("native_work_host_testkit", TOOL)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def test_private_linux_testkit_is_reproducible_and_contains_only_expected_sources(tmp_path):
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    report_a = BUILDER.build(ROOT, first)
    report_b = BUILDER.build(ROOT, second)
    assert report_a["sha256"] == report_b["sha256"]
    assert report_a["file_count"] == report_b["file_count"] == 12
    assert report_a["native_deploy_ready"] is False
    assert report_a["installation_performed"] is False
    assert report_a["remote_server_accessed"] is False
    assert report_a["private_publication_approved"] is False

    with zipfile.ZipFile(first) as archive:
        names = set(archive.namelist())
        assert len(names) == 12
        assert "native-source.tar.gz" in names
        assert "README.md" in names
        assert "SHA256SUMS" in names
        assert "check_target_host.sh" in names
        assert "run_isolated_test.sh" in names
        assert "packages/ultimate-slicer-server/install_native.py" in names
        assert "tests/native_linux_install_sandbox.py" in names
        assert len([n for n in names if n.startswith("units/")]) == 5
        assert all(not n.startswith("/") and ".." not in Path(n).parts for n in names)
        assert all(not n.endswith((".pem", ".key", ".crt", "secret.json")) for n in names)

        lines = archive.read("SHA256SUMS").decode().splitlines()
        checked = {}
        for line in lines:
            digest, name = line.split("  ", 1)
            checked[name] = digest
            assert sha256(archive.read(name)).hexdigest() == digest
        assert set(checked) == names - {"SHA256SUMS"}

        preflight = archive.read("check_target_host.sh").decode()
        assert 'if [ "$(id -u)" -eq 0 ]' in preflight
        assert "MISSING_NATIVE_RUNTIME_COMMAND=" in preflight
        assert "packages/ultimate-slicer-server/install_native.py --check-host" in preflight
        assert "packages/ultimate-slicer-server/install_native.py \\" in preflight
        assert "BUNDLE_DEPLOY_APPROVED=false" in preflight
        assert "INSTALLATION_PERFORMED=false" in preflight
        executable_lines = [
            line for line in preflight.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        shell_body = "\n".join(executable_lines)
        for forbidden in (" --install", " --upgrade", " --rollback", "apt-get", "systemctl start", "systemctl enable", "curl ", "wget "):
            assert forbidden not in shell_body
        assert not any(line.lstrip().startswith("useradd ") for line in executable_lines)

        root_test = archive.read("run_isolated_test.sh").decode()
        assert "native_linux_install_sandbox.py" in root_test
        assert 'if [ "$(id -u)" -ne 0 ]' in root_test
        assert " --install" not in root_test
        assert "systemctl start" not in root_test

        source = archive.read("native-source.tar.gz")
        assert sha256(source).hexdigest() == report_a["native_source_sha256"]
        with tarfile.open(fileobj=BytesIO(source), mode="r:gz") as inner:
            members = inner.getnames()
            manifest = json.load(inner.extractfile(
                "ultimate-slicer-server/source-manifest.json"
            ))
            assert manifest["native_deploy_ready"] is False
            assert manifest["contains_slicer_engine_binary"] is False
            assert manifest["contains_private_configuration"] is False
            assert len(members) == manifest["complete_source_file_count"] + 1
            assert "ultimate-slicer-server/payload/release.json" in members


def test_existing_private_work_server_testkit_is_never_overwritten(tmp_path):
    occupied = tmp_path / "existing.zip"
    occupied.write_bytes(b"do not overwrite")
    with pytest.raises(FileExistsError):
        BUILDER.build(ROOT, occupied)
    assert occupied.read_bytes() == b"do not overwrite"
