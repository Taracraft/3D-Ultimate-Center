"""Deterministic filename lookup on a Studio printer SD card."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from .bambu_direct_print import _close_ftps
from .printer_storage import BambuPrinterStorage

_SUPPORTED_SUFFIXES = (
    ".gcode",
    ".gcode.3mf",
    ".3mf",
    ".stl",
    ".obj",
)
_COMMON_FOLDERS = (
    "",
    "cache",
    "model",
    "models",
    "gcode",
    "print",
)


def _kind(name: str) -> str:
    lowered = name.casefold()
    if lowered.endswith((".gcode", ".gcode.3mf")):
        return "gcode"
    if lowered.endswith(".3mf"):
        return "project"
    if lowered.endswith((".stl", ".obj")):
        return "model"
    return "file"


def _filename_candidates(requested: str) -> list[str]:
    names = [requested]
    lowered = requested.casefold()
    if lowered.endswith(".gcode"):
        names.insert(0, f"{requested}.3mf")
    elif lowered.endswith(".3mf") and not lowered.endswith(".gcode.3mf"):
        embedded = requested[:-4]
        if embedded.casefold().endswith(".gcode"):
            names.append(embedded)
    result: list[str] = []
    for name in names:
        if name not in result:
            result.append(name)
    return result


def find_storage_file(
    storage: BambuPrinterStorage,
    filename: str,
) -> dict[str, Any] | None:
    """Resolve a real history filename without scanning the complete SD tree.

    Bambu print history may expose the embedded ``plate_*.gcode`` name while
    the uploaded file on the SD card is ``plate_*.gcode.3mf``. Both exact
    forms are checked in the root and a small allowlist of known Bambu
    folders. Human-readable process labels without a file suffix are rejected
    immediately.
    """
    requested = PurePosixPath(
        str(filename or "").replace("\\", "/")
    ).name.strip()
    if not requested:
        return None
    lowered = requested.casefold()
    if not lowered.endswith(_SUPPORTED_SUFFIXES):
        return None

    client = storage._connect(timeout=12)
    try:
        if client.sock is not None:
            client.sock.settimeout(4)
        for folder in _COMMON_FOLDERS:
            for name in _filename_candidates(requested):
                command_path = f"{folder}/{name}" if folder else name
                size = storage._size(client, command_path)
                if size is None:
                    continue
                item_path = f"/{command_path.lstrip('/')}"
                return {
                    "path": item_path,
                    "name": name,
                    "kind": _kind(name),
                    "size_bytes": size,
                    "modified": "",
                    "preview_data_url": "",
                }
    finally:
        _close_ftps(client)
    return None
