"""Reusable test doubles for V6 provider boundaries."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from core.makerworld import (
    MakerWorldCreator,
    MakerWorldDownload,
    MakerWorldModel,
    MakerWorldPrintProfile,
    MakerWorldSearchResult,
)
from core.preview_jobs import PreviewJobRecord
from core.providers import ProviderCapabilities, ProviderHealth
from core.slicing import SliceJobRecord, SliceJobStatus


class FakeMakerWorldProvider:
    def __init__(self, download_file: Path) -> None:
        self.download_file = download_file
        self.model = MakerWorldModel(
            id="mw_test_model",
            title="MakerWorld Test Model",
            model_url="https://makerworld.example/models/mw_test_model",
            description="End-to-end test model",
            creator=MakerWorldCreator(
                id="creator_test",
                name="Test Creator",
                profile_url="https://makerworld.example/@creator_test",
            ),
            license_name="CC BY 4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            thumbnail_url="https://makerworld.example/thumb.png",
            downloads=100,
            likes=25,
            tags=("test", "calibration"),
            print_profiles=(
                MakerWorldPrintProfile(
                    id="mw_profile_04",
                    name="0.20 mm Standard",
                    printer_model="X1 Carbon",
                    nozzle_diameter=0.4,
                    plate_count=1,
                    filament_count=1,
                    thumbnail_url=None,
                ),
            ),
        )

    async def search(
        self,
        query: str,
        *,
        cursor: str | None = None,
        limit: int = 24,
    ) -> MakerWorldSearchResult:
        items = (self.model,) if query.casefold() in self.model.title.casefold() else ()
        return MakerWorldSearchResult(items=items[:limit], next_cursor=None)

    async def get_model(self, model_id_or_url: str) -> MakerWorldModel:
        if model_id_or_url not in {self.model.id, self.model.model_url}:
            raise KeyError(model_id_or_url)
        return self.model

    async def download(
        self,
        model_id: str,
        *,
        profile_id: str | None,
        license_acknowledged: bool,
    ) -> MakerWorldDownload:
        if model_id != self.model.id:
            raise KeyError(model_id)
        if profile_id not in {None, "mw_profile_04"}:
            raise KeyError(profile_id)
        return MakerWorldDownload(
            model=self.model,
            profile_id=profile_id,
            filename=self.download_file.name,
            content_type="model/stl",
            temporary_path=str(self.download_file),
            source_url=self.model.model_url,
            license_acknowledged=license_acknowledged,
        )


class FakeSlicerProvider:
    async def health(self) -> ProviderHealth:
        return ProviderHealth(provider_id="fake_slicer", available=True)

    async def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id="fake_slicer",
            input_formats=("stl", "3mf"),
            output_formats=("gcode",),
            supports_cancel=True,
            supports_layer_preview=True,
            max_parallel_jobs=1,
        )

    async def submit(self, job: SliceJobRecord) -> SliceJobRecord:
        return replace(job, status=SliceJobStatus.SUCCEEDED, progress=100.0)

    async def inspect(self, job_id: str) -> SliceJobRecord:
        raise NotImplementedError

    async def cancel(self, job_id: str) -> None:
        return None


class FakePreviewRenderer:
    async def render(self, asset_id: str, job_id: str) -> str:
        return f"preview_for_{asset_id}"
