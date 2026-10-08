"""Full gallery management HTTP API for Ultimate 3D Studio."""
from __future__ import annotations

from functools import partial
from pathlib import Path
import time
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import API_BASE, DOMAIN, VERSION
from .gallery_repository import StudioGalleryRepository

_DATA_REPOSITORY = "gallery_management_repository"
_DATA_VIEWS = "gallery_management_views_registered"


def _success(data: Any, **meta: Any) -> web.Response:
    return web.json_response({
        "data": data,
        "error": None,
        "meta": {"api_version": "v1", "component_version": VERSION, **meta},
    })


def _error(status: int, code: str, message: str) -> web.Response:
    return web.json_response({
        "data": None,
        "error": {"code": code, "message": message},
        "meta": {"api_version": "v1", "component_version": VERSION},
    }, status=status)


def _repository(hass: HomeAssistant) -> StudioGalleryRepository:
    data = hass.data.setdefault(DOMAIN, {})
    repository = data.get(_DATA_REPOSITORY)
    if not isinstance(repository, StudioGalleryRepository):
        repository = StudioGalleryRepository(
            Path(hass.config.path("printer_control_center", "archive"))
        )
        data[_DATA_REPOSITORY] = repository
    return repository


def _admin_error(request: web.Request) -> web.Response | None:
    user = request.get("hass_user")
    if user is None or not user.is_admin:
        return _error(403, "admin_required", "Administrator access is required")
    return None


def _confirmed_query(request: web.Request) -> bool:
    return request.query.get("confirmed", "").lower() in {"1", "true", "yes"}


async def _json(request: web.Request) -> tuple[dict[str, Any] | None, web.Response | None]:
    try:
        value = await request.json()
    except Exception:
        return None, _error(400, "invalid_json", "Request body must contain valid JSON")
    if not isinstance(value, dict):
        return None, _error(400, "invalid_json", "Request body must contain a JSON object")
    if value.get("confirmed") is not True:
        return None, _error(409, "confirmation_required", "Explicit confirmation is required")
    return value, None


class GalleryLibraryView(HomeAssistantView):
    url = f"{API_BASE}/gallery/manage"
    name = "api:ultimate_3d_studio:gallery:manage"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            data = await hass.async_add_executor_job(
                partial(
                    _repository(hass).list_folder,
                    request.query.get("folder", ""),
                    request.query.get("q", ""),
                    request.query.get("recursive", "0").lower() in {"1", "true", "yes"},
                )
            )
        except FileNotFoundError:
            return _error(404, "gallery_folder_not_found", "Gallery folder was not found")
        except (ValueError, NotADirectoryError) as exc:
            return _error(400, "invalid_gallery_folder", str(exc))
        return _success(data, count=len(data["items"]))


