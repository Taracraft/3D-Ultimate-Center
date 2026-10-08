"""Authenticated MakerWorld browse, detail and transfer API for Studio."""
from __future__ import annotations

from functools import partial
import logging
from pathlib import Path
import re
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import API_BASE, DOMAIN, VERSION
from .gallery_repository import StudioGalleryRepository
from .geometry_export import export_binary_stl
from .makerworld_detail import async_load_detail
from .makerworld_download import async_download_instance as async_resolve_download
from .makerworld_runtime import MakerWorldError, get_makerworld_runtime
from .rich_text import readable_rich_text, safe_rich_html

_LOGGER = logging.getLogger(__name__)
_DATA_VIEWS = "makerworld_browser_views_registered"
_GALLERY_REPOSITORY_KEY = "gallery_management_repository"


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


def _gallery(hass: HomeAssistant) -> StudioGalleryRepository:
    data = hass.data.setdefault(DOMAIN, {})
    repository = data.get(_GALLERY_REPOSITORY_KEY)
    if not isinstance(repository, StudioGalleryRepository):
        repository = StudioGalleryRepository(
            Path(hass.config.path("printer_control_center", "archive"))
        )
        data[_GALLERY_REPOSITORY_KEY] = repository
    return repository


def _safe_filename(value: Any, instance_id: str) -> str:
    name = str(value or "").strip()
    if not name:
        name = f"MakerWorld-{instance_id}.3mf"
    if not name.lower().endswith(".3mf"):
        name += ".3mf"
    name = Path(name).name
    name = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß._() +\-]", "_", name)
    return name[:220] or f"MakerWorld-{instance_id}.3mf"


async def _download_payload(request: web.Request, instance_id: str) -> bytes:
    runtime = get_makerworld_runtime(request.app["hass"])
    design_id = str(request.query.get("design_id", "")).strip()
    profile_id = str(request.query.get("profile_id", "")).strip()
    model_id = str(request.query.get("model_id", "")).strip()
    if design_id or profile_id or model_id:
        return await runtime.async_download_instance(
            instance_id,
            design_id=design_id,
            profile_id=profile_id,
            model_id=model_id,
        )
    return await async_resolve_download(runtime, instance_id)


async def _download_payload_from_body(
    request: web.Request,
    instance_id: str,
    body: dict[str, Any],
) -> bytes:
    runtime = get_makerworld_runtime(request.app["hass"])
    design_id = str(body.get("design_id", "")).strip()
    profile_id = str(body.get("profile_id", "")).strip()
    model_id = str(body.get("model_id", "")).strip()
    if design_id or profile_id or model_id:
        return await runtime.async_download_instance(
            instance_id,
            design_id=design_id,
            profile_id=profile_id,
            model_id=model_id,
        )
    return await async_resolve_download(runtime, instance_id)


class MakerWorldBrowseView(HomeAssistantView):
    url = f"{API_BASE}/makerworld/browse"
    name = "api:ultimate_3d_studio:makerworld:browse"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        try:
            offset = int(request.query.get("offset", "0"))
            limit = int(request.query.get("limit", "24"))
        except ValueError:
            return _error(400, "invalid_pagination", "offset and limit must be integers")
        terms = request.query.getall("term", [])
        runtime = get_makerworld_runtime(request.app["hass"])
        try:
            data = await runtime.async_browse(
                query=request.query.get("q", ""),
                nav_key=request.query.get("nav_key", "Trending"),
                offset=offset,
                limit=limit,
                terms=terms,
            )
        except ValueError as exc:
            return _error(400, "invalid_makerworld_query", str(exc))
        except MakerWorldError as exc:
            _LOGGER.warning("MakerWorld browse failed: %s", exc)
            return _error(502, "makerworld_browse_failed", str(exc))
        return _success(data, count=len(data["items"]))


