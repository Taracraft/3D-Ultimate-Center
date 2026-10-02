"""Framework-neutral slicing API facade."""

from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from core.profiles import ProfileSelection
from core.slice_service import SliceService

from .contracts import ApiError, ApiResponse


class V1SlicingApplication:
    def __init__(self, slicing: SliceService) -> None:
        self._slicing = slicing

    def create_job(self, payload: dict) -> ApiResponse:
        def action() -> dict:
            profiles = payload.get("profiles") or {}
            selection = ProfileSelection(
                printer_profile_id=profiles.get("printer"),
                nozzle_profile_id=profiles.get("nozzle"),
                process_profile_id=profiles.get("process"),
                build_plate_profile_id=profiles.get("build_plate"),
                filament_profile_ids=tuple(profiles.get("filaments", ())),
            )
            job = self._slicing.create_job(
                project_id=str(payload["project_id"]),
                plate_id=str(payload["plate_id"]),
                provider_id=str(payload["provider_id"]),
                profile_selection=selection,
            )
            return asdict(job)

        return self._guard(action)

    def get_job(self, job_id: str) -> ApiResponse:
        return self._guard(lambda: asdict(self._slicing.get(job_id)))

    async def run_job(self, job_id: str) -> ApiResponse:
        return await self._guard_async(lambda: self._slicing.run(job_id))

    async def cancel_job(self, job_id: str) -> ApiResponse:
        return await self._guard_async(lambda: self._slicing.cancel(job_id))

    def _guard(self, action) -> ApiResponse:
        request_id = uuid4().hex
        try:
            return ApiResponse(data=action(), request_id=request_id)
        except KeyError as error:
            return ApiResponse(
                error=ApiError("not_found", str(error)),
                request_id=request_id,
            )
        except ValueError as error:
            return ApiResponse(
                error=ApiError("validation_failed", str(error)),
                request_id=request_id,
            )
        except Exception as error:
            return ApiResponse(
                error=ApiError("internal_error", str(error)),
                request_id=request_id,
            )

    async def _guard_async(self, action) -> ApiResponse:
        request_id = uuid4().hex
        try:
            job = await action()
            return ApiResponse(data=asdict(job), request_id=request_id)
        except KeyError as error:
            return ApiResponse(
                error=ApiError("not_found", str(error)),
                request_id=request_id,
            )
        except ValueError as error:
            return ApiResponse(
                error=ApiError("validation_failed", str(error)),
                request_id=request_id,
            )
        except Exception as error:
            return ApiResponse(
                error=ApiError("internal_error", str(error)),
                request_id=request_id,
            )