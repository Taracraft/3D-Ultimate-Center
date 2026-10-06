"""Behavioral coverage for historical and newly ingested audit secrets."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import types
from unittest.mock import patch

COMPONENT = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6"


class MemoryStore:
    def __init__(self, _hass, _version, _key):
        self.data = {"events": []}
        self.saved = None
        self.pending = None

    async def async_load(self):
        return deepcopy(self.data)

    async def async_save(self, value):
        self.saved = deepcopy(value)

    def async_delay_save(self, callback, _delay):
        self.pending = callback


def modules():
    package = types.ModuleType("_studio_audit_regression")
    package.__path__ = [str(COMPONENT)]
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    storage = types.ModuleType("homeassistant.helpers.storage")
    storage.Store = MemoryStore
    const = types.ModuleType(package.__name__ + ".const")
    const.DOMAIN = "studio_audit_regression"
    overrides = {
        package.__name__: package,
        const.__name__: const,
        "homeassistant.core": core,
        "homeassistant.helpers.storage": storage,
    }
    loaded = []
    with patch.dict(sys.modules, overrides):
        for filename in ("audit_safety", "audit_log"):
            name = package.__name__ + "." + filename
            spec = importlib.util.spec_from_file_location(name, COMPONENT / (filename + ".py"))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            loaded.append(module)
    return loaded


def test_quoted_json_and_python_log_values_hide_complete_secrets():
    safety, _ = modules()
    for value in (
        '{"access_token": "canary-quoted"}',
        "{'password': 'canary with spaces'}",
        'password="canary with spaces"',
        '{"cookie": "session=canary; csrf=another-canary"}',
        '{"private_key": "canary\\nsecond-canary"}',
    ):
        assert "canary" not in safety.redact_audit_text(value)


def test_authorization_schemes_and_url_userinfo_are_redacted():
    safety, _ = modules()
    for value in (
        "Authorization: Basic Y2FuYXJ5OnNlY3JldA==",
        "Bearer canary.secret",
        "https://user:canary-secret@example.test/camera?width=640",
        "rtsp://user:canary-secret@example.test/live",
    ):
        output = safety.redact_audit_text(value)
        assert "canary" not in output and "Y2FuYXJ5" not in output
    assert safety.redact_audit_text("https://example.test/image?width=640") == "https://example.test/image?width=640"
    assert safety.redact_audit_text("Bearer canary.secret") == "Bearer ***"


def test_redaction_is_idempotent_and_preserves_ordinary_diagnostics():
    safety, _ = modules()
    original = {"printer_id": "printer-1", "issues": [{"code": "HMS_0300", "message": "motor unavailable"}], "url": "https://ha.test/camera?token=canary&width=640"}
    sanitized = safety.sanitize_audit_value(original)
    assert sanitized["issues"] == original["issues"]
    assert sanitized["printer_id"] == "printer-1"
    assert sanitized["url"].endswith("token=***&width=640")
    assert safety.sanitize_audit_value(sanitized) == sanitized
    assert "canary" in original["url"]


def test_append_masks_metadata_and_returns_a_detached_record():
    _, log = modules()
    audit = log.V6AuditLog(types.SimpleNamespace(data={}))
    payload = {"safe": [1, 2], "access_token": "canary-details"}
    event = asyncio.run(audit.async_append(category="System", component="camera", event="password=canary-event", status="info", actor="Bearer canary.actor", details=payload))
    assert "canary" not in json.dumps(event)
    assert "canary" not in json.dumps(audit._store.pending())
    assert payload["access_token"] == "canary-details"
    event["details"]["safe"].append(3)
    assert audit._events[0]["details"]["safe"] == [1, 2]


def test_historical_read_preserves_all_records_order_and_stored_history():
    _, log = modules()
    audit = log.V6AuditLog(types.SimpleNamespace(data={}))
    original = [{"id": str(i), "category": "System", "details": {"access_token": "canary-old"}} for i in range(300)]
    audit._store.data = {"events": deepcopy(original)}
    result = asyncio.run(audit.async_list(limit=500))
    assert len(result) == 300
    assert [item["id"] for item in result] == [str(i) for i in reversed(range(300))]
    assert "canary" not in json.dumps(result)
    assert audit._events == original and audit._store.saved is None


def test_historical_summary_never_exposes_secret_metadata():
    _, log = modules()
    audit = log.V6AuditLog(types.SimpleNamespace(data={}))
    audit._store.data = {"events": [{"category": "token=canary-category", "status": "password=canary-status"}]}
    result = asyncio.run(audit.async_summary())
    assert result["total"] == 1
    assert "canary" not in json.dumps(result)


def test_historical_read_keeps_explicit_cleanup_preview_and_apply_working():
    _, log = modules()
    audit = log.V6AuditLog(types.SimpleNamespace(data={}))
    audit._store.data = {"events": [{"id": "kept", "details": {"access_token": "canary-history"}}]}
    asyncio.run(audit.async_list())
    preview = asyncio.run(audit.async_sanitize_existing())
    assert preview == {"scanned": 1, "changed": 1, "applied": False, "events_deleted": 0}
    assert audit._store.saved is None
    result = asyncio.run(audit.async_sanitize_existing(apply=True))
    assert result["events_deleted"] == 0 and result["changed"] == 1
    assert audit._store.saved["events"][0]["id"] == "kept"
    assert "canary" not in json.dumps(audit._store.saved)
