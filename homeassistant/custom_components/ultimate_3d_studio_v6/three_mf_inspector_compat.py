"""Compatibility-safe 3MF inspection for large Bambu multi-plate projects.

This module preserves the canonical inspector and only supplements plate discovery
when the original result underreports plates because the metadata byte budget was
exhausted before all archive entries were scanned.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
import re
from typing import Any
import xml.etree.ElementTree as ET
import zipfile

from .three_mf_inspector import inspect_model as _inspect_model

_PLATE_FILE = re.compile(
    r"(?:^|/)(?:plate|plate_thumbnail|thumbnail|top|pick)[_-]?(\d+)(?:[_-][^/.]+)?(?:\.[^/]+)?$",
    re.IGNORECASE,
)
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_MAX_ENTRIES = 8192
_MAX_CONFIG_BYTES = 32_000_000


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].casefold()


def _metadata(element: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for child in element:
        if _local_name(child) != "metadata":
            continue
        key = str(child.attrib.get("key") or child.attrib.get("name") or "").strip().casefold()
        value = str(child.attrib.get("value") or child.text or "").strip()
        if key:
            result[key] = value
    return result


def _nonnegative_integer(value: object) -> int | None:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _plate_index_from_filename(filename: str) -> int | None:
    stem = str(PurePosixPath(filename).with_suffix(""))
    match = _PLATE_FILE.search(stem)
    if not match:
        return None
    return max(0, int(match.group(1)) - 1)


def _plate_record(index: int) -> dict[str, Any]:
    return {
        "plate_index": index,
        "display_number": index + 1,
        "name": f"Druckplatte {index + 1}",
        "object_count": None,
        "source": "3mf-large-project-compat",
        "thumbnail_available": False,
        "thumbnail_path": None,
    }


def _discover_model_settings(data: bytes) -> tuple[dict[int, str], dict[int, int]]:
    names: dict[int, str] = {}
    counts: dict[int, int] = {}
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return names, counts

    sequential = 0
    for plate in root.iter():
        if _local_name(plate) not in {"plate", "buildplate", "build_plate"}:
            continue
        meta = _metadata(plate)
        parsed = _nonnegative_integer(
            plate.attrib.get("id")
            or plate.attrib.get("index")
            or meta.get("plater_id")
            or meta.get("plate_id")
            or meta.get("plate_index")
        )
        index = sequential if parsed is None else parsed if parsed == 0 else parsed - 1
        sequential += 1
        if index < 0 or index > 255:
            continue
        name = str(
            meta.get("plater_name")
            or meta.get("plate_name")
            or meta.get("name")
            or meta.get("title")
            or meta.get("label")
            or ""
        ).strip()[:240]
        if name:
            names[index] = name
        count = 0
        for child in plate.iter():
            if _local_name(child) in {"model_instance", "instance", "object"}:
                count += 1
        counts[index] = count
    return names, counts


def _supplement_large_project(result: dict[str, Any], data: bytes) -> dict[str, Any]:
    discovered: dict[int, dict[str, Any]] = {}
    for existing in result.get("plates", []):
        if not isinstance(existing, dict):
            continue
        index = _nonnegative_integer(existing.get("plate_index"))
        if index is not None and index <= 255:
            discovered[index] = dict(existing)

    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > _MAX_ENTRIES:
                return result
            for info in infos:
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts:
                    return result
                index = _plate_index_from_filename(info.filename)
                if index is not None and index <= 255:
                    record = discovered.setdefault(index, _plate_record(index))
                    if path.suffix.casefold() in _IMAGE_SUFFIXES:
                        current = str(record.get("thumbnail_path") or "")
                        lowered = info.filename.casefold()
                        preferred = "/plate_" in lowered or lowered.startswith("metadata/plate_")
                        if not current or preferred:
                            record["thumbnail_available"] = True
                            record["thumbnail_path"] = info.filename

            settings = next(
                (info for info in infos if info.filename.casefold().endswith("model_settings.config")),
                None,
            )
            if settings is not None and settings.file_size <= _MAX_CONFIG_BYTES:
                names, counts = _discover_model_settings(archive.read(settings))
                for index in set(names) | set(counts):
                    record = discovered.setdefault(index, _plate_record(index))
                    if names.get(index):
                        record["name"] = names[index]
                    if index in counts:
                        record["object_count"] = counts[index]
    except (OSError, zipfile.BadZipFile, KeyError):
        return result

    if len(discovered) <= len(result.get("plates", [])):
        return result
    ordered = [discovered[index] for index in sorted(discovered)]
    return {**result, "plate_count": len(ordered), "plates": ordered}


def inspect_model(filename: str, data: bytes) -> dict[str, Any]:
    """Inspect a model without changing the established parser for normal files."""
    result = _inspect_model(filename, data)
    if result.get("format") != "3mf":
        return result
    return _supplement_large_project(result, data)
