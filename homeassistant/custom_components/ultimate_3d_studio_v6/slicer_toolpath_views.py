"""Authenticated real G-code toolpath preview endpoints with job-bound caching."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .gcode_toolpath import parse_toolpath
from .slicer_views import API_PREFIX
from .slicer_backend_router import V6SlicerBackendRouter
from .slicer_native_contract import SlicerServerConfigurationError, SlicerServerError

_CACHE_KEY = "ultimate_3d_studio_v6_toolpath_cache"
_CACHE_LIMIT = 3


def _cache(hass: HomeAssistant) -> OrderedDict[str, dict[str, Any]]:
    cache = hass.data.get(_CACHE_KEY)
    if isinstance(cache, OrderedDict):
        return cache
    created: OrderedDict[str, dict[str, Any]] = OrderedDict()
    hass.data[_CACHE_KEY] = created
    return created


def _complete_toolpath(data: bytes) -> dict[str, Any]:
    """Parse the complete artifact once for all later summary and range requests."""
    summary = parse_toolpath(data)
    layer_count = int(summary.get("layer_count", 0) or 0)
    if layer_count <= 0:
        raise ValueError("Toolpath enthält keine druckbaren Layer")
    complete = parse_toolpath(data, start_layer=0, end_layer=layer_count)
    chunk = complete.get("chunk")
    if not isinstance(chunk, dict) or not isinstance(chunk.get("layers"), list):
        raise ValueError("Toolpath konnte nicht vollständig aufgebaut werden")
    return complete


def _response_from_cached(
    cached: dict[str, Any],
    selected_layer: int | None,
    start_layer: int | None,
    end_layer: int | None,
) -> dict[str, Any]:
    parsed = cached.get("parsed")
    if not isinstance(parsed, dict):
        raise ValueError("Toolpath-Cache ist unvollständig")
    complete_chunk = parsed.get("chunk")
    all_layers = complete_chunk.get("layers") if isinstance(complete_chunk, dict) else None
    if not isinstance(all_layers, list):
        raise ValueError("Toolpath-Cache enthält keine Layer")

    result = {
        key: deepcopy(value)
        for key, value in parsed.items()
        if key not in {"chunk", "selected"}
    }
    layer_count = len(all_layers)

    if selected_layer is not None:
        if selected_layer < 0 or selected_layer >= layer_count:
            raise ValueError("Layer liegt außerhalb des gültigen Bereichs")
        result["selected"] = deepcopy(all_layers[selected_layer])

    if start_layer is not None or end_layer is not None:
        start = max(0, int(start_layer or 0))
        end = min(layer_count, int(end_layer if end_layer is not None else start + 1))
        if start >= layer_count or end <= start:
            raise ValueError("Layer-Bereich liegt außerhalb des gültigen Bereichs")
        layers = deepcopy(all_layers[start:end])
        result["chunk"] = {
            "start_layer": start,
            "end_layer": end,
            "layers": layers,
            "segment_count": sum(
                len(layer.get("segments", []))
                for layer in layers
                if isinstance(layer, dict)
            ),
        }
    return result


class SlicerJobToolpathView(HomeAssistantView):
    url = f"{API_PREFIX}/jobs/{{job_id}}/toolpath"
    name = "api:ultimate_3d_studio_v6:slicer_job_toolpath"
    requires_auth = True

    async def get(self, request: web.Request, job_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            layer_raw = request.query.get("layer")
            start_raw = request.query.get("start")
            end_raw = request.query.get("end")
            selected_layer = int(layer_raw) if layer_raw is not None else None
            start_layer = int(start_raw) if start_raw is not None else None
            end_layer = int(end_raw) if end_raw is not None else None

            cache = _cache(hass)
            cached = cache.get(job_id)
            cache_hit = cached is not None
            if cached is None:
                try:
                    data, _filename, digest, _content_type = await V6SlicerBackendRouter(
                        hass
                    ).async_artifact(job_id)
                except (SlicerServerConfigurationError, SlicerServerError) as exc:
                    return web.json_response({"error": str(exc)}, status=502)
                parsed = await hass.async_add_executor_job(_complete_toolpath, data)
                cached = {"digest": digest, "parsed": parsed}
                cache[job_id] = cached
                while len(cache) > _CACHE_LIMIT:
                    cache.popitem(last=False)
            cache.move_to_end(job_id)

            result = _response_from_cached(
                cached,
                selected_layer,
                start_layer,
                end_layer,
            )
        except (TypeError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

        return web.json_response(
            {"data": result},
            headers={
                "Cache-Control": "private, max-age=300",
                "X-U3D-Toolpath-Cache": "hit" if cache_hit else "miss",
            },
        )


def async_register_slicer_toolpath_views(hass: HomeAssistant) -> None:
    hass.http.register_view(SlicerJobToolpathView())