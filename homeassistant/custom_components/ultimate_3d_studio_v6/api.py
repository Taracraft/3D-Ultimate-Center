"""Authenticated HTTP API for Ultimate 3D Studio V6."""

from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .commands import PrinterCommandError, PrinterCommandRequest, command_capabilities
from .const import API_BASE, DATA_RUNTIMES, DATA_VIEWS_REGISTERED, DOMAIN, VERSION
from .discovery import discover
from .gallery_runtime import V6GalleryRuntime
from .makerworld_catalog import MakerWorldCatalog
from .runtime import Ultimate3DStudioRuntime

_LOGGER = logging.getLogger(__name__)
_DATA_GALLERY = "gallery_runtime"
_DATA_MAKERWORLD = "makerworld_catalog"


def _success(data: Any, **meta: Any) -> web.Response:
    return web.json_response(
        {
            "data": data,
            "error": None,
            "meta": {
                "api_version": "v1",
                "component_version": VERSION,
                **meta,
            },
        }
    )


def _error(status: int, code: str, message: str) -> web.Response:
    return web.json_response(
        {
            "data": None,
            "error": {"code": code, "message": message},
            "meta": {"api_version": "v1", "component_version": VERSION},
        },
        status=status,
    )


def _runtimes(hass: HomeAssistant) -> Iterable[Ultimate3DStudioRuntime]:
    runtimes = hass.data.get(DOMAIN, {}).get(DATA_RUNTIMES, {})
    if not isinstance(runtimes, dict):
        return ()
    return tuple(
        runtime
        for runtime in runtimes.values()
        if isinstance(runtime, Ultimate3DStudioRuntime)
    )


def _gallery(hass: HomeAssistant) -> V6GalleryRuntime:
    domain_data = hass.data.setdefault(DOMAIN, {})
    gallery = domain_data.get(_DATA_GALLERY)
    if not isinstance(gallery, V6GalleryRuntime):
        gallery = V6GalleryRuntime(hass)
        domain_data[_DATA_GALLERY] = gallery
    return gallery


def _makerworld(hass: HomeAssistant) -> MakerWorldCatalog:
    domain_data = hass.data.setdefault(DOMAIN, {})
    catalog = domain_data.get(_DATA_MAKERWORLD)
    if not isinstance(catalog, MakerWorldCatalog):
        catalog = MakerWorldCatalog(hass)
        domain_data[_DATA_MAKERWORLD] = catalog
    return catalog


def _admin_error(request: web.Request) -> web.Response | None:
    user = request.get("hass_user")
    if user is None or not user.is_admin:
        return _error(403, "admin_required", "Administrator access is required")
    return None


async def _confirmed_payload(request: web.Request) -> tuple[dict[str, Any] | None, web.Response | None]:
    try:
        payload = await request.json()
    except Exception:
        return None, _error(400, "invalid_json", "Request body must contain valid JSON")
    if not isinstance(payload, dict):
        return None, _error(400, "invalid_json", "Request body must contain a JSON object")
    if payload.get("confirmed") is not True:
        return None, _error(409, "confirmation_required", "Explicit confirmation is required")
    return payload, None


class HealthView(HomeAssistantView):
    url = f"{API_BASE}/health"
    name = "api:ultimate_3d_studio_v6:health"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        runtimes = tuple(_runtimes(hass))
        return _success(
            {
                "status": "ready"
                if runtimes and all(runtime.is_ready for runtime in runtimes)
                else "idle",
                "entries": [runtime.health() for runtime in runtimes],
            },
            entry_count=len(runtimes),
            provider_count=sum(runtime.provider_count for runtime in runtimes),
        )


class PrintersView(HomeAssistantView):
    url = f"{API_BASE}/printers"
    name = "api:ultimate_3d_studio_v6:printers"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        printers: list[dict[str, object]] = []
        for runtime in _runtimes(hass):
            printers.extend(
                snapshot.as_dict() for snapshot in await runtime.async_printers()
            )
        return _success({"items": printers}, count=len(printers))


class GalleryView(HomeAssistantView):
    url = f"{API_BASE}/gallery"
    name = "api:ultimate_3d_studio_v6:gallery"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        query = request.query.get("q", "")
        try:
            limit = int(request.query.get("limit", "100"))
        except ValueError:
            limit = 100
        try:
            items = await hass.async_add_executor_job(_gallery(hass).search, query, limit)
        except ValueError as exc:
            return _error(400, "invalid_gallery_query", str(exc))
        except Exception:
            _LOGGER.exception("V6 gallery scan failed")
            return _error(500, "gallery_scan_failed", "V6 gallery could not be scanned")
        return _success({"items": items}, count=len(items), legacy_v5_read_only=True)


