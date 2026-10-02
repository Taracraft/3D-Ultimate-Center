"""Automatic mesh analysis after asset registration."""

from __future__ import annotations

from .asset_service import AssetService
from .common import utc_now
from .mesh_parsers import parse_mesh
from .sqlite_mesh import SqliteMeshRepository


class AnalysisService:
    def __init__(
        self,
        assets: AssetService,
        mesh_repository: SqliteMeshRepository,
    ) -> None:
        self._assets = assets
        self._mesh_repository = mesh_repository

    def analyze_asset(self, asset_id: str):
        asset = self._assets.get(asset_id)
        path = self._assets.resolve_path(asset)
        metadata = parse_mesh(path)
        self._mesh_repository.save(asset.id, metadata, utc_now())
        return metadata