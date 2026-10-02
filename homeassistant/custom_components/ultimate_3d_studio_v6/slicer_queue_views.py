"""Authenticated V6 slicer queue endpoints."""
from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import API_BASE, VERSION
from .slicer_backend_router import V6SlicerBackendRouter
from .slicer_native_contract import (
    SlicerServerConfigurationError,
    SlicerServerError,
)
from .slicer_job_list_client import async_list_slicer_jobs


class SlicerQueueStatusView(HomeAssistantView):
    """Return queue status summary."""

    url = f"{API_BASE}/slicer/queue/status"
    name = "api:ultimate_3d_studio_v6:slicer:queue:status"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            items = await async_list_slicer_jobs(hass)
        except SlicerServerConfigurationError as exc:
            return web.json_response({
                "data": None,
                "error": {"code": "slicing_server_not_configured", "message": str(exc)},
                "meta": {"api_version": "v1", "component_version": VERSION},
            }, status=503)
        except SlicerServerError as exc:
            return web.json_response({
                "data": None,
                "error": {"code": "slicer_queue_status_failed", "message": str(exc)},
                "meta": {"api_version": "v1", "component_version": VERSION},
            }, status=502)

        queued = sum(1 for j in items if j.get("status") == "queued")
        running = sum(1 for j in items if j.get("status") == "running")
        completed = sum(1 for j in items if j.get("status") == "succeeded")
        failed = sum(1 for j in items if j.get("status") in ("failed", "cancelled", "interrupted"))

        return web.json_response({
            "data": {
                "total_jobs": len(items),
                "queued_jobs": queued,
                "running_jobs": running,
                "completed_jobs": completed,
                "failed_jobs": failed,
            },
            "error": None,
            "meta": {"api_version": "v1", "component_version": VERSION},
        })


class SlicerBatchCreateView(HomeAssistantView):
    """Handle batch job creation from uploaded files."""

    url = f"{API_BASE}/slicer/jobs/batch"
    name = "api:ultimate_3d_studio_v6:slicer:jobs:batch"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        try:
            reader = await request.multipart()
            files = []
            plate_index = 0
            auto_release = False

            while True:
                part = await reader.next()
                if part is None:
                    break
                if part.name and part.name.startswith("files_"):
                    content = await part.read()
                    if content:
                        files.append((part.filename or "model", content))
                elif part.name == "plate_index":
                    plate_index = int(await part.text())
                elif part.name == "auto_release":
                    auto_release = await part.text() == "true"

            if not files:
                return web.json_response(
                    {"error": "No files provided"},
                    status=400,
                )

            result = await self._process_batch(request.app["hass"], files, plate_index, auto_release)
            return web.json_response({"data": result})

        except Exception as exc:
            return web.json_response(
                {"error": str(exc)},
                status=500,
            )

    async def _process_batch(
        self,
        hass: HomeAssistant,
        files: list[tuple[str, bytes]],
        plate_index: int,
        auto_release: bool,
    ) -> dict[str, Any]:
        router = V6SlicerBackendRouter(hass)
        created = 0
        failed = 0
        jobs = []
        errors = []

        for filename, content in files:
            tmp_path = None
            try:
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=Path(filename).suffix)
                with os.fdopen(tmp_fd, "wb") as tmp:
                    tmp.write(content)

                job = await router.async_create_plate_job(
                    backend="server",
                    filename=filename,
                    model=content,
                    _catalog={},
                    _plate_index=plate_index,
                )
                if auto_release and job.get("status") == "queued":
                    await router.async_release_job(job["id"])
                created += 1
                jobs.append(job)

            except Exception as exc:
                failed += 1
                errors.append(f"{filename}: {str(exc)}")
            finally:
                if tmp_path:
                    Path(tmp_path).unlink(missing_ok=True)

        return {
            "created": created,
            "failed": failed,
            "jobs": jobs,
            "errors": errors,
        }


class SlicerReleaseJobView(HomeAssistantView):
    """Release a single queued job."""

    url = f"{API_BASE}/slicer/jobs/{{job_id}}/release"
    name = "api:ultimate_3d_studio_v6:slicer:job:release"
    requires_auth = True

    async def post(self, request: web.Request, job_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        router = V6SlicerBackendRouter(hass)
        try:
            await router.async_release_job(job_id)
            return web.json_response({"data": {"released": True}})
        except SlicerServerError as exc:
            return web.json_response(
                {"error": str(exc)},
                status=400,
            )


class SlicerReleaseAllView(HomeAssistantView):
    """Release all queued jobs."""

    url = f"{API_BASE}/slicer/jobs/release-all"
    name = "api:ultimate_3d_studio_v6:slicer:release:all"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        router = V6SlicerBackendRouter(hass)
        released = 0
        try:
            items = await async_list_slicer_jobs(hass)
            for job in items:
                if job.get("status") == "queued":
                    try:
                        await router.async_release_job(job["id"])
                        released += 1
                    except SlicerServerError:
                        pass
        except SlicerServerConfigurationError:
            return web.json_response({
                "data": {"released": 0},
                "error": None,
                "meta": {"api_version": "v1", "component_version": VERSION},
            })

        return web.json_response({"data": {"released": released}})


def async_register_slicer_queue_views(hass: HomeAssistant) -> None:
    """Register queue-related API views."""
    hass.http.register_view(SlicerQueueStatusView())
    hass.http.register_view(SlicerBatchCreateView())
    hass.http.register_view(SlicerReleaseJobView())
    hass.http.register_view(SlicerReleaseAllView())