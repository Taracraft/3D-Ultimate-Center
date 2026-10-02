"""Gallery Core domain types."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class GalleryFolder:
    id: str
    name: str
    created_at: str
    updated_at: str
    parent_id: str | None = None


@dataclass(slots=True, frozen=True)
class GalleryItem:
    asset_id: str
    title: str
    description: str
    favorite: bool
    created_at: str
    updated_at: str
    folder_id: str | None = None
    tags: tuple[str, ...] = ()