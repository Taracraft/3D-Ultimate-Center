"""Framework-neutral MakerWorld API facade."""

from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from core.makerworld import MakerWorldDestination
from core.makerworld_import_service import MakerWorldImportRequest, MakerWorldImportService
from core.profiles import ProfileSelection

from .contracts import ApiError, ApiResponse


class V1MakerWorldApplication:
    def __init__(self, service: MakerWorldImportService) -> None:
        self._service = service

    async def search(self, query: str, cursor: str | None = None, limit: int = 24) -> ApiResponse:
        return await self._guard_async(lambda: self._search_data(query, cursor, limit))

    async def get_model(self, model_id_or_url: str) -> ApiResponse:
        return await self._guard_async(lambda: self._model_data(model_id_or_url))

    def get_asset_info(self, asset_id: str) -> ApiResponse:
        request_id = uuid4().hex
        try:
            info = self._service.get_asset_info(asset_id)
            if info is None:
                return ApiResponse(
                    error=ApiError("not_found", "asset has no MakerWorld provenance"),
                    request_id=request_id,
                )
            return ApiResponse(data=info, request_id=request_id)
        except Exception as error:
            return ApiResponse(
                error=ApiError("internal_error", str(error)),
                request_id=request_id,
            )

    async def import_model(self, payload: dict) -> ApiResponse:
        profiles = payload.get("profiles") or {}
        request = MakerWorldImportRequest(
            model_id_or_url=str(payload["model_id_or_url"]),
            destination=MakerWorldDestination(str(payload["destination"])),
            profile_id=payload.get("profile_id"),
            license_acknowledged=bool(payload.get("license_acknowledged", False)),
            project_id=payload.get("project_id"),
            plate_id=payload.get("plate_id"),
            slicer_provider_id=payload.get("slicer_provider_id"),
            profile_selection=ProfileSelection(
                printer_profile_id=profiles.get("printer"),
                nozzle_profile_id=profiles.get("nozzle"),
                process_profile_id=profiles.get("process"),
                build_plate_profile_id=profiles.get("build_plate"),
                filament_profile_ids=tuple(profiles.get("filaments", ())),
            ),
        )
        return await self._guard_async(lambda: self._service.import_model(request))

    async def _search_data(self, query: str, cursor: str | None, limit: int) -> dict:
        result = await self._service.search(query, cursor, limit)
        return asdict(result)

    async def _model_data(self, model_id_or_url: str) -> dict:
        model = await self._service.get_model(model_id_or_url)
        return asdict(model)

    async def _guard_async(self, action) -> ApiResponse:
        request_id = uuid4().hex
        try:
            return ApiResponse(data=await action(), request_id=request_id)
        except KeyError as error:
            return ApiResponse(error=ApiError("not_found", str(error)), request_id=request_id)
        except ValueError as error:
            return ApiResponse(error=ApiError("validation_failed", str(error)), request_id=request_id)
        except Exception as error:
            return ApiResponse(error=ApiError("internal_error", str(error)), request_id=request_id)