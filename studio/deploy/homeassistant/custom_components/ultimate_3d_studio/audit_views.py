"""HTTP views for the persistent Studio system audit log."""
from __future__ import annotations

from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .audit_log import get_audit_log

API_PREFIX = "/api/ultimate_3d_studio/v1/system/audit"
_ALLOWED_STATUSES = {"info", "success", "warning", "error", "failed", "cancelled"}


def _text(value: Any, fallback: str = "") -> str:
    text = str(value if value is not None else fallback).strip()
    return text[:500]


class AuditLogView(HomeAssistantView):
    url = API_PREFIX
    name = "api:ultimate_3d_studio:audit_log"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            limit = int(request.query.get("limit", "1000"))
        except ValueError:
            limit = 1000
        category_query = request.query.get("category", "")
        categories = [item.strip() for item in category_query.split(",") if item.strip()]
        audit = get_audit_log(hass)
        items = await audit.async_list(
            limit=limit,
            component=request.query.get("component") or None,
            categories=categories,
            job_id=request.query.get("job_id") or None,
            printer_id=request.query.get("printer_id") or None,
            status=request.query.get("status") or None,
        )
        summary = await audit.async_summary()
        return web.json_response({
            "data": {
                "items": items,
                "count": len(items),
                "persistent": True,
                **summary,
            }
        })

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            payload = await request.json()
        except Exception:
            return web.json_response(
                {"data": None, "error": {"code": "invalid_json", "message": "Valid JSON is required"}},
                status=400,
            )
        if not isinstance(payload, dict):
            return web.json_response(
                {"data": None, "error": {"code": "invalid_payload", "message": "A JSON object is required"}},
                status=400,
            )
        status = _text(payload.get("status"), "info").casefold()
        if status not in _ALLOWED_STATUSES:
            status = "info"
        user = request.get("hass_user")
        actor = None
        if user is not None:
            actor = getattr(user, "name", None) or getattr(user, "id", None)
        details = payload.get("details")
        if not isinstance(details, dict):
            details = {"value": details} if details is not None else {}
        event = await get_audit_log(hass).async_append(
            category=_text(payload.get("category"), "System"),
            component=_text(payload.get("component"), "frontend"),
            event=_text(payload.get("event"), "frontend_event"),
            status=status,
            source=_text(payload.get("source"), "frontend"),
            actor=actor,
            correlation_id=_text(payload.get("correlation_id")) or None,
            job_id=_text(payload.get("job_id")) or None,
            printer_id=_text(payload.get("printer_id")) or None,
            duration_ms=int(payload["duration_ms"]) if isinstance(payload.get("duration_ms"), (int, float)) else None,
            details=details,
        )
        return web.json_response({"data": event})

    async def delete(self, request: web.Request) -> web.Response:
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return web.json_response(
                {"data": None, "error": {"code": "admin_required", "message": "Administrator access is required"}},
                status=403,
            )
        await get_audit_log(request.app["hass"]).async_clear()
        return web.json_response({"data": {"cleared": True}})


class AuditSanitizeView(HomeAssistantView):
    url = API_PREFIX + "/sanitize"
    name = "api:ultimate_3d_studio:audit_sanitize"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return web.json_response(
                {"data": None, "error": {"code": "admin_required", "message": "Administrator access is required"}},
                status=403,
            )
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        audit = get_audit_log(request.app["hass"])
        confirmed = payload.get("confirmed") is True
        confirmation_text = str(payload.get("confirmation_text") or "").strip()
        if not confirmed:
            preview = await audit.async_sanitize_existing(apply=False)
            return web.json_response({"data": {
                **preview,
                "confirmation_required": True,
                "confirmation_text": "AUDIT BEREINIGEN",
            }})
        if confirmation_text != "AUDIT BEREINIGEN":
            return web.json_response(
                {"data": None, "error": {"code": "confirmation_required", "message": "AUDIT BEREINIGEN is required"}},
                status=409,
            )
        result = await audit.async_sanitize_existing(apply=True)
        await audit.async_append(
            category="System",
            component="audit_runtime",
            event="audit_history_sanitized",
            status="success",
            source="backend",
            details=result,
        )
        return web.json_response({"data": result})


def async_register_audit_views(hass: HomeAssistant) -> None:
    hass.http.register_view(AuditLogView())
    hass.http.register_view(AuditSanitizeView())
