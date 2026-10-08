"""Authenticated Studio printer SD-card management endpoints."""
from __future__ import annotations

from functools import partial
from pathlib import PurePosixPath
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import API_BASE, VERSION
from .printer_storage import PrinterStorageError
from .printer_storage_runtime import (
    async_printer_storage_summary,
    async_storage_for_printer,
)

MAX_REQUEST_BYTES = 600_000_000


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


async def _confirmed_json(
    request: web.Request,
) -> tuple[dict[str, Any] | None, web.Response | None]:
    try:
        payload = await request.json()
    except Exception:
        return None, _error(400, "invalid_json", "Request body must contain valid JSON")
    if not isinstance(payload, dict):
        return None, _error(400, "invalid_json", "Request body must contain a JSON object")
    if payload.get("confirmed") is not True:
        return None, _error(409, "confirmation_required", "Explicit confirmation is required")
    return payload, None


class PrinterStorageSummaryView(HomeAssistantView):
    url = f"{API_BASE}/storage"
    name = "api:ultimate_3d_studio:storage"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        items = await async_printer_storage_summary(request.app["hass"])
        return _success({"items": items}, count=len(items))


class PrinterStorageListView(HomeAssistantView):
    url = f"{API_BASE}/storage/{{printer_id}}"
    name = "api:ultimate_3d_studio:storage:list"
    requires_auth = True

    async def get(self, request: web.Request, printer_id: str) -> web.Response:
        folder = request.query.get("folder", "/")
        previews = request.query.get("previews", "1").casefold() not in {
            "0",
            "false",
            "no",
        }
        try:
            storage = await async_storage_for_printer(
                request.app["hass"],
                printer_id,
            )
            data = await request.app["hass"].async_add_executor_job(
                partial(
                    storage.list_items,
                    folder,
                    include_previews=previews,
                )
            )
        except PrinterStorageError as exc:
            return _error(409, "storage_unavailable", str(exc))
        except Exception as exc:
            return _error(502, "storage_list_failed", str(exc))
        return _success(data, printer_id=printer_id)


class PrinterStorageTreeView(HomeAssistantView):
    url = f"{API_BASE}/storage/{{printer_id}}/tree"
    name = "api:ultimate_3d_studio:storage:tree"
    requires_auth = True

    async def get(self, request: web.Request, printer_id: str) -> web.Response:
        try:
            storage = await async_storage_for_printer(
                request.app["hass"],
                printer_id,
            )
            items = await request.app["hass"].async_add_executor_job(storage.tree)
        except PrinterStorageError as exc:
            return _error(409, "storage_unavailable", str(exc))
        except Exception as exc:
            return _error(502, "storage_tree_failed", str(exc))
        return _success(
            {"items": items},
            count=len(items),
            printer_id=printer_id,
        )


class PrinterStorageDownloadView(HomeAssistantView):
    url = f"{API_BASE}/storage/{{printer_id}}/download"
    name = "api:ultimate_3d_studio:storage:download"
    requires_auth = True

    async def get(self, request: web.Request, printer_id: str) -> web.Response:
        path = request.query.get("path", "")
        if not path:
            return _error(400, "path_required", "SD-card path is required")
        try:
            storage = await async_storage_for_printer(
                request.app["hass"],
                printer_id,
            )
            data = await request.app["hass"].async_add_executor_job(
                storage.download,
                path,
            )
        except PrinterStorageError as exc:
            return _error(409, "storage_download_failed", str(exc))
        except Exception as exc:
            return _error(502, "storage_download_failed", str(exc))
        filename = PurePosixPath(path).name.replace('"', "_") or "printer-file.bin"
        return web.Response(
            body=data,
            content_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )


