"""G-code metadata extraction and persistence service."""

from __future__ import annotations

from .asset_service import AssetService
from .common import utc_now
from .gcode_parser import parse_gcode
from .sqlite_slicing import SqliteGCodeRepository


class GCodeService:
    def __init__(
        self,
        assets: AssetService,
        repository: SqliteGCodeRepository,
    ) -> None:
        self._assets = assets
        self._repository = repository

    def analyze(self, asset_id: str):
        asset = self._assets.get(asset_id)
        path = self._assets.resolve_path(asset)
        metadata = parse_gcode(path)
        self._repository.save(asset.id, metadata, utc_now())
        return metadata

    def get(self, asset_id: str):
        metadata = self._repository.get(asset_id)
        if metadata is None:
            raise KeyError(asset_id)
        return metadata