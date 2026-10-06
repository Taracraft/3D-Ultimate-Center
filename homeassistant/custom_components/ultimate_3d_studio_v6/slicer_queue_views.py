"""Authenticated V6 slicer queue endpoints."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import API_BASE, VERSION
from .slicer_backend_router import V6SlicerBackendRouter
from .slicer_plate_views_v2 import (
    _batch_material_plan_for_model,
    _prepare_plate_job_contract,
)
from .slicer_native_contract import (
    SlicerServerConfigurationError,
    SlicerServerError,
)
from .slicer_job_list_client import async_list_slicer_jobs
from .slicer_backend_router import SlicerCancellationError


MAX_BATCH_BYTES = 160_000_000


class BatchBodyTooLarge(ValueError):
    pass


async def _read_batch_part(part: Any, limit: int) -> bytes:
    content = bytearray()
    while True:
        chunk = await part.read_chunk(size=64 * 1024)
        if not chunk:
            return bytes(content)
        if len(content) + len(chunk) > limit:
            raise BatchBodyTooLarge("batch_payload_too_large")
        content.extend(chunk)


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
        running = sum(1 for j in items if j.get("status") in {"running", "cancelling"})
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
            files: list[tuple[str, bytes]] = []
            total_bytes = 0
            file_parts = 0
            plate_index = 0
            auto_release = False
            auto_release_seen = False
            studio_plate: dict[str, Any] | None = None
            material_plan: dict[str, Any] | None = None
            process_overrides: dict[str, Any] = {}

            while True:
                part = await reader.next()
                if part is None:
                    break
                if part.name and part.name.startswith("files_"):
                    file_parts += 1
                    if file_parts > 50:
                        return web.json_response({"error": "batch_limit_exceeded", "max_files": 50}, status=413)
                    content = await _read_batch_part(part, MAX_BATCH_BYTES - total_bytes)
                    total_bytes += len(content)
                    if content:
                        files.append((part.filename or "model.3mf", content))
                elif part.name == "plate_index":
                    plate_index = int((await _read_batch_part(part, 128)).decode("utf-8"))
                elif part.name == "auto_release":
                    value = (await _read_batch_part(part, 128)).decode("utf-8").strip().casefold()
                    if value not in {"true", "false"}:
                        return web.json_response({"error": "invalid_auto_release"}, status=400)
                    auto_release = value == "true"
                    auto_release_seen = True
                elif part.name in {"studio_plate", "material_plan", "process_overrides"}:
                    raw = (await _read_batch_part(part, 1_000_000)).decode("utf-8")
                    if len(raw) > 1_000_000:
                        return web.json_response({"error": f"{part.name}_too_large"}, status=413)
                    try:
                        decoded = json.loads(raw)
                    except json.JSONDecodeError:
                        return web.json_response({"error": f"invalid_{part.name}_json"}, status=400)
                    if not isinstance(decoded, dict):
                        return web.json_response({"error": f"invalid_{part.name}"}, status=400)
                    if part.name == "studio_plate":
                        studio_plate = decoded
                    elif part.name == "material_plan":
                        material_plan = decoded
                    else:
                        process_overrides = decoded

            if not files:
                return web.json_response({"error": "No files provided"}, status=400)
            if len(files) > 50:
                return web.json_response({"error": "batch_limit_exceeded", "max_files": 50}, status=413)
            if not 0 <= plate_index <= 255:
                return web.json_response({"error": "plate_index_out_of_range"}, status=400)
            if studio_plate is None or material_plan is None:
                return web.json_response({
                    "error": "batch_profile_contract_required",
                    "message": "Bitte im Studio zuerst Drucker, Profile und Materialquelle auswählen.",
                }, status=422)
            if not auto_release_seen:
                auto_release = False

            invalid_names = [name for name, _ in files if Path(name).suffix.casefold() != ".3mf"]
            if invalid_names:
                return web.json_response({
                    "error": "batch_requires_3mf",
                    "files": invalid_names[:10],
                    "message": "Die Warteschlange benötigt 3MF-Projekte mit Objekt- und Materialinformationen.",
                }, status=415)

            hass: HomeAssistant = request.app["hass"]
            prepared: list[tuple[str, bytes, dict[str, Any]]] = []
            # Validate the whole batch before any file is uploaded or any job is created.
            for filename, content in files:
                per_file_plate = {
                    **studio_plate,
                    "project_name": Path(filename).stem,
                }
                per_file_material_plan = _batch_material_plan_for_model(
                    material_plan,
                    content,
                )
                contract = await _prepare_plate_job_contract(
                    hass,
                    filename,
                    content,
                    plate_index,
                    dict(process_overrides),
                    per_file_material_plan,
                    per_file_plate,
                )
                prepared.append((filename, content, contract))

            router = V6SlicerBackendRouter(hass)
            jobs = []
            errors = []
            for filename, content, contract in prepared:
                try:
                    job = await router.async_create_plate_job(
                        "server",
                        filename,
                        content,
                        contract["catalog"],
                        plate_index,
                        contract["options"],
                        target_printer=contract["target_printer"],
                        material_plan=contract["material_plan"],
                        selected_process_profile=contract["selected_process_profile"],
                        source_project_name=contract["project_name"],
                        manual_release=not auto_release,
                    )
                    resolved_plan = contract["material_plan"]
                    material_summary = contract["material_source_summary"]
                    job["material_plan"] = {
                        "applied": False,
                        "handled_by_native_server": True,
                        "assignment_count": len(resolved_plan["assignments"]),
                        "material_channel_count": len(resolved_plan["filaments"]),
                    }
                    job["material_source_plan"] = material_summary
                    job["compatibility_contract"] = contract["compatibility_contract"]
                    job["target_printer"] = contract["target_printer"]
                    job["selected_backend"] = "server"
                    jobs.append(job)
                except (SlicerServerConfigurationError, SlicerServerError, ValueError) as exc:
                    errors.append(f"{filename}: {exc}")
            return web.json_response({"data": {
                "created": len(jobs),
                "failed": len(errors),
                "jobs": jobs,
                "errors": errors,
            }})
        except BatchBodyTooLarge as exc:
            return web.json_response({"error": str(exc), "max_bytes": MAX_BATCH_BYTES}, status=413)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except SlicerServerConfigurationError as exc:
            return web.json_response({"error": str(exc)}, status=503)
        except SlicerServerError as exc:
            return web.json_response({"error": str(exc)}, status=502)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)


class SlicerCancelJobView(HomeAssistantView):
    """Authenticated cooperative cancellation; no printer or kill command is exposed."""
    url = f"{API_BASE}/slicer/jobs/{{job_id}}/cancel"
    name = "api:ultimate_3d_studio_v6:slicer:job:cancel"
    requires_auth = True

    async def post(self, request: web.Request, job_id: str) -> web.Response:
        try:
            result = await V6SlicerBackendRouter(request.app["hass"]).async_cancel_job(job_id)
            return web.json_response({"data": result})
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except SlicerCancellationError as exc:
            return web.json_response({"error": {"code": str(exc), "message": str(exc)}}, status=exc.status)


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
    hass.http.register_view(SlicerCancelJobView())
    hass.http.register_view(SlicerReleaseJobView())
    hass.http.register_view(SlicerReleaseAllView())
