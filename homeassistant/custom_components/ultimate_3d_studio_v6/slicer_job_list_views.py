"""Authenticated V6 slicer-job list endpoint."""
from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import API_BASE, VERSION
from .slicer_job_list_client import async_list_slicer_jobs
from .slicer_native_contract import (
    SlicerServerConfigurationError,
    SlicerServerError,
)


class SlicerJobListView(HomeAssistantView):
    url = f"{API_BASE}/slicer/jobs-list"
    name = "api:ultimate_3d_studio_v6:slicer:jobs:list"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            items = await async_list_slicer_jobs(hass)
        except SlicerServerConfigurationError as exc:
            return web.json_response({
                "data": None,
                "error": {
                    "code": "slicing_server_not_configured",
                    "message": str(exc),
                },
                "meta": {
                    "api_version": "v1",
                    "component_version": VERSION,
                },
            }, status=503)
        except SlicerServerError as exc:
            return web.json_response({
                "data": None,
                "error": {
                    "code": "slicer_job_list_failed",
                    "message": str(exc),
                },
                "meta": {
                    "api_version": "v1",
                    "component_version": VERSION,
                },
            }, status=502)

        return web.json_response({
            "data": {"items": items},
            "error": None,
            "meta": {
                "api_version": "v1",
                "component_version": VERSION,
                "count": len(items),
            },
        })


def async_register_slicer_job_list_views(
    hass: HomeAssistant,
) -> None:
    hass.http.register_view(SlicerJobListView())