class MakerWorldDetailView(HomeAssistantView):
    url = f"{API_BASE}/makerworld/design/{{design_id}}"
    name = "api:ultimate_3d_studio:makerworld:detail"
    requires_auth = True

    async def get(self, request: web.Request, design_id: str) -> web.Response:
        runtime = get_makerworld_runtime(request.app["hass"])
        try:
            detail = await async_load_detail(runtime, design_id)
            detail["description_html"] = safe_rich_html(detail.get("description", ""))
            detail["description"] = readable_rich_text(
                detail.get("description", ""),
                30_000,
            )
        except ValueError as exc:
            return _error(400, "invalid_makerworld_design", str(exc))
        except MakerWorldError as exc:
            _LOGGER.warning("MakerWorld detail failed for %s: %s", design_id, exc)
            return _error(502, "makerworld_detail_failed", str(exc))
        except Exception as exc:
            _LOGGER.exception("Unexpected MakerWorld detail error for %s", design_id)
            return _error(
                502,
                "makerworld_detail_failed",
                f"Unerwarteter MakerWorld-Detailfehler: {exc}",
            )
        return _success(detail, instance_count=detail["instance_count"])


class MakerWorldInstanceView(HomeAssistantView):
    url = f"{API_BASE}/makerworld/instance/{{instance_id}}/{{operation}}"
    name = "api:ultimate_3d_studio:makerworld:instance"
    requires_auth = True

    async def get(
        self,
        request: web.Request,
        instance_id: str,
        operation: str,
    ) -> web.Response:
        if operation not in {"download", "model-stl"}:
            return _error(404, "unknown_makerworld_operation", "Unknown MakerWorld operation")
        try:
            payload = await _download_payload(request, instance_id)
            if operation == "model-stl":
                payload = await request.app["hass"].async_add_executor_job(
                    export_binary_stl,
                    payload,
                    f"MakerWorld {instance_id}",
                )
                filename = f"MakerWorld-{instance_id}.stl"
                content_type = "model/stl"
            else:
                filename = f"MakerWorld-{instance_id}.3mf"
                content_type = "model/3mf"
        except ValueError as exc:
            return _error(400, "invalid_makerworld_instance", str(exc))
        except MakerWorldError as exc:
            _LOGGER.warning("MakerWorld instance download failed for %s: %s", instance_id, exc)
            return _error(502, "makerworld_download_failed", str(exc))
        safe = filename.replace('"', "_")
        return web.Response(
            body=payload,
            content_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{safe}"',
                "Cache-Control": "no-store",
            },
        )

    async def post(
        self,
        request: web.Request,
        instance_id: str,
        operation: str,
    ) -> web.Response:
        if operation != "save":
            return _error(404, "unknown_makerworld_operation", "Unknown MakerWorld operation")
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        body, body_error = await _confirmed_payload(request)
        if body_error is not None:
            return body_error
        assert body is not None
        try:
            payload = await _download_payload_from_body(request, instance_id, body)
            item = await request.app["hass"].async_add_executor_job(
                partial(
                    _gallery(request.app["hass"]).upload,
                    _safe_filename(body.get("filename"), instance_id),
                    payload,
                    str(body.get("folder", "")),
                    bool(body.get("overwrite", False)),
                )
            )
        except FileExistsError:
            return _error(409, "gallery_model_exists", "A model with this name already exists")
        except ValueError as exc:
            return _error(400, "invalid_makerworld_transfer", str(exc))
        except MakerWorldError as exc:
            _LOGGER.warning("MakerWorld gallery transfer failed for %s: %s", instance_id, exc)
            return _error(502, "makerworld_download_failed", str(exc))
        return _success(item, saved=True)


def async_register_makerworld_views(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(_DATA_VIEWS):
        return
    hass.http.register_view(MakerWorldBrowseView())
    hass.http.register_view(MakerWorldDetailView())
    hass.http.register_view(MakerWorldInstanceView())
    data[_DATA_VIEWS] = True
