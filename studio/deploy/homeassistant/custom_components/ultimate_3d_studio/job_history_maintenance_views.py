"""Authenticated Studio print-history maintenance endpoints."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import API_BASE, DATA_RUNTIMES, DOMAIN, VERSION
from .runtime import Ultimate3DStudioRuntime


def _success(data: Any, **meta: Any) -> web.Response:
    return web.json_response({
        "data": data,
        "error": None,
        "meta": {
            "api_version": "v1",
            "component_version": VERSION,
            **meta,
        },
    })


def _error(status: int, code: str, message: str) -> web.Response:
    return web.json_response({
        "data": None,
        "error": {"code": code, "message": message},
        "meta": {"api_version": "v1", "component_version": VERSION},
    }, status=status)


def _runtimes(hass: HomeAssistant) -> Iterable[Ultimate3DStudioRuntime]:
    value = hass.data.get(DOMAIN, {}).get(DATA_RUNTIMES, {})
    if not isinstance(value, dict):
        return ()
    return tuple(
        runtime
        for runtime in value.values()
        if isinstance(runtime, Ultimate3DStudioRuntime)
    )


def _admin_error(request: web.Request) -> web.Response | None:
    user = request.get("hass_user")
    if user is None or not user.is_admin:
        return _error(403, "admin_required", "Administrator access is required")
    return None


async def _confirmation_error(request: web.Request) -> web.Response | None:
    try:
        payload = await request.json()
    except Exception:
        return _error(400, "invalid_json", "Request body must contain valid JSON")
    if not isinstance(payload, dict) or payload.get("confirmed") is not True:
        return _error(409, "confirmation_required", "Explicit confirmation is required")
    return None


class HistoryClearView(HomeAssistantView):
    url = f"{API_BASE}/jobs/history/clear"
    name = "api:ultimate_3d_studio:jobs:history:clear"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        confirmation_error = await _confirmation_error(request)
        if confirmation_error is not None:
            return confirmation_error
        removed = 0
        for runtime in _runtimes(request.app["hass"]):
            removed += await runtime.jobs.async_clear_history()
        return _success({"removed": removed}, cleared=True)


class HistoryRemoveView(HomeAssistantView):
    url = f"{API_BASE}/jobs/history/{{job_id}}/remove"
    name = "api:ultimate_3d_studio:jobs:history:remove"
    requires_auth = True

    async def post(self, request: web.Request, job_id: str) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        confirmation_error = await _confirmation_error(request)
        if confirmation_error is not None:
            return confirmation_error
        for runtime in _runtimes(request.app["hass"]):
            removed = await runtime.jobs.async_remove_history(job_id)
            if removed is not None:
                return _success(removed, removed=True)
        return _error(404, "history_job_not_found", "History job was not found")


def async_register_job_history_maintenance_views(
    hass: HomeAssistant,
) -> None:
    hass.http.register_view(HistoryClearView())
    hass.http.register_view(HistoryRemoveView())
