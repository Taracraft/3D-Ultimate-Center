"""Profile Core types."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ProfileKind(StrEnum):
    PRINTER = "printer"
    NOZZLE = "nozzle"
    FILAMENT = "filament"
    PROCESS = "process"
    BUILD_PLATE = "build_plate"
    CALIBRATION = "calibration"


class ProfileSource(StrEnum):
    LOCAL = "local"
    MANUAL_UPLOAD = "manual_upload"
    BAMBU_CLOUD = "bambu_cloud"
    BAMBU_EXPORT = "bambu_export"
    ORCA_EXPORT = "orca_export"
    LEGACY_IMPORT = "legacy_import"


@dataclass(slots=True, frozen=True)
class ProfileSelection:
    printer_profile_id: str | None = None
    nozzle_profile_id: str | None = None
    process_profile_id: str | None = None
    build_plate_profile_id: str | None = None
    filament_profile_ids: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class ProfileRecord:
    id: str
    kind: ProfileKind
    name: str
    source: ProfileSource
    payload: dict[str, Any]
    created_at: str
    updated_at: str
    vendor_id: str | None = None
