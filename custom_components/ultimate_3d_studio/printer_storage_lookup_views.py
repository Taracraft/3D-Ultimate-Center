"""Authenticated Studio printer SD-card file lookup endpoint."""
from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import API_BASE, VERSION
from .printer_storage import PrinterStorageError
from .printer_storage_lookup import find_storage_file
from .printer_storage_runtime import async_storage_for_printer


def _success(data: object, **meta: object) -> web.Response:
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


class PrinterStorageLookupView(HomeAssistantView):
    url = f"{API_BASE}/storage/{{printer_id}}/lookup"
    name = "api:ultimate_3d_studio:storage:lookup"
    requires_auth = True

    async def get(self, request: web.Request, printer_id: str) -> web.Response:
        filename = request.query.get("filename", "").strip()
        if not filename:
            return _error(400, "filename_required", "Filename is required")
        try:
            storage = await async_storage_for_printer(
                request.app["hass"],
                printer_id,
            )
            item = await request.app["hass"].async_add_executor_job(
                find_storage_file,
                storage,
                filename,
            )
        except PrinterStorageError as exc:
            return _error(409, "storage_unavailable", str(exc))
        except Exception as exc:
            return _error(502, "storage_lookup_failed", str(exc))
        if item is None:
            return _error(
                404,
                "storage_file_not_found",
                "The file is no longer present on the printer SD card",
            )
        return _success(item, printer_id=printer_id)


def async_register_printer_storage_lookup_views(
    hass: HomeAssistant,
) -> None:
    hass.http.register_view(PrinterStorageLookupView())
