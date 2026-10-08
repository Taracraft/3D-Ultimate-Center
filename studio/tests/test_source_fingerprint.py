"""Publication evidence without network, account access or live-system writes."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("source_fingerprint_under_test", ROOT / "tools/studio_source_fingerprint.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize("payload", [b"", b"hello\n", b"line\r\n", b"\xef\xbb\xbfhello\n", b"\x00\xff\x01"])
def test_git_blob_identity_includes_exact_bytes_and_header(tmp_path, payload):
    path = tmp_path / "source"
    path.write_bytes(payload)
    value = MODULE.fingerprint(path)
    expected = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload, usedforsecurity=False).hexdigest()
    assert value == {"size_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "git_blob_sha": expected}
    assert path.read_bytes() == payload


def test_inventory_retains_sql_and_never_includes_runtime_or_recovery(tmp_path):
    for name in ["core/schema.sql", "frontend/card.ts", "core/secrets.yaml", "core/config.json",
                 "core/module.py.bak.20261005", "core/.env", "core/data/jobs.json",
                 "frontend/node_modules/pkg/index.js", "frontend/backups/old.ts"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic", encoding="utf-8")
    result = MODULE.source_inventory(tmp_path)
    assert [r["path"] for r in result["files"]] == ["core/schema.sql", "frontend/card.ts"]
    assert result["published"] is False
    assert result["file_count"] == 2
    assert all(str(tmp_path) not in str(record) for record in result["files"])


def test_p1_retired_namespace_stubs_are_excluded_from_public_scope(tmp_path):
    tests = tmp_path / "tests"
    frontend = tmp_path / "frontend"
    tests.mkdir()
    frontend.mkdir()
    (tests / "test_studio_example.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tests / "test_v6_example.py").write_text(
        "from __future__ import annotations\n\n"
        "# Retired by the P1 namespace migration on 2026-10-07.\n"
        "# Active contract moved to test_studio_example.py.\n"
        "__test__ = False\n",
        encoding="utf-8",
    )
    (frontend / "studio-api.ts").write_text("export const current = true;\n", encoding="utf-8")
    (frontend / "v6-api.ts").write_text(
        "// Retired by the P1 namespace migration on 2026-10-07.\n"
        "// Active module: studio-api.ts\n",
        encoding="utf-8",
    )
    result = MODULE.source_inventory(tmp_path)
    assert [row["path"] for row in result["files"]] == [
        "frontend/studio-api.ts",
        "tests/test_studio_example.py",
    ]


def test_active_v6_test_or_frontend_file_fails_publication_closed(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_v6_active.py").write_text("def test_old():\n    assert True\n", encoding="utf-8")
    with pytest.raises(MODULE.SourceInventoryError, match="active_v6_test_in_publish_scope"):
        MODULE.source_inventory(tmp_path)

    (tests / "test_v6_active.py").unlink()
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "v6-api.ts").write_text("export const legacy = true;\n", encoding="utf-8")
    with pytest.raises(MODULE.SourceInventoryError, match="active_v6_frontend_in_publish_scope"):
        MODULE.source_inventory(tmp_path)


def test_publication_root_files_use_neutral_p1_tool_names():
    assert "build_studio_core.mjs" in MODULE.ROOT_FILES
    assert "connector_studio_gate.py" in MODULE.ROOT_FILES
    assert "build_v6_core.mjs" not in MODULE.ROOT_FILES
    assert "connector_v6_gate.py" not in MODULE.ROOT_FILES


def test_p1_retired_deploy_trees_are_excluded_from_public_scope(tmp_path):
    active_component = tmp_path / "deploy/homeassistant/custom_components/ultimate_3d_studio"
    retired_component = tmp_path / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6"
    active_web = tmp_path / "deploy/homeassistant/www/3d-studio"
    retired_web = tmp_path / "deploy/homeassistant/www/3d-studio-v6"
    for directory in (active_component, retired_component, active_web, retired_web):
        directory.mkdir(parents=True, exist_ok=True)
    (active_component / "runtime.py").write_text("# active\n", encoding="utf-8")
    (retired_component / "runtime.py").write_text("# legacy\n", encoding="utf-8")
    (active_web / "bundle.js").write_text("// active\n", encoding="utf-8")
    (retired_web / "bundle.js").write_text("// legacy\n", encoding="utf-8")
    (retired_component / MODULE.P1_RETIRED_TREE_MARKER).write_text(
        MODULE.P1_RETIRED_MARKER
        + "\nActive tree: deploy/homeassistant/custom_components/ultimate_3d_studio\n",
        encoding="utf-8",
    )
    (retired_web / MODULE.P1_RETIRED_TREE_MARKER).write_text(
        MODULE.P1_RETIRED_MARKER
        + "\nActive tree: deploy/homeassistant/www/3d-studio\n",
        encoding="utf-8",
    )
    result = MODULE.source_inventory(tmp_path)
    paths = [row["path"] for row in result["files"]]
    assert "deploy/homeassistant/custom_components/ultimate_3d_studio/runtime.py" in paths
    assert "deploy/homeassistant/www/3d-studio/bundle.js" in paths
    assert not any("ultimate_3d_studio_v6" in path or "3d-studio-v6" in path for path in paths)


def test_active_v6_deploy_tree_fails_publication_closed(tmp_path):
    active = tmp_path / "deploy/homeassistant/custom_components/ultimate_3d_studio"
    legacy = tmp_path / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6"
    active.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (active / "runtime.py").write_text("# active\n", encoding="utf-8")
    (legacy / "runtime.py").write_text("# legacy\n", encoding="utf-8")
    with pytest.raises(MODULE.SourceInventoryError, match="active_v6_deploy_tree_in_publish_scope"):
        MODULE.source_inventory(tmp_path)


def test_retired_v6_tree_requires_neutral_replacement(tmp_path):
    legacy = tmp_path / "deploy/homeassistant/www/3d-studio-v6"
    legacy.mkdir(parents=True)
    (legacy / MODULE.P1_RETIRED_TREE_MARKER).write_text(
        MODULE.P1_RETIRED_MARKER + "\nActive tree: deploy/homeassistant/www/3d-studio\n",
        encoding="utf-8",
    )
    with pytest.raises(MODULE.SourceInventoryError, match="retired_v6_tree_missing_active_replacement"):
        MODULE.source_inventory(tmp_path)


def test_retired_v6_puppet_stubs_are_excluded_and_active_files_fail_closed(tmp_path):
    puppet = tmp_path / "deploy/homeassistant/host/puppet"
    puppet.mkdir(parents=True)
    for legacy_name, active_name in MODULE.RETIRED_V6_PUPPET.items():
        (puppet / active_name).write_text("# active\n", encoding="utf-8")
        (puppet / legacy_name).write_text(
            MODULE.P1_RETIRED_MARKER + f"\nActive file: {active_name}\n",
            encoding="utf-8",
        )
    result = MODULE.source_inventory(tmp_path)
    paths = [row["path"] for row in result["files"]]
    assert all(f"deploy/homeassistant/host/puppet/{name}" not in paths for name in MODULE.RETIRED_V6_PUPPET)
    assert all(f"deploy/homeassistant/host/puppet/{name}" in paths for name in MODULE.RETIRED_V6_PUPPET.values())

    first = next(iter(MODULE.RETIRED_V6_PUPPET))
    (puppet / first).write_text("# active legacy helper\n", encoding="utf-8")
    with pytest.raises(MODULE.SourceInventoryError, match="active_v6_puppet_in_publish_scope"):
        MODULE.source_inventory(tmp_path)


def test_active_v6_product_token_fails_publication_closed(tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "active.ts").write_text('export const label = "Studio V6";\n', encoding="utf-8")
    with pytest.raises(MODULE.SourceInventoryError, match="active_namespace_content:v6_product_token"):
        MODULE.source_inventory(tmp_path)


def test_active_legacy_api_namespace_fails_publication_closed(tmp_path):
    api = tmp_path / "api"
    api.mkdir()
    (api / "routes.py").write_text('API_BASE = "/api/printer_control_center/v1"\n', encoding="utf-8")
    with pytest.raises(MODULE.SourceInventoryError, match="active_namespace_content:legacy_api_namespace"):
        MODULE.source_inventory(tmp_path)


def test_double_studio_mechanical_name_fails_publication_closed(tmp_path):
    deploy = tmp_path / "deploy"
    deploy.mkdir()
    (deploy / "camera.py").write_text("class Ultimate3DStudioStudioCamera: pass\n", encoding="utf-8")
    with pytest.raises(MODULE.SourceInventoryError, match="active_namespace_content:double_studio_token"):
        MODULE.source_inventory(tmp_path)


def test_frontend_dist_is_not_canonical_public_source(tmp_path):
    frontend = tmp_path / "frontend"
    dist = frontend / "dist"
    dist.mkdir(parents=True)
    (frontend / "studio-entry.ts").write_text("export {};\n", encoding="utf-8")
    (dist / "v6-entry.js").write_text('window.name = "Studio V6";\n', encoding="utf-8")
    result = MODULE.source_inventory(tmp_path)
    paths = [row["path"] for row in result["files"]]
    assert "frontend/studio-entry.ts" in paths
    assert not any(path.startswith("frontend/dist/") for path in paths)


def test_storage_upgrade_legacy_fixture_remains_allowed(tmp_path):
    tests_dir = tmp_path / "frontend-tests"
    tests_dir.mkdir()
    fixture = tests_dir / "storage-upgrade.test.ts"
    fixture.write_text(
        'const legacy = ["ultimate-3d-studio-v6-backup", "other-v6"];\n',
        encoding="utf-8",
    )
    result = MODULE.source_inventory(tmp_path)
    assert any(row["path"] == "frontend-tests/storage-upgrade.test.ts" for row in result["files"])


def test_link_in_source_fails_closed(tmp_path, monkeypatch):
    source = tmp_path / "core"
    source.mkdir()
    (source / "module.py").write_text("# source")
    monkeypatch.setattr(MODULE, "_link", lambda path: path.name == "module.py")
    with pytest.raises(MODULE.SourceInventoryError, match="linked_source"):
        MODULE.source_inventory(tmp_path)


def test_oversized_file_is_not_silently_skipped(tmp_path, monkeypatch):
    path = tmp_path / "source.py"
    path.write_bytes(b"large")
    monkeypatch.setattr(MODULE, "MAX_FILE_BYTES", 4)
    with pytest.raises(MODULE.SourceInventoryError, match="source_size_limit"):
        MODULE.fingerprint(path)


def test_empty_source_is_not_a_complete_release(tmp_path):
    with pytest.raises(MODULE.SourceInventoryError, match="empty_source_inventory"):
        MODULE.source_inventory(tmp_path)


def test_current_project_source_inventory_is_reproducible():
    """Retain a source-bound gate artifact, not an upload or deployment claim."""
    before = MODULE.source_inventory(ROOT)
    after = MODULE.source_inventory(ROOT)
    assert before == after, "Source changed during fingerprint capture; rerun on a stable tree."
    assert before["complete_for_declared_scope"] and before["published"] is False
    assert any(row["path"] == "core/schema.sql" for row in before["files"])
    target = ROOT / ".test-results"
    target.mkdir(exist_ok=True)
    (target / "public-source-fingerprints.json").write_text(json.dumps(before, ensure_ascii=True, indent=2), encoding="utf-8")
    names = {"makerworld_transfer.py", "makerworld_runtime.py", "makerworld_download.py",
             "gcode_toolpath.py", "toolpath-material-colors.ts", "makerworld-detail-dialog-studio.ts",
             "test_makerworld_transfer_contract.py", "studio_source_fingerprint.py", "test_source_fingerprint.py"}
    subset = {"scope": "selected_publication_files_only", "published": False,
              "stable_source_count": before["file_count"],
              "files": [row for row in before["files"] if Path(row["path"]).name in names]}
    (target / "public-transfer-fingerprints.json").write_text(json.dumps(subset, ensure_ascii=True, indent=2), encoding="utf-8")
