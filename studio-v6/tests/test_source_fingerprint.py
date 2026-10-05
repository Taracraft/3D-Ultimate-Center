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
             "gcode_toolpath.py", "toolpath-material-colors.ts", "makerworld-detail-dialog-v6.ts",
             "test_makerworld_transfer_contract.py", "studio_source_fingerprint.py", "test_source_fingerprint.py"}
    subset = {"scope": "selected_publication_files_only", "published": False,
              "stable_source_count": before["file_count"],
              "files": [row for row in before["files"] if Path(row["path"]).name in names]}
    (target / "public-transfer-fingerprints.json").write_text(json.dumps(subset, ensure_ascii=True, indent=2), encoding="utf-8")
