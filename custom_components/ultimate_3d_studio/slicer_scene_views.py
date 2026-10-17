"""Authenticated editable 3MF scene endpoint for the Studio 3D Studio."""
from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .slicer_plate_views import API_PREFIX, _read_model
from .three_mf_scene import extract_scene


class SlicerProjectSceneView(HomeAssistantView):
    url = f"{API_PREFIX}/scene"
    name = "api:ultimate_3d_studio:slicer_project_scene"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        loaded = await _read_model(request)
        if isinstance(loaded, web.Response):
            return loaded
        filename, model = loaded
        try:
            plate_index = int(request.query.get("plate_index", "0"))
        except ValueError:
            return web.json_response({"error": "plate_index must be numeric"}, status=400)
        if plate_index < 0 or plate_index > 255:
            return web.json_response({"error": "plate_index is out of range"}, status=400)
        try:
            scene = await request.app["hass"].async_add_executor_job(
                extract_scene,
                filename,
                model,
                plate_index,
            )
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        return web.json_response({"data": scene}, headers={"Cache-Control": "no-store"})


def async_register_slicer_scene_views(hass: HomeAssistant) -> None:
    hass.http.register_view(SlicerProjectSceneView())
