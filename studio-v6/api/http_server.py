"""Standalone aiohttp transport adapter for the V6 application facade."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, replace
from typing import Any, Awaitable, Callable
from uuid import uuid4

from aiohttp import ContentTypeError, web

from core.bootstrap import StudioRuntime
from core.database import CURRENT_SCHEMA_VERSION, schema_version
from core.version import API_VERSION, STUDIO_VERSION

from .contracts import ApiError, ApiResponse
from .routes import API_BASE, ROUTES

LOGGER = logging.getLogger(__name__)

RUNTIME_KEY: web.AppKey[StudioRuntime] = web.AppKey("studio_runtime", StudioRuntime)
CLOSE_RUNTIME_KEY: web.AppKey[bool] = web.AppKey("close_studio_runtime", bool)
if hasattr(web, "RequestKey"):
    REQUEST_ID_KEY = web.RequestKey(
        "printer_control_center_request_id",
        str,
    )
else:
    REQUEST_ID_KEY = "printer_control_center_request_id"

_ERROR_STATUS = {
    "validation_failed": 400,
    "not_found": 404,
    "method_not_allowed": 405,
    "request_too_large": 413,
    "internal_error": 500,
}


def _request_id(request: web.Request) -> str:
    value = request.get(REQUEST_ID_KEY)
    return value if value else uuid4().hex


def _response_status(response: ApiResponse, success_status: int = 200) -> int:
    if response.error is None:
        return success_status
    return _ERROR_STATUS.get(response.error.code, 500)


def _json_response(
    request: web.Request,
    response: ApiResponse,
    *,
    success_status: int = 200,
) -> web.Response:
    transport_response = replace(
        response,
        request_id=_request_id(request),
        version=API_VERSION,
    )
    return web.json_response(
        asdict(transport_response),
        status=_response_status(transport_response, success_status),
    )


def _transport_error(
    request: web.Request,
    *,
    code: str,
    message: str,
    status: int,
    details: dict[str, Any] | None = None,
) -> web.Response:
    response = ApiResponse(
        error=ApiError(code=code, message=message, details=details),
        request_id=_request_id(request),
        version=API_VERSION,
    )
    result = web.json_response(asdict(response), status=status)
    result.headers["X-Request-ID"] = response.request_id or ""
    result.headers["X-Printer-Control-Center-Version"] = STUDIO_VERSION
    return result


def _require_fields(payload: dict[str, Any], *field_names: str) -> None:
    missing = [
        field_name
        for field_name in field_names
        if field_name not in payload or payload[field_name] is None
    ]
    if missing:
        raise web.HTTPBadRequest(
            text=f"Missing required fields: {', '.join(missing)}"
        )


async def _read_json_object(
    request: web.Request,
    *,
    allow_empty: bool = False,
) -> dict[str, Any]:
    if allow_empty and request.content_length in (None, 0):
        return {}

    try:
        payload = await request.json()
    except (json.JSONDecodeError, ContentTypeError) as error:
        raise web.HTTPBadRequest(
            text=f"Request body must contain a valid JSON object: {error}"
        ) from error

    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Request body must be a JSON object")
    return payload


@web.middleware
async def api_error_middleware(
    request: web.Request,
    handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
) -> web.StreamResponse:
    request[REQUEST_ID_KEY] = uuid4().hex

    try:
        response = await handler(request)
    except web.HTTPRequestEntityTooLarge:
        return _transport_error(
            request,
            code="request_too_large",
            message="Request body exceeds the configured HTTP limit",
            status=413,
        )
    except web.HTTPMethodNotAllowed as error:
        return _transport_error(
            request,
            code="method_not_allowed",
            message=f"Method {request.method} is not allowed for this route",
            status=405,
            details={"allowed_methods": sorted(error.allowed_methods)},
        )
    except web.HTTPNotFound:
        return _transport_error(
            request,
            code="not_found",
            message=f"No API route matches {request.method} {request.path}",
            status=404,
        )
    except web.HTTPBadRequest as error:
        return _transport_error(
            request,
            code="validation_failed",
            message=error.text or "Invalid request",
            status=400,
        )
    except web.HTTPException as error:
        return _transport_error(
            request,
            code="internal_error" if error.status >= 500 else "validation_failed",
            message=error.reason,
            status=error.status,
        )
    except Exception:
        LOGGER.exception(
            "Unhandled standalone API error for %s %s",
            request.method,
            request.path,
        )
        return _transport_error(
            request,
            code="internal_error",
            message="The API request could not be completed",
            status=500,
        )

    response.headers["X-Request-ID"] = _request_id(request)
    response.headers["X-Printer-Control-Center-Version"] = STUDIO_VERSION
    return response


def _runtime(request: web.Request) -> StudioRuntime:
    return request.app[RUNTIME_KEY]


async def health(request: web.Request) -> web.Response:
    runtime = _runtime(request)
    actual_schema_version = schema_version(runtime.paths.database)
    ready = actual_schema_version == CURRENT_SCHEMA_VERSION
    status = 200 if ready else 503
    response = ApiResponse(
        data={
            "status": "ready" if ready else "degraded",
            "service": "ultimate-3d-printing-studio",
            "studio_version": STUDIO_VERSION,
            "api_version": API_VERSION,
            "api_base": API_BASE,
            "schema_version": actual_schema_version,
            "expected_schema_version": CURRENT_SCHEMA_VERSION,
            "runtime_root": str(runtime.paths.root),
        },
        request_id=_request_id(request),
        version=API_VERSION,
    )
    return web.json_response(asdict(response), status=status)


async def version(request: web.Request) -> web.Response:
    response = ApiResponse(
        data={
            "studio_version": STUDIO_VERSION,
            "api_version": API_VERSION,
            "api_base": API_BASE,
            "schema_version": CURRENT_SCHEMA_VERSION,
        },
        request_id=_request_id(request),
        version=API_VERSION,
    )
    return web.json_response(asdict(response), status=200)


async def create_upload(request: web.Request) -> web.Response:
    payload = await _read_json_object(request)
    _require_fields(
        payload,
        "original_name",
        "expected_size",
        "source_ui",
        "target",
    )
    response = _runtime(request).application.create_upload(payload)
    return _json_response(request, response, success_status=201)


async def write_upload_chunk(request: web.Request) -> web.Response:
    upload_id = request.match_info["upload_id"]
    raw_offset = request.query.get("offset", "0")
    try:
        offset = int(raw_offset)
    except ValueError as error:
        raise web.HTTPBadRequest(text="offset must be an integer") from error
    if offset < 0:
        raise web.HTTPBadRequest(text="offset must be greater than or equal to zero")

    chunk = await request.read()
    response = _runtime(request).application.write_upload_chunk(
        upload_id,
        offset,
        chunk,
    )
    return _json_response(request, response)


async def complete_upload(request: web.Request) -> web.Response:
    upload_id = request.match_info["upload_id"]
    response = _runtime(request).application.finalize_upload(upload_id)
    return _json_response(request, response)


async def search_gallery(request: web.Request) -> web.Response:
    query = request.query.get("q", "")
    raw_limit = request.query.get("limit", "100")
    try:
        limit = int(raw_limit)
    except ValueError as error:
        raise web.HTTPBadRequest(text="limit must be an integer") from error
    if limit < 1 or limit > 1000:
        raise web.HTTPBadRequest(text="limit must be between 1 and 1000")

    response = _runtime(request).application.search_gallery(query, limit)
    return _json_response(request, response)


async def create_project(request: web.Request) -> web.Response:
    payload = await _read_json_object(request)
    _require_fields(payload, "name")
    response = _runtime(request).application.create_project(payload)
    return _json_response(request, response, success_status=201)


async def get_project(request: web.Request) -> web.Response:
    project_id = request.match_info["project_id"]
    response = _runtime(request).application.get_project(project_id)
    return _json_response(request, response)


async def execute_project_command(request: web.Request) -> web.Response:
    project_id = request.match_info["project_id"]
    payload = await _read_json_object(request)
    response = _runtime(request).application.execute_scene_command(project_id, payload)
    return _json_response(request, response)


async def undo_project(request: web.Request) -> web.Response:
    project_id = request.match_info["project_id"]
    response = _runtime(request).application.undo_project(project_id)
    return _json_response(request, response)


async def redo_project(request: web.Request) -> web.Response:
    project_id = request.match_info["project_id"]
    response = _runtime(request).application.redo_project(project_id)
    return _json_response(request, response)


async def save_project(request: web.Request) -> web.Response:
    project_id = request.match_info["project_id"]
    response = _runtime(request).application.save_project(project_id)
    return _json_response(request, response)


async def restore_project(request: web.Request) -> web.Response:
    project_id = request.match_info["project_id"]
    payload = await _read_json_object(request, allow_empty=True)
    revision_value = payload.get("revision")
    if revision_value is None:
        revision = None
    else:
        try:
            revision = int(revision_value)
        except (TypeError, ValueError) as error:
            raise web.HTTPBadRequest(text="revision must be an integer") from error

    response = _runtime(request).application.restore_project_revision(
        project_id,
        revision,
    )
    return _json_response(request, response)


async def gallery_to_studio(request: web.Request) -> web.Response:
    asset_id = request.match_info["asset_id"]
    payload = await _read_json_object(request, allow_empty=True)
    project_id = payload.get("project_id")
    plate_id = payload.get("plate_id")
    response = _runtime(request).application.gallery_to_studio(
        asset_id,
        str(project_id) if project_id is not None else None,
        str(plate_id) if plate_id is not None else None,
    )
    return _json_response(request, response)


async def _close_runtime(application: web.Application) -> None:
    if application[CLOSE_RUNTIME_KEY]:
        application[RUNTIME_KEY].close()


def create_http_application(
    runtime: StudioRuntime,
    *,
    close_runtime: bool = False,
    client_max_size: int = 16 * 1024 * 1024,
) -> web.Application:
    application = web.Application(
        middlewares=[api_error_middleware],
        client_max_size=client_max_size,
    )
    application[RUNTIME_KEY] = runtime
    application[CLOSE_RUNTIME_KEY] = close_runtime

    system_base = ROUTES["system"]
    upload_base = ROUTES["uploads"]
    project_base = ROUTES["projects"]
    gallery_base = ROUTES["gallery"]

    application.router.add_get(f"{system_base}/health", health)
    application.router.add_get(f"{system_base}/version", version)

    application.router.add_post(upload_base, create_upload)
    application.router.add_post(
        f"{upload_base}/{{upload_id}}/chunks",
        write_upload_chunk,
    )
    application.router.add_post(
        f"{upload_base}/{{upload_id}}/complete",
        complete_upload,
    )

    application.router.add_get(gallery_base, search_gallery)
    application.router.add_post(
        f"{gallery_base}/{{asset_id}}/studio",
        gallery_to_studio,
    )

    application.router.add_post(project_base, create_project)
    application.router.add_get(f"{project_base}/{{project_id}}", get_project)
    application.router.add_post(
        f"{project_base}/{{project_id}}/commands",
        execute_project_command,
    )
    application.router.add_post(
        f"{project_base}/{{project_id}}/undo",
        undo_project,
    )
    application.router.add_post(
        f"{project_base}/{{project_id}}/redo",
        redo_project,
    )
    application.router.add_post(
        f"{project_base}/{{project_id}}/save",
        save_project,
    )
    application.router.add_post(
        f"{project_base}/{{project_id}}/restore",
        restore_project,
    )

    application.on_cleanup.append(_close_runtime)
    return application