class GalleryAssetView(HomeAssistantView):
    url = f"{API_BASE}/gallery/manage/{{asset_id}}/{{operation}}"
    name = "api:ultimate_3d_studio:gallery:manage:asset"
    requires_auth = True

    async def get(self, request: web.Request, asset_id: str, operation: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        repository = _repository(hass)
        try:
            if operation == "preview":
                result = await hass.async_add_executor_job(repository.preview, asset_id)
                if result is None:
                    return _error(404, "preview_not_found", "No preview is available")
                payload, content_type = result
                return web.Response(body=payload, content_type=content_type, headers={"Cache-Control": "private, max-age=300"})
            if operation == "download":
                payload, filename = await hass.async_add_executor_job(repository.download, asset_id)
                content_type = "application/octet-stream"
            elif operation == "model-stl":
                payload, filename = await hass.async_add_executor_job(repository.model_stl, asset_id)
                content_type = "model/stl"
            else:
                return _error(404, "unknown_gallery_operation", "Unknown gallery operation")
        except FileNotFoundError:
            return _error(404, "gallery_model_not_found", "Gallery model was not found")
        except ValueError as exc:
            return _error(422, "gallery_conversion_failed", str(exc))
        safe = filename.replace('"', "_").replace("\r", "_").replace("\n", "_")
        return web.Response(
            body=payload,
            content_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{safe}"', "Cache-Control": "no-store"},
        )


class GalleryActionView(HomeAssistantView):
    url = f"{API_BASE}/gallery/manage/action"
    name = "api:ultimate_3d_studio:gallery:manage:action"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        body, body_error = await _json(request)
        if body_error is not None:
            return body_error
        assert body is not None
        action = str(body.get("action", ""))
        repository = _repository(request.app["hass"])
        hass: HomeAssistant = request.app["hass"]
        try:
            if action == "create_folder":
                result = await hass.async_add_executor_job(repository.create_folder, str(body.get("folder", "")), str(body.get("name", "")))
            elif action == "rename":
                result = await hass.async_add_executor_job(repository.rename, str(body.get("path", "")), str(body.get("new_name", "")))
            elif action == "move":
                result = await hass.async_add_executor_job(partial(repository.move, str(body.get("path", "")), str(body.get("target_folder", "")), bool(body.get("overwrite", False))))
            elif action == "delete":
                result = await hass.async_add_executor_job(repository.delete, str(body.get("path", "")))
            else:
                return _error(400, "unknown_gallery_action", "Unknown gallery action")
        except FileNotFoundError:
            return _error(404, "gallery_item_not_found", "Gallery item was not found")
        except FileExistsError:
            return _error(409, "gallery_item_exists", "The destination already contains an item with this name")
        except (ValueError, NotADirectoryError) as exc:
            return _error(400, "invalid_gallery_action", str(exc))
        return _success(result, action=action)


class GalleryUploadView(HomeAssistantView):
    url = f"{API_BASE}/gallery/manage/upload"
    name = "api:ultimate_3d_studio:gallery:manage:upload"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        if not _confirmed_query(request):
            return _error(409, "confirmation_required", "Explicit confirmation is required")
        hass: HomeAssistant = request.app["hass"]
        try:
            item = await hass.async_add_executor_job(
                partial(
                    _repository(hass).upload,
                    request.query.get("filename", ""),
                    await request.read(),
                    request.query.get("folder", ""),
                    request.query.get("overwrite", "0").lower() in {"1", "true", "yes"},
                )
            )
        except FileExistsError:
            return _error(409, "gallery_model_exists", "A model with this name already exists")
        except ValueError as exc:
            return _error(400, "invalid_gallery_upload", str(exc))
        return _success(item, uploaded=True)


class GalleryTransferView(HomeAssistantView):
    url = f"{API_BASE}/gallery/manage/transfer/{{operation}}"
    name = "api:ultimate_3d_studio:gallery:manage:transfer"
    requires_auth = True

    async def get(self, request: web.Request, operation: str) -> web.Response:
        if operation != "export":
            return _error(404, "unknown_gallery_operation", "Unknown gallery operation")
        hass: HomeAssistant = request.app["hass"]
        payload = await hass.async_add_executor_job(_repository(hass).export_zip)
        filename = f"ultimate-3d-studio-gallery-{int(time.time())}.zip"
        return web.Response(body=payload, content_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})

    async def post(self, request: web.Request, operation: str) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        hass: HomeAssistant = request.app["hass"]
        payload = await request.read()
        try:
            if operation == "inspect":
                result = await hass.async_add_executor_job(_repository(hass).inspect_zip, payload)
            elif operation == "import":
                if not _confirmed_query(request):
                    return _error(409, "confirmation_required", "Explicit confirmation is required")
                result = await hass.async_add_executor_job(
                    partial(
                        _repository(hass).import_zip,
                        payload,
                        request.query.get("overwrite", "0").lower() in {"1", "true", "yes"},
                    )
                )
            else:
                return _error(404, "unknown_gallery_operation", "Unknown gallery operation")
        except FileExistsError:
            return _error(409, "gallery_import_conflicts", "ZIP contains existing files")
        except ValueError as exc:
            return _error(400, "invalid_gallery_zip", str(exc))
        return _success(result, operation=operation)


def async_register_gallery_management_views(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(_DATA_VIEWS):
        return
    for view in (
        GalleryLibraryView(),
        GalleryAssetView(),
        GalleryActionView(),
        GalleryUploadView(),
        GalleryTransferView(),
    ):
        hass.http.register_view(view)
    data[_DATA_VIEWS] = True
