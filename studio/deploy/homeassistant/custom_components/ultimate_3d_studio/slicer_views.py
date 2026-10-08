"""Authenticated geometry, plans and native slicing-server endpoints."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .profile_runtime import get_profile_runtime
from .request_body import RequestBodyTooLarge, async_read_limited_body
from .slicer_runtime import SlicerRuntimeError, get_slicer_runtime
from .slicer_backend_router import StudioSlicerBackendRouter, normalize_backend
from .slicer_native_contract import (
    MAX_MODEL_BYTES,
    SlicerServerConfigurationError,
    SlicerServerError,
)

API_PREFIX = "/api/ultimate_3d_studio/v1/slicer"
MAX_GEOMETRY_BYTES = 160_000_000
_ALLOWED_GEOMETRY_SUFFIXES = {".stl", ".3mf"}


def _safe_filename(value: str, fallback: str) -> str:
    raw = Path(value or fallback).name.strip()
    cleaned = "".join(
        character if character.isalnum() or character in "-_. " else "_"
        for character in raw
    ).strip(" .")
    return (cleaned or fallback)[:180]


def _server_error_response(exc: Exception) -> web.Response:
    status = 503 if isinstance(exc, SlicerServerConfigurationError) else 502
    return web.json_response({"error": str(exc)}, status=status)


class SlicerProviderView(HomeAssistantView):
    """Describe the native Studio slicing server and its live readiness."""

    url = f"{API_PREFIX}/provider"
    name = "api:ultimate_3d_studio:slicer_provider"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        try:
            backend = normalize_backend(request.query.get("backend"))
            provider = await StudioSlicerBackendRouter(
                request.app["hass"]
            ).async_provider(backend)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except (
            SlicerServerConfigurationError,
            SlicerServerError,
        ) as exc:
            return _server_error_response(exc)
        return web.json_response({"data": provider})


class SlicerGeometryView(HomeAssistantView):
    """Store transformed STL/3MF geometry for a persistent slice plan."""

    url = f"{API_PREFIX}/geometry"
    name = "api:ultimate_3d_studio:slicer_geometry"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        runtime = get_slicer_runtime(request.app["hass"])
        filename = request.query.get("filename", "scene.stl")
        try:
            geometry = await async_read_limited_body(request, MAX_GEOMETRY_BYTES)
        except RequestBodyTooLarge:
            return web.json_response({"error": "geometry exceeds 160 MB"}, status=413)
        if not geometry:
            return web.json_response({"error": "geometry body is empty"}, status=400)
        try:
            stored = await runtime.async_store_geometry(filename, geometry)
        except SlicerRuntimeError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        return web.json_response({
            "data": {
                "geometry_id": stored["geometry_id"],
                "filename": stored["filename"],
                "size_bytes": stored["size_bytes"],
                "sha256": sha256(geometry).hexdigest(),
            },
        }, status=201)


class SlicerPlansView(HomeAssistantView):
    """List or create persistent Studio slice plans."""

    url = f"{API_PREFIX}/plans"
    name = "api:ultimate_3d_studio:slicer_plans"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        runtime = get_slicer_runtime(request.app["hass"])
        return web.json_response({"data": await runtime.async_list_plans()})

    async def post(self, request: web.Request) -> web.Response:
        runtime = get_slicer_runtime(request.app["hass"])
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "request body must be JSON"}, status=400)
        if not isinstance(payload, dict):
            return web.json_response({"error": "request body must be an object"}, status=400)
        try:
            plan = await runtime.async_create_plan(payload)
        except SlicerRuntimeError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        return web.json_response({"data": plan}, status=201)


class SlicerPlanView(HomeAssistantView):
    """Read or remove one slice plan."""

    url = f"{API_PREFIX}/plans/{{plan_id}}"
    name = "api:ultimate_3d_studio:slicer_plan"
    requires_auth = True

    async def get(self, request: web.Request, plan_id: str) -> web.Response:
        runtime = get_slicer_runtime(request.app["hass"])
        plan = await runtime.async_get_plan(plan_id)
        if plan is None:
            return web.json_response({"error": "slice plan not found"}, status=404)
        return web.json_response({"data": plan})

    async def delete(self, request: web.Request, plan_id: str) -> web.Response:
        runtime = get_slicer_runtime(request.app["hass"])
        removed = await runtime.async_delete_plan(plan_id)
        if not removed:
            return web.json_response({"error": "slice plan not found"}, status=404)
        return web.json_response({"data": {"deleted": True, "id": plan_id}})


class SlicerJobsView(HomeAssistantView):
    """Create one real G-code job from the current trusted Studio profile selection."""

    url = f"{API_PREFIX}/jobs"
    name = "api:ultimate_3d_studio:slicer_jobs"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        filename = _safe_filename(request.query.get("filename", "scene.stl"), "scene.stl")
        if Path(filename).suffix.casefold() not in _ALLOWED_GEOMETRY_SUFFIXES:
            return web.json_response({"error": "only STL or 3MF models are supported"}, status=400)
        try:
            model = await async_read_limited_body(request, MAX_MODEL_BYTES)
        except RequestBodyTooLarge:
            return web.json_response({"error": "model exceeds 300 MB"}, status=413)
        if not model:
            return web.json_response({"error": "model body is empty"}, status=400)
        hass: HomeAssistant = request.app["hass"]
        catalog = await get_profile_runtime(hass).async_catalog()
        try:
            backend = normalize_backend(request.query.get("backend"))
            job = await StudioSlicerBackendRouter(hass).async_create_plate_job(
                backend, filename, model, catalog, 0
            )
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except (SlicerServerConfigurationError, SlicerServerError) as exc:
            return _server_error_response(exc)
        return web.json_response({"data": job}, status=202)


class SlicerJobView(HomeAssistantView):
    """Return the live state and slicing metrics of one native server job."""

    url = f"{API_PREFIX}/jobs/{{job_id}}"
    name = "api:ultimate_3d_studio:slicer_job"
    requires_auth = True

    async def get(self, request: web.Request, job_id: str) -> web.Response:
        try:
            job = await StudioSlicerBackendRouter(request.app["hass"]).async_get_job(job_id)
        except (SlicerServerConfigurationError, SlicerServerError) as exc:
            return _server_error_response(exc)
        return web.json_response({"data": job})


class SlicerJobArtifactView(HomeAssistantView):
    """Proxy one verified G-code 3MF artifact without exposing the server internals."""

    url = f"{API_PREFIX}/jobs/{{job_id}}/artifact"
    name = "api:ultimate_3d_studio:slicer_job_artifact"
    requires_auth = True

    async def get(self, request: web.Request, job_id: str) -> web.Response:
        try:
            data, filename, digest, content_type = await StudioSlicerBackendRouter(
                request.app["hass"]
            ).async_artifact(job_id)
        except (SlicerServerConfigurationError, SlicerServerError) as exc:
            return _server_error_response(exc)
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        }
        if digest:
            headers["X-Content-SHA256"] = digest
        return web.Response(body=data, content_type=content_type, headers=headers)


def async_register_slicer_views(hass: HomeAssistant) -> None:
    """Register the provider, persistent plan and native server routes."""
    for view in (
        SlicerProviderView(),
        SlicerGeometryView(),
        SlicerPlansView(),
        SlicerPlanView(),
        SlicerJobsView(),
        SlicerJobView(),
        SlicerJobArtifactView(),
    ):
        hass.http.register_view(view)
