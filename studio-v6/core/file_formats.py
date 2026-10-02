"""File format validation shared by upload and import paths."""

from pathlib import Path

from .assets import AssetFormat, AssetKind

_FORMATS = {
    ".stl": (AssetFormat.STL, AssetKind.MODEL),
    ".3mf": (AssetFormat.THREE_MF, AssetKind.MODEL),
    ".obj": (AssetFormat.OBJ, AssetKind.MODEL),
    ".step": (AssetFormat.STEP, AssetKind.MODEL),
    ".stp": (AssetFormat.STEP, AssetKind.MODEL),
    ".gcode": (AssetFormat.GCODE, AssetKind.SLICE_ARTIFACT),
}


def resolve_format(filename: str) -> tuple[AssetFormat, AssetKind]:
    suffix = Path(filename).suffix.casefold()
    result = _FORMATS.get(suffix)
    if result is None:
        raise ValueError(f"unsupported file format: {suffix or '<none>'}")
    return result
