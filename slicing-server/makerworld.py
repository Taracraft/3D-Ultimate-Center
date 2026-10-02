"""MakerWorld domain contracts and import destinations."""

from dataclasses import dataclass
from enum import StrEnum


class MakerWorldDestination(StrEnum):
    GALLERY = "gallery"
    STUDIO = "studio"
    SLICER = "slicer"


@dataclass(slots=True, frozen=True)
class MakerWorldCreator:
    id: str | None
    name: str
    profile_url: str | None = None


@dataclass(slots=True, frozen=True)
class MakerWorldPrintProfile:
    id: str
    name: str
    printer_model: str | None
    nozzle_diameter: float | None
    plate_count: int | None
    filament_count: int | None
    thumbnail_url: str | None = None


@dataclass(slots=True, frozen=True)
class MakerWorldModel:
    id: str
    title: str
    model_url: str
    description: str
    creator: MakerWorldCreator
    license_name: str | None
    license_url: str | None
    thumbnail_url: str | None
    downloads: int | None
    likes: int | None
    tags: tuple[str, ...]
    print_profiles: tuple[MakerWorldPrintProfile, ...]


@dataclass(slots=True, frozen=True)
class MakerWorldSearchResult:
    items: tuple[MakerWorldModel, ...]
    next_cursor: str | None = None


@dataclass(slots=True, frozen=True)
class MakerWorldDownload:
    model: MakerWorldModel
    profile_id: str | None
    filename: str
    content_type: str
    temporary_path: str
    source_url: str
    license_acknowledged: bool