class PrinterStorageUploadView(HomeAssistantView):
    url = f"{API_BASE}/storage/{{printer_id}}/upload"
    name = "api:ultimate_3d_studio:storage:upload"
    requires_auth = True

    async def post(self, request: web.Request, printer_id: str) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        if request.query.get("confirmed", "").casefold() not in {
            "1",
            "true",
            "yes",
        }:
            return _error(
                409,
                "confirmation_required",
                "Explicit confirmation is required",
            )
        filename = request.query.get("filename", "")
        folder = request.query.get("folder", "/")
        overwrite = request.query.get("overwrite", "0").casefold() in {
            "1",
            "true",
            "yes",
        }
        if not filename:
            return _error(400, "filename_required", "Filename is required")
        content_length = request.content_length or 0
        if content_length > MAX_REQUEST_BYTES:
            return _error(413, "upload_too_large", "Upload exceeds 600 MB")
        data = await request.read()
        if not data:
            return _error(400, "empty_upload", "Upload body is empty")
        if len(data) > MAX_REQUEST_BYTES:
            return _error(413, "upload_too_large", "Upload exceeds 600 MB")
        try:
            storage = await async_storage_for_printer(
                request.app["hass"],
                printer_id,
            )
            item = await request.app["hass"].async_add_executor_job(
                partial(
                    storage.upload,
                    filename,
                    data,
                    folder,
                    overwrite=overwrite,
                )
            )
        except FileExistsError:
            return _error(
                409,
                "target_exists",
                "A file with this name already exists",
            )
        except PrinterStorageError as exc:
            return _error(409, "storage_upload_failed", str(exc))
        except Exception as exc:
            return _error(502, "storage_upload_failed", str(exc))
        return _success(item, uploaded=True, printer_id=printer_id)


class PrinterStorageActionView(HomeAssistantView):
    url = f"{API_BASE}/storage/{{printer_id}}/actions"
    name = "api:ultimate_3d_studio:storage:actions"
    requires_auth = True

    async def post(self, request: web.Request, printer_id: str) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        payload, payload_error = await _confirmed_json(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None
        action = str(payload.get("action", "")).strip().casefold()
        path = str(payload.get("path", "")).strip()
        target_folder = str(payload.get("target_folder", "/")).strip() or "/"
        name = str(payload.get("name", "")).strip()
        overwrite = payload.get("overwrite") is True

        try:
            storage = await async_storage_for_printer(
                request.app["hass"],
                printer_id,
            )
            if action == "create_folder":
                result = await request.app["hass"].async_add_executor_job(
                    storage.create_folder,
                    target_folder,
                    name,
                )
            elif action == "rename":
                result = await request.app["hass"].async_add_executor_job(
                    storage.rename,
                    path,
                    name,
                )
            elif action == "move":
                result = await request.app["hass"].async_add_executor_job(
                    partial(
                        storage.move,
                        path,
                        target_folder,
                        overwrite=overwrite,
                    )
                )
            elif action == "copy":
                result = await request.app["hass"].async_add_executor_job(
                    partial(
                        storage.copy,
                        path,
                        target_folder,
                        overwrite=overwrite,
                    )
                )
            elif action == "delete":
                await request.app["hass"].async_add_executor_job(
                    storage.delete,
                    path,
                )
                result = {"deleted": True, "path": path}
            else:
                return _error(400, "invalid_action", "Unknown storage action")
        except FileExistsError:
            return _error(
                409,
                "target_exists",
                "A matching target already exists",
            )
        except PrinterStorageError as exc:
            return _error(409, "storage_action_failed", str(exc))
        except Exception as exc:
            return _error(502, "storage_action_failed", str(exc))
        return _success(result, action=action, printer_id=printer_id)


def async_register_printer_storage_views(hass: HomeAssistant) -> None:
    for view in (
        PrinterStorageSummaryView(),
        PrinterStorageListView(),
        PrinterStorageTreeView(),
        PrinterStorageDownloadView(),
        PrinterStorageUploadView(),
        PrinterStorageActionView(),
    ):
        hass.http.register_view(view)
