"""Register slicer output files as immutable Studio assets and job artifacts."""

from __future__ import annotations

from pathlib import Path

from .asset_service import AssetService
from .assets import AssetFormat, AssetKind
from .common import new_id, utc_now
from .gcode_service import GCodeService
from .slice_artifacts import SliceArtifactKind, SliceArtifactRecord
from .slice_service import SliceService


class SliceArtifactService:
    def __init__(
        self,
        assets: AssetService,
        slicing: SliceService,
        gcode: GCodeService,
    ) -> None:
        self._assets = assets
        self._slicing = slicing
        self._gcode = gcode

    def register_file(
        self,
        *,
        job_id: str,
        source_path: str | Path,
        original_name: str,
        kind: SliceArtifactKind,
    ):
        asset_format = self._format_for_kind(kind, original_name)
        asset, duplicate = self._assets.register_file(
            source_path=source_path,
            original_name=original_name,
            kind=AssetKind.SLICE_ARTIFACT,
            format=asset_format,
        )
        artifact = SliceArtifactRecord(
            id=new_id("artifact"),
            slice_job_id=job_id,
            asset_id=asset.id,
            kind=kind,
            created_at=utc_now(),
        )
        job = self._slicing.attach_artifact(artifact)
        metadata = None
        if asset_format in {AssetFormat.GCODE, AssetFormat.BGCODE}:
            metadata = self._gcode.analyze(asset.id)
        return {
            "job": job,
            "artifact": artifact,
            "asset": asset,
            "duplicate": duplicate,
            "gcode_metadata": metadata,
        }

    @staticmethod
    def _format_for_kind(kind: SliceArtifactKind, filename: str) -> AssetFormat:
        suffix = Path(filename).suffix.casefold()
        if kind == SliceArtifactKind.SLICED_3MF or suffix == ".3mf":
            return AssetFormat.THREE_MF
        if kind == SliceArtifactKind.BGCODE or suffix == ".bgcode":
            return AssetFormat.BGCODE
        if kind == SliceArtifactKind.GCODE or suffix == ".gcode":
            return AssetFormat.GCODE
        if kind == SliceArtifactKind.PREVIEW or suffix == ".png":
            return AssetFormat.PNG
        if kind == SliceArtifactKind.LOG:
            return AssetFormat.JSON
        raise ValueError(f"unsupported slice artifact: {kind.value} / {suffix}")
