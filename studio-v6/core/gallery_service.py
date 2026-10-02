"""Gallery Core application service."""

from __future__ import annotations

from dataclasses import replace

from .common import new_id, utc_now
from .gallery import GalleryFolder, GalleryItem
from .sqlite_gallery import SqliteGalleryRepository


class GalleryService:
    def __init__(self, repository: SqliteGalleryRepository) -> None:
        self._repository = repository

    def create_folder(
        self,
        name: str,
        parent_id: str | None = None,
    ) -> GalleryFolder:
        normalized = name.strip()
        if not normalized:
            raise ValueError("folder name must not be empty")
        now = utc_now()
        folder = GalleryFolder(
            id=new_id("folder"),
            name=normalized,
            parent_id=parent_id,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_folder(folder)
        return folder

    def add_asset(
        self,
        *,
        asset_id: str,
        title: str,
        description: str = "",
        folder_id: str | None = None,
        tags: tuple[str, ...] = (),
        favorite: bool = False,
    ) -> GalleryItem:
        normalized = title.strip()
        if not normalized:
            raise ValueError("gallery title must not be empty")
        now = utc_now()
        item = GalleryItem(
            asset_id=asset_id,
            title=normalized,
            description=description.strip(),
            folder_id=folder_id,
            favorite=favorite,
            tags=tags,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_item(item)
        return item

    def set_favorite(self, asset_id: str, favorite: bool) -> GalleryItem:
        item = self._repository.get_item(asset_id)
        if item is None:
            raise KeyError(asset_id)
        updated = replace(item, favorite=favorite, updated_at=utc_now())
        self._repository.add_item(updated)
        return updated

    def search(self, query: str = "", limit: int = 100) -> list[GalleryItem]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        return self._repository.search(query, limit)