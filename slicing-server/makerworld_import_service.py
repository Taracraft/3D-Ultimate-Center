"""MakerWorld import pipeline for Gallery, Studio and Slicer destinations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .archive_security import validate_archive
from .asset_service import AssetService
from .common import new_id, utc_now
from .file_formats import resolve_format
from .gallery_service import GalleryService
from .handoff import HandoffService
from .makerworld import MakerWorldDestination
from .makerworld_profiles import profile_snapshot, resolve_print_profile
from .makerworld_provider import MakerWorldProvider
from .makerworld_repository import MakerWorldRepository
from .profiles import ProfileSelection
from .slice_service import SliceService


@dataclass(slots=True, frozen=True)
class MakerWorldImportRequest:
    model_id_or_url: str
    destination: MakerWorldDestination
    profile_id: str | None = None
    license_acknowledged: bool = False
    project_id: str | None = None
    plate_id: str | None = None
    slicer_provider_id: str | None = None
    profile_selection: ProfileSelection = ProfileSelection()


class MakerWorldImportService:
    def __init__(
        self,
        *,
        provider: MakerWorldProvider,
        repository: MakerWorldRepository,
        assets: AssetService,
        gallery: GalleryService,
        handoffs: HandoffService,
        slicing: SliceService,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._assets = assets
        self._gallery = gallery
        self._handoffs = handoffs
        self._slicing = slicing

    async def search(self, query: str, cursor: str | None = None, limit: int = 24):
        result = await self._provider.search(query, cursor=cursor, limit=limit)
        fetched_at = utc_now()
        for model in result.items:
            self._repository.save_model(model, fetched_at)
        return result

    async def get_model(self, model_id_or_url: str):
        model = await self._provider.get_model(model_id_or_url)
        self._repository.save_model(model, utc_now())
        return model

    def get_asset_info(self, asset_id: str) -> dict | None:
        return self._repository.get_asset_info(asset_id)

    async def import_model(self, request: MakerWorldImportRequest) -> dict:
        import_id = new_id("makerworld_import")
        created_at = utc_now()
        model = await self.get_model(request.model_id_or_url)
        selected_profile = resolve_print_profile(
            model,
            request.profile_id,
            request.destination,
        )
        selected_profile_data = profile_snapshot(selected_profile)

        try:
            download = await self._provider.download(
                model.id,
                profile_id=request.profile_id,
                license_acknowledged=request.license_acknowledged,
            )
            if not download.license_acknowledged:
                raise ValueError("MakerWorld license must be acknowledged before import")

            source_path = Path(download.temporary_path)
            validate_archive(source_path)
            asset_format, asset_kind = resolve_format(download.filename)
            asset, duplicate = self._assets.register_file(
                source_path=source_path,
                original_name=download.filename,
                kind=asset_kind,
                format=asset_format,
            )

            result = self._route_destination(request, model, asset.id)
            self._repository.save_import(
                import_id=import_id,
                model_id=model.id,
                profile_id=request.profile_id,
                selected_profile=selected_profile_data,
                destination=request.destination.value,
                asset_id=asset.id,
                project_id=result.get("project_id"),
                slice_job_id=result.get("slice_job_id"),
                source_url=download.source_url,
                license_acknowledged=True,
                created_at=created_at,
            )
            return {
                "import_id": import_id,
                "model": asdict(model),
                "selected_profile": selected_profile_data,
                "asset": asdict(asset),
                "duplicate": duplicate,
                **result,
            }
        except Exception as error:
            self._repository.save_import(
                import_id=import_id,
                model_id=model.id,
                profile_id=request.profile_id,
                selected_profile=selected_profile_data,
                destination=request.destination.value,
                source_url=model.model_url,
                license_acknowledged=request.license_acknowledged,
                created_at=created_at,
                error_code=error.__class__.__name__,
                error_message=str(error),
            )
            raise

    def _route_destination(self, request, model, asset_id: str) -> dict:
        if request.destination == MakerWorldDestination.GALLERY:
            item = self._gallery.add_asset(
                asset_id=asset_id,
                title=model.title,
                description=model.description,
                tags=model.tags,
            )
            return {
                "gallery_item": asdict(item),
                "project_id": None,
                "slice_job_id": None,
            }

        session, handoff = self._handoffs.gallery_asset_to_project(
            asset_id,
            request.project_id,
            request.plate_id,
        )
        if request.destination == MakerWorldDestination.STUDIO:
            return {
                "project_id": session.project.id,
                "slice_job_id": None,
                "project": asdict(session.project),
                "handoff": asdict(handoff),
            }

        if not request.slicer_provider_id:
            raise ValueError("slicer_provider_id is required for Slicer destination")
        plate_id = request.plate_id or session.project.plates[0].id
        job = self._slicing.create_job(
            project_id=session.project.id,
            plate_id=plate_id,
            provider_id=request.slicer_provider_id,
            profile_selection=request.profile_selection,
        )
        return {
            "project_id": session.project.id,
            "slice_job_id": job.id,
            "project": asdict(session.project),
            "slice_job": asdict(job),
            "handoff": asdict(handoff),
        }