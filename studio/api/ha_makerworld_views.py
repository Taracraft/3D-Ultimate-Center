"""Home Assistant HTTP adapters for MakerWorld search, import and asset provenance."""

from __future__ import annotations

from dataclasses import asdict

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .makerworld_application import V1MakerWorldApplication


def _json_response(response) -> web.Response:
    status = 200
    if response.error is not None:
        status = {
            "not_found": 404,
            "validation_failed": 400,
            "internal_error": 500,
        }.get(response.error.code, 500)
    return web.json_response(asdict(response), status=status)


class _MakerWorldView(HomeAssistantView):
    requires_auth = True

    def __init__(self, hass: HomeAssistant, application: V1MakerWorldApplication) -> None:
        self._hass = hass
        self._application = application


class V1MakerWorldSearchView(_MakerWorldView):
    url = "/api/ultimate_3d_studio/v1/makerworld/search"
    name = "api:printer_control_center:v1:makerworld_search"

    async def get(self, request: web.Request) -> web.Response:
        query = request.query.get("q", "").strip()
        cursor = request.query.get("cursor")
        try:
            limit = int(request.query.get("limit", "24"))
        except ValueError:
            limit = 24
        response = await self._application.search(query, cursor, limit)
        return _json_response(response)


class V1MakerWorldImportView(_MakerWorldView):
    url = "/api/ultimate_3d_studio/v1/makerworld/import"
    name = "api:printer_control_center:v1:makerworld_import"

    async def post(self, request: web.Request) -> web.Response:
        payload = await request.json()
        response = await self._application.import_model(payload)
        return _json_response(response)


class V1MakerWorldAssetInfoView(_MakerWorldView):
    url = "/api/ultimate_3d_studio/v1/makerworld/assets/{asset_id}"
    name = "api:printer_control_center:v1:makerworld_asset_info"

    async def get(self, request: web.Request, asset_id: str) -> web.Response:
        response = await self._hass.async_add_executor_job(
            self._application.get_asset_info,
            asset_id,
        )
        return _json_response(response)


def register_v1_makerworld_views(
    hass: HomeAssistant,
    application: V1MakerWorldApplication,
) -> None:
    for view_type in (
        V1MakerWorldSearchView,
        V1MakerWorldImportView,
        V1MakerWorldAssetInfoView,
    ):
        hass.http.register_view(view_type(hass, application))
