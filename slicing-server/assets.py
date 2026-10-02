"""Asset Core types."""

from dataclasses import dataclass
from enum import StrEnum


class AssetKind(StrEnum):
    MODEL = "model"
    PROJECT = "project"
    SLICE_ARTIFACT = "slice_artifact"
    PREVIEW = "preview"
    PROFILE_PACKAGE = "profile_package"


class AssetFormat(StrEnum):
    STL = "stl"
    THREE_MF = "3mf"
    OBJ = "obj"
    STEP = "step"
    GCODE = "gcode"
    BGCODE = "bgcode"
    PNG = "png"
    JPEG = "jpeg"
    JSON = "json"
    ZIP = "zip"


@dataclass(slots=True, frozen=True)
class AssetRecord:
    id: str
    kind: AssetKind
    format: AssetFormat
    digest: str
    size_bytes: int
    original_name: str
    storage_key: str
    created_at: str