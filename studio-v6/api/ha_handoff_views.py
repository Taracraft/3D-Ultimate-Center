"""Home Assistant HTTP adapters for Gallery and Queue handoffs."""

from __future__ import annotations

from dataclasses import asdict

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .application import V1Application


def _json_response(response) -> web.Response:
    status = 200
    if response.error is not None:
        status = {
            "not_found": 404,
            "validation_failed": 400,
            "internal_error": 500,
        }.get(response.error.code, 500)
    return web.json_response(asdict(response), status=status)


class _HandoffView(HomeAssistantView):
    requires_auth = True

    def __init__(self, hass: HomeAssistant, application: V1Application) -> None:
        self._hass = hass
        self._application = application


class V1GalleryToStudioView(_HandoffView):
    url = "/api/printer_control_center/v1/handoffs/gallery/{asset_id}/studio"
    name = "api:printer_control_center:v1:gallery_to_studio"

    async def post(self, request: web.Request, asset_id: str) -> web.Response:
        payload = await request.json() if request.can_read_body else {}
        response = await self._hass.async_add_executor_job(
            self._application.gallery_to_studio,
            asset_id,
            payload.get("project_id"),
            payload.get("plate_id"),
        )
        return _json_response(response)


class V1QueueToStudioView(_HandoffView):
    url = "/api/printer_control_center/v1/handoffs/queue/{queue_item_id}/studio"
    name = "api:printer_control_center:v1:queue_to_studio"

    async def post(self, request: web.Request, queue_item_id: str) -> web.Response:
        payload = await request.json() if request.can_read_body else {}
        response = await self._hass.async_add_executor_job(
            self._application.queue_to_studio,
            queue_item_id,
            payload.get("project_id"),
        )
        return _json_response(response)


def register_v1_handoff_views(
    hass: HomeAssistant,
    application: V1Application,
) -> None:
    hass.http.register_view(V1GalleryToStudioView(hass, application))
    hass.http.register_view(V1QueueToStudioView(hass, application))