"""Authenticated HTTP views for 3D Ultimate Studio projects and revisions."""
from __future__ import annotations

from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .studio_project_repository import (
    ProjectConflictError,
    ProjectValidationError,
    get_studio_project_repository,
)

API_PREFIX = "/api/ultimate_3d_studio_v6/v1/studio/projects"


def _success(data: Any, **meta: Any) -> web.Response:
    return web.json_response({"data": data, "error": None, "meta": meta})


def _error(status: int, code: str, message: str, **details: Any) -> web.Response:
    return web.json_response(
        {"data": None, "error": {"code": code, "message": message, **details}},
        status=status,
    )


def _admin_error(request: web.Request) -> web.Response | None:
    user = request.get("hass_user")
    if user is None or not user.is_admin:
        return _error(403, "admin_required", "Administrator access is required")
    return None


async def _json(request: web.Request) -> tuple[dict[str, Any] | None, web.Response | None]:
    try:
        payload = await request.json()
    except Exception:
        return None, _error(400, "invalid_json", "Valid JSON is required")
    if not isinstance(payload, dict):
        return None, _error(400, "invalid_payload", "A JSON object is required")
    return payload, None


def _revision(payload: dict[str, Any], key: str = "expected_revision") -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProjectValidationError(f"{key} must be a positive integer")
    return value


def _project_data(project: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in project.items() if key != "revisions"}


class StudioProjectsView(HomeAssistantView):
    url = API_PREFIX
    name = "api:ultimate_3d_studio_v6:studio_projects"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        items = await get_studio_project_repository(request.app["hass"]).async_list()
        return _success({"items": items}, count=len(items), persistent=True)

    async def post(self, request: web.Request) -> web.Response:
        if (error := _admin_error(request)) is not None:
            return error
        payload, error = await _json(request)
        if error is not None:
            return error
        assert payload is not None
        try:
            project = await get_studio_project_repository(
                request.app["hass"]
            ).async_create(payload.get("name"), payload.get("snapshot"))
        except ProjectValidationError as exc:
            return _error(400, "invalid_project", str(exc))
        return _success(_project_data(project), created=True)


class StudioProjectView(HomeAssistantView):
    url = API_PREFIX + "/{project_id}"
    name = "api:ultimate_3d_studio_v6:studio_project"
    requires_auth = True

    async def get(self, request: web.Request, project_id: str) -> web.Response:
        project = await get_studio_project_repository(
            request.app["hass"]
        ).async_get(project_id)
        if project is None:
            return _error(404, "project_not_found", "Project was not found")
        return _success(_project_data(project))

    async def post(self, request: web.Request, project_id: str) -> web.Response:
        if (error := _admin_error(request)) is not None:
            return error
        payload, error = await _json(request)
        if error is not None:
            return error
        assert payload is not None
        try:
            project = await get_studio_project_repository(
                request.app["hass"]
            ).async_save_project(
                project_id,
                name=payload.get("name"),
                snapshot=payload.get("snapshot"),
                expected_revision=_revision(payload),
            )
        except ProjectConflictError as exc:
            current = await get_studio_project_repository(
                request.app["hass"]
            ).async_get(project_id)
            return _error(
                409,
                "revision_conflict",
                str(exc),
                current_revision=int(current.get("revision", 0)) if current else None,
            )
        except ProjectValidationError as exc:
            return _error(400, "invalid_project", str(exc))
        if project is None:
            return _error(404, "project_not_found", "Project was not found")
        return _success(_project_data(project), saved=True)

    async def delete(self, request: web.Request, project_id: str) -> web.Response:
        if (error := _admin_error(request)) is not None:
            return error
        payload, error = await _json(request)
        if error is not None:
            return error
        assert payload is not None
        try:
            removed = await get_studio_project_repository(
                request.app["hass"]
            ).async_delete(project_id, expected_revision=_revision(payload))
        except ProjectConflictError as exc:
            return _error(409, "revision_conflict", str(exc))
        except ProjectValidationError as exc:
            return _error(400, "invalid_project", str(exc))
        if not removed:
            return _error(404, "project_not_found", "Project was not found")
        return _success({"id": project_id}, deleted=True)


class StudioProjectRevisionsView(HomeAssistantView):
    url = API_PREFIX + "/{project_id}/revisions"
    name = "api:ultimate_3d_studio_v6:studio_project_revisions"
    requires_auth = True

    async def get(self, request: web.Request, project_id: str) -> web.Response:
        items = await get_studio_project_repository(
            request.app["hass"]
        ).async_revisions(project_id)
        if items is None:
            return _error(404, "project_not_found", "Project was not found")
        return _success({"items": items}, count=len(items))


class StudioProjectRestoreView(HomeAssistantView):
    url = API_PREFIX + "/{project_id}/restore"
    name = "api:ultimate_3d_studio_v6:studio_project_restore"
    requires_auth = True

    async def post(self, request: web.Request, project_id: str) -> web.Response:
        if (error := _admin_error(request)) is not None:
            return error
        payload, error = await _json(request)
        if error is not None:
            return error
        assert payload is not None
        try:
            project = await get_studio_project_repository(
                request.app["hass"]
            ).async_restore(
                project_id,
                source_revision=_revision(payload, "source_revision"),
                expected_revision=_revision(payload),
            )
        except ProjectConflictError as exc:
            return _error(409, "revision_conflict", str(exc))
        except ProjectValidationError as exc:
            return _error(400, "invalid_project", str(exc))
        if project is None:
            return _error(404, "project_not_found", "Project was not found")
        return _success(_project_data(project), restored=True)


def async_register_studio_project_views(hass: HomeAssistant) -> None:
    hass.http.register_view(StudioProjectsView())
    hass.http.register_view(StudioProjectView())
    hass.http.register_view(StudioProjectRevisionsView())
    hass.http.register_view(StudioProjectRestoreView())