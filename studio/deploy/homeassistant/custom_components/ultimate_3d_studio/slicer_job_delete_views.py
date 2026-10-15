"""Authenticated terminal slicer-job deletion endpoint for Studio."""
from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import API_BASE, VERSION
from .slicer_job_delete_client import async_delete_slicer_job
from .slicer_native_contract import (
    SlicerServerConfigurationError,
    SlicerServerError,
)


def _error(status: int, code: str, message: str) -> web.Response:
    return web.json_response({
        "data": None,
        "error": {"code": code, "message": message},
        "meta": {"api_version": "v1", "component_version": VERSION},
    }, status=status)


class SlicerJobDeleteView(HomeAssistantView):
    url = f"{API_BASE}/slicer/jobs/{{job_id}}/delete"
    name = "api:ultimate_3d_studio:slicer:jobs:delete"
    requires_auth = True

    async def post(
        self,
        request: web.Request,
        job_id: str,
    ) -> web.Response:
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return _error(
                403,
                "admin_required",
                "Administrator access is required",
            )
        try:
            payload = await request.json()
        except Exception:
            return _error(
                400,
                "invalid_json",
                "Request body must contain valid JSON",
            )
        if not isinstance(payload, dict) or payload.get("confirmed") is not True:
            return _error(
                409,
                "confirmation_required",
                "Explicit confirmation is required",
            )

        hass: HomeAssistant = request.app["hass"]
        try:
            result = await async_delete_slicer_job(hass, job_id)
        except SlicerServerConfigurationError as exc:
            return _error(503, "slicing_server_not_configured", str(exc))
        except SlicerServerError as exc:
            message = str(exc)
            status = 409 if "HTTP 409" in message else 404 if "HTTP 404" in message else 502
            return _error(status, "slicer_job_delete_failed", message)

        return web.json_response({
            "data": result,
            "error": None,
            "meta": {
                "api_version": "v1",
                "component_version": VERSION,
                "deleted": True,
            },
        })


def async_register_slicer_job_delete_views(
    hass: HomeAssistant,
) -> None:
    hass.http.register_view(SlicerJobDeleteView())
