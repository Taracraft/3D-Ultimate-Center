"""Home Assistant HTTP adapter for Gallery Core."""

from __future__ import annotations

from dataclasses import asdict

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .application import V1Application


class V1GalleryView(HomeAssistantView):
    url = "/api/printer_control_center/v1/gallery"
    name = "api:printer_control_center:v1:gallery"
    requires_auth = True

    def __init__(self, hass: HomeAssistant, application: V1Application) -> None:
        self._hass = hass
        self._application = application

    async def get(self, request: web.Request) -> web.Response:
        query = request.query.get("q", "")
        try:
            limit = int(request.query.get("limit", "100"))
        except ValueError:
            limit = 100
        response = await self._hass.async_add_executor_job(
            self._application.search_gallery,
            query,
            limit,
        )
        status = 200 if response.error is None else 400
        return web.json_response(asdict(response), status=status)


def register_v1_gallery_views(
    hass: HomeAssistant,
    application: V1Application,
) -> None:
    hass.http.register_view(V1GalleryView(hass, application))