class GalleryPreviewView(HomeAssistantView):
    url = f"{API_BASE}/gallery/{{asset_id}}/preview"
    name = "api:ultimate_3d_studio_v6:gallery:preview"
    requires_auth = True

    async def get(self, request: web.Request, asset_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            result = await hass.async_add_executor_job(_gallery(hass).preview, asset_id)
        except (KeyError, ValueError):
            return _error(404, "preview_not_found", "No preview is available for this asset")
        if result is None:
            return _error(404, "preview_not_found", "No preview is available for this asset")
        payload, content_type = result
        return web.Response(
            body=payload,
            content_type=content_type,
            headers={"Cache-Control": "private, max-age=300"},
        )


class GalleryDownloadView(HomeAssistantView):
    url = f"{API_BASE}/gallery/{{asset_id}}/download"
    name = "api:ultimate_3d_studio_v6:gallery:download"
    requires_auth = True

    async def get(self, request: web.Request, asset_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            payload, content_type, filename = await hass.async_add_executor_job(
                _gallery(hass).download,
                asset_id,
            )
        except (KeyError, ValueError):
            return _error(404, "gallery_asset_not_found", "Gallery asset was not found")
        safe_filename = filename.replace('"', "_").replace("\r", "_").replace("\n", "_")
        return web.Response(
            body=payload,
            content_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "Cache-Control": "no-store",
            },
        )


class MakerWorldCatalogView(HomeAssistantView):
    url = f"{API_BASE}/makerworld/catalog"
    name = "api:ultimate_3d_studio_v6:makerworld:catalog"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        items = await _makerworld(hass).async_list()
        return _success(
            {
                "items": items,
                "official_search_url": "https://makerworld.com/de/search/models",
                "public_api_available": False,
                "url_import_supported": True,
            },
            count=len(items),
        )

    async def post(self, request: web.Request) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        payload, payload_error = await _confirmed_payload(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None
        model_url = str(payload.get("model_url", "")).strip()
        try:
            item = await _makerworld(request.app["hass"]).async_add(model_url)
        except ValueError as exc:
            return _error(400, "invalid_makerworld_url", str(exc))
        except Exception:
            _LOGGER.exception("MakerWorld metadata import failed for %s", model_url)
            return _error(
                502,
                "makerworld_metadata_failed",
                "MakerWorld model metadata could not be loaded",
            )
        return _success(item, added=True)


class MakerWorldRefreshView(HomeAssistantView):
    url = f"{API_BASE}/makerworld/catalog/{{model_id}}/refresh"
    name = "api:ultimate_3d_studio_v6:makerworld:refresh"
    requires_auth = True

    async def post(self, request: web.Request, model_id: str) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        _payload, payload_error = await _confirmed_payload(request)
        if payload_error is not None:
            return payload_error
        try:
            item = await _makerworld(request.app["hass"]).async_refresh(model_id)
        except ValueError as exc:
            return _error(400, "invalid_makerworld_url", str(exc))
        except Exception:
            _LOGGER.exception("MakerWorld metadata refresh failed for %s", model_id)
            return _error(
                502,
                "makerworld_metadata_failed",
                "MakerWorld model metadata could not be refreshed",
            )
        if item is None:
            return _error(404, "makerworld_model_not_found", "MakerWorld catalog item was not found")
        return _success(item, refreshed=True)


class MakerWorldRemoveView(HomeAssistantView):
    url = f"{API_BASE}/makerworld/catalog/{{model_id}}/remove"
    name = "api:ultimate_3d_studio_v6:makerworld:remove"
    requires_auth = True

    async def post(self, request: web.Request, model_id: str) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        _payload, payload_error = await _confirmed_payload(request)
        if payload_error is not None:
            return payload_error
        removed = await _makerworld(request.app["hass"]).async_remove(model_id)
        if removed is None:
            return _error(404, "makerworld_model_not_found", "MakerWorld catalog item was not found")
        return _success(removed, removed=True)


class JobsView(HomeAssistantView):
    url = f"{API_BASE}/jobs"
    name = "api:ultimate_3d_studio_v6:jobs"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        current: list[dict[str, Any]] = []
        queue: list[dict[str, Any]] = []
        history: list[dict[str, Any]] = []

        for runtime in _runtimes(hass):
            await runtime.async_printers()
            data = runtime.jobs.as_dict()
            current.extend(data["current"])
            queue.extend(data["queue"])
            history.extend(data["history"])

        history.sort(
            key=lambda item: item.get("completed_at")
            or item.get("started_at")
            or "",
            reverse=True,
        )
        queue.sort(key=lambda item: item.get("queued_at") or "", reverse=True)
        return _success(
            {
                "current": current,
                "queue": queue,
                "history": history,
                "read_only": False,
                "persistent": True,
                "repeat_supported": True,
                "queue_remove_supported": True,
                "queue_execution_enabled": False,
            },
            current_count=len(current),
            queue_count=len(queue),
            history_count=len(history),
        )


class JobRepeatView(HomeAssistantView):
    url = f"{API_BASE}/jobs/{{job_id}}/repeat"
    name = "api:ultimate_3d_studio_v6:jobs:repeat"
    requires_auth = True

    async def post(self, request: web.Request, job_id: str) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        _payload, payload_error = await _confirmed_payload(request)
        if payload_error is not None:
            return payload_error

        hass: HomeAssistant = request.app["hass"]
        for runtime in _runtimes(hass):
            queued = await runtime.jobs.async_repeat(job_id)
            if queued is not None:
                _LOGGER.info(
                    "V6 history job queued for repeat: source=%s queue=%s",
                    job_id,
                    queued.get("job_id"),
                )
                return _success(queued, queued=True, execution_started=False)

        return _error(404, "job_not_found", "No matching history job was found")


class QueuedJobRemoveView(HomeAssistantView):
    url = f"{API_BASE}/jobs/queue/{{job_id}}/remove"
    name = "api:ultimate_3d_studio_v6:jobs:queue:remove"
    requires_auth = True

    async def post(self, request: web.Request, job_id: str) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        _payload, payload_error = await _confirmed_payload(request)
        if payload_error is not None:
            return payload_error

        hass: HomeAssistant = request.app["hass"]
        for runtime in _runtimes(hass):
            removed = await runtime.jobs.async_remove_queued(job_id)
            if removed is not None:
                _LOGGER.info("V6 queued job removed: queue=%s", job_id)
                return _success(removed, removed=True)

        return _error(404, "queued_job_not_found", "No matching queued job was found")


class CapabilitiesView(HomeAssistantView):
    url = f"{API_BASE}/capabilities"
    name = "api:ultimate_3d_studio_v6:capabilities"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        return _success(
            {
                "commands": command_capabilities(),
                "execution_policy": {
                    "admin_only": True,
                    "confirmation_required": True,
                    "offline_execution": False,
                    "execution_endpoint_enabled": True,
                },
            }
        )


class CommandView(HomeAssistantView):
    url = f"{API_BASE}/commands"
    name = "api:ultimate_3d_studio_v6:commands"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error

        payload, payload_error = await _confirmed_payload(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None

        try:
            command_request = PrinterCommandRequest.from_payload(payload)
        except PrinterCommandError as exc:
            return _error(400, "invalid_command", str(exc))

        hass: HomeAssistant = request.app["hass"]
        try:
            for runtime in _runtimes(hass):
                result = await runtime.async_command(
                    command_request.printer_id,
                    command_request.command,
                    speed_level=command_request.speed_level,
                )
                if result is not None:
                    _LOGGER.info(
                        "V6 printer command accepted: printer=%s provider=%s command=%s sequence=%s",
                        result.printer_id,
                        result.provider,
                        result.command,
                        result.sequence_id,
                    )
                    return _success(result.as_dict(), accepted=True)
        except RuntimeError as exc:
            _LOGGER.warning(
                "V6 printer command rejected: printer=%s command=%s reason=%s",
                command_request.printer_id,
                command_request.command,
                exc,
            )
            return _error(409, "printer_unavailable", str(exc))
        except Exception:
            _LOGGER.exception(
                "V6 printer command failed: printer=%s command=%s",
                command_request.printer_id,
                command_request.command,
            )
            return _error(500, "command_failed", "Printer command could not be published")

        return _error(404, "printer_not_found", "No matching V6 printer was found")


class DiscoveryView(HomeAssistantView):
    url = f"{API_BASE}/discovery"
    name = "api:ultimate_3d_studio_v6:discovery"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        candidates = await hass.async_add_executor_job(discover)
        items = [candidate.as_dict() for candidate in candidates]
        return _success({"items": items}, count=len(items))


def async_register_http_views(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(DATA_VIEWS_REGISTERED):
        return

    hass.http.register_view(HealthView())
    hass.http.register_view(PrintersView())
    hass.http.register_view(GalleryView())
    hass.http.register_view(GalleryPreviewView())
    hass.http.register_view(GalleryDownloadView())
    hass.http.register_view(MakerWorldCatalogView())
    hass.http.register_view(MakerWorldRefreshView())
    hass.http.register_view(MakerWorldRemoveView())
    hass.http.register_view(JobsView())
    hass.http.register_view(JobRepeatView())
    hass.http.register_view(QueuedJobRemoveView())
    hass.http.register_view(CapabilitiesView())
    hass.http.register_view(CommandView())
    hass.http.register_view(DiscoveryView())
    domain_data[DATA_VIEWS_REGISTERED] = True