from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"
FRONTEND = ROOT / "frontend"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def load_audit_safety():
    path = BACKEND / "audit_safety.py"
    spec = importlib.util.spec_from_file_location("studio_audit_safety_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_audit_backend_collects_all_studio_sources() -> None:
    audit_log = source(BACKEND / "audit_log.py")
    audit_views = source(BACKEND / "audit_views.py")
    audit_runtime = source(BACKEND / "audit_runtime.py")
    init = source(BACKEND / "__init__.py")

    assert "MAX_EVENTS = 10_000" in audit_log
    assert '"category": str(category or "System")' in audit_log
    assert "async_delay_save" in audit_log
    assert "async def post" in audit_views
    assert "async_summary" in audit_views
    assert "EVENT_STATE_CHANGED" in audit_runtime
    assert "EVENT_CALL_SERVICE" in audit_runtime
    assert "custom_components.printer_slicing_server" in audit_runtime
    assert "StudioAuditLoggingHandler" in audit_runtime
    assert "async_start_audit_runtime" in init


def test_audit_frontend_has_category_chips_search_and_sort() -> None:
    panel = source(FRONTEND / "audit-log-panel-v3.ts")
    transport = source(FRONTEND / "ha-api-transport.ts")
    entry = source(FRONTEND / "studio-entry.ts")
    studio = source(FRONTEND / "studio-mega-workspace-v2.ts")
    jobs = source(FRONTEND / "job-activity-store.ts")
    slicing_server = source(FRONTEND / "slicing-server-workspace.ts")

    assert "data-remove-category" in panel
    assert "data-remove-term" in panel
    assert "Neueste zuerst ↓" in panel
    assert "Älteste zuerst ↑" in panel
    assert "#availableCategories" in panel
    assert "MakerWorld" in panel and "Slicing-Server" in panel and "Studio" in panel
    assert "writeFrontendAudit" in transport
    assert "GET_AUDIT_INTERVAL_MS" in transport
    assert "window_error" in entry
    assert "model_import_completed" in studio
    assert "slice_completed" in studio
    assert "runtime_state_changed" in jobs
    assert "overview_changed" in slicing_server

def test_audit_redacts_nested_keys_bearer_values_and_secret_urls() -> None:
    safety = load_audit_safety()
    payload = {
        "access_token": "camera-secret",
        "nested": {
            "Authorization": "Bearer abc.def.ghi",
            "message": "request Authorization=top-secret failed",
            "url": "https://ha.local/api/camera?token=visible-secret&width=640",
            "safe": "kept",
        },
        "items": [{"api-key": "nested-key"}, "Bearer second.secret"],
    }
    sanitized = safety.sanitize_audit_value(payload)
    assert sanitized["access_token"] == "***"
    assert sanitized["nested"]["Authorization"] == "***"
    assert "top-secret" not in sanitized["nested"]["message"]
    assert "visible-secret" not in sanitized["nested"]["url"]
    assert sanitized["nested"]["url"].endswith("token=***&width=640")
    assert sanitized["nested"]["safe"] == "kept"
    assert sanitized["items"][0]["api-key"] == "***"
    assert sanitized["items"][1] == "Bearer ***"


def test_audit_attribute_allowlist_drops_camera_secrets_and_frame_noise() -> None:
    safety = load_audit_safety()
    filtered = safety.safe_audit_attributes({
        "printer_id": "printer-1",
        "printer_state": "idle",
        "issues": [{"code": "ok", "access_token": "nested-secret"}],
        "access_token": "camera-secret",
        "entity_picture": "/api/camera_proxy/camera.studio?token=secret",
        "frames_received": 12345,
        "sequence": 999,
        "last_frame_at": "2026-09-09T00:00:00Z",
    })
    assert filtered["printer_id"] == "printer-1"
    assert filtered["printer_state"] == "idle"
    assert filtered["issues"][0]["access_token"] == "***"
    assert "access_token" not in filtered
    assert "entity_picture" not in filtered
    assert "frames_received" not in filtered
    assert "sequence" not in filtered
    assert "last_frame_at" not in filtered


def test_audit_runtime_uses_exact_platform_and_service_whitelists() -> None:
    runtime = source(BACKEND / "audit_runtime.py")
    audit_log = source(BACKEND / "audit_log.py")
    audit_views = source(BACKEND / "audit_views.py")
    assert 'entry.platform in ENTITY_PLATFORMS' in runtime
    assert 'if domain not in SERVICE_DOMAINS' in runtime
    assert 'any(marker in entity_id.casefold()' not in runtime
    assert 'safe_audit_attributes' in runtime
    assert 're.findall(r"[a-z0-9]+"' in runtime
    assert 'sanitize_audit_value(deepcopy(details or {}))' in audit_log
    assert 'async_sanitize_existing' in audit_log
    assert 'confirmation_text != "AUDIT BEREINIGEN"' in audit_views
    assert '"events_deleted": 0' in audit_log

