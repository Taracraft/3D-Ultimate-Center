"""Safe Bambu/Orca 3MF inspection for plates, objects and materials."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import PurePosixPath
import re
from typing import Any
import xml.etree.ElementTree as ET
import zipfile

_MAX_ENTRIES = 8192
_MAX_METADATA_BYTES = 32_000_000
_PLATE_FILE = re.compile(
    r"(?:^|/)(?:plate|plate_thumbnail|thumbnail|top|pick)[_-]?(\d+)(?:[_-][^/.]+)?(?:\.[^/]+)?$",
    re.IGNORECASE,
)


def _integer(value: Any) -> int | None:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _text(value: Any, limit: int = 240) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value).strip()[:limit]


def _normalise_color(value: Any) -> str | None:
    text = _text(value, 32).upper()
    if not text:
        return None
    if not text.startswith("#"):
        text = f"#{text}"
    if re.fullmatch(r"#[0-9A-F]{6}(?:[0-9A-F]{2})?", text):
        return text[:7]
    return None


def _plate_record(index: int) -> dict[str, Any]:
    return {
        "plate_index": index,
        "display_number": index + 1,
        "name": f"Druckplatte {index + 1}",
        "object_count": None,
        "source": "3mf",
        "thumbnail_available": False,
        "thumbnail_path": None,
    }


def _merge_plate(
    plates: dict[int, dict[str, Any]],
    index: int,
    *,
    name: str = "",
    object_count: int | None = None,
    thumbnail_path: str | None = None,
) -> None:
    if index < 0 or index > 255:
        return
    record = plates.setdefault(index, _plate_record(index))
    if name:
        record["name"] = name
    if object_count is not None and object_count >= 0:
        record["object_count"] = object_count
    if thumbnail_path:
        current = str(record.get("thumbnail_path") or "")
        lowered = thumbnail_path.casefold()
        preferred = "/plate_" in lowered or lowered.startswith("metadata/plate_")
        if not current or preferred:
            record["thumbnail_available"] = True
            record["thumbnail_path"] = thumbnail_path


def _filename_plate_index(filename: str) -> int | None:
    stem = str(PurePosixPath(filename).with_suffix(""))
    match = _PLATE_FILE.search(stem)
    if not match:
        return None
    number = int(match.group(1))
    return max(0, number - 1)


def _metadata_map(element: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for child in element:
        if child.tag.rsplit("}", 1)[-1].casefold() != "metadata":
            continue
        key = _text(child.attrib.get("key") or child.attrib.get("name"), 120)
        value = _text(child.attrib.get("value") or child.text, 500)
        if key:
            values[key.casefold()] = value
    return values


def _object_record(element: ET.Element, plate_index: int | None, parent_id: str | None = None) -> dict[str, Any]:
    metadata = _metadata_map(element)
    object_id = _text(element.attrib.get("id") or metadata.get("object_id") or metadata.get("id"), 120)
    name = _text(
        element.attrib.get("name")
        or metadata.get("name")
        or metadata.get("object_name")
        or metadata.get("source_file")
        or f"Objekt {object_id or '?'}",
        240,
    )
    extruder = _integer(
        metadata.get("extruder")
        or metadata.get("filament")
        or metadata.get("filament_id")
        or element.attrib.get("extruder")
    )
    return {
        "object_id": object_id or f"anonymous-{id(element)}",
        "parent_id": parent_id,
        "name": name,
        "plate_index": plate_index,
        "extruder": extruder,
        "printable": _text(metadata.get("printable") or element.attrib.get("printable"), 16).casefold() not in {"0", "false", "no"},
        "type": _text(metadata.get("type") or element.attrib.get("type") or "model", 60),
        "parts": [],
    }


def _parse_model_settings(data: bytes) -> tuple[list[dict[str, Any]], dict[str, int]]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return [], {}

    objects: list[dict[str, Any]] = []
    object_plate: dict[str, int] = {}

    sequential_plate = 0
    for plate in root.iter():
        local = plate.tag.rsplit("}", 1)[-1].casefold()
        if local not in {"plate", "buildplate", "build_plate"}:
            continue
        metadata = _metadata_map(plate)
        parsed = _integer(
            plate.attrib.get("id")
            or plate.attrib.get("index")
            or metadata.get("plater_id")
            or metadata.get("plate_id")
            or metadata.get("plate_index")
        )
        plate_index = sequential_plate if parsed is None else parsed if parsed == 0 else parsed - 1
        sequential_plate += 1
        for child in plate.iter():
            child_local = child.tag.rsplit("}", 1)[-1].casefold()
            if child_local not in {"model_instance", "instance", "object"}:
                continue
            child_meta = _metadata_map(child)
            object_id = _text(
                child.attrib.get("object_id")
                or child.attrib.get("id")
                or child_meta.get("object_id"),
                120,
            )
            if object_id:
                object_plate[object_id] = plate_index

    for element in root.iter():
        local = element.tag.rsplit("}", 1)[-1].casefold()
        if local != "object":
            continue
        metadata = _metadata_map(element)
        object_id = _text(element.attrib.get("id") or metadata.get("object_id") or metadata.get("id"), 120)
        plate_index = object_plate.get(object_id)
        raw_plate = _integer(metadata.get("plate_id") or metadata.get("plate_index"))
        if raw_plate is not None:
            plate_index = raw_plate if raw_plate == 0 else raw_plate - 1
        record = _object_record(element, plate_index)
        for child in element:
            child_local = child.tag.rsplit("}", 1)[-1].casefold()
            if child_local in {"part", "volume", "mesh", "component"}:
                part = _object_record(child, plate_index, record["object_id"])
                if part.get("extruder") is None:
                    part["extruder"] = record.get("extruder")
                record["parts"].append(part)
        objects.append(record)

    return objects, object_plate


def _json_list(payload: dict[str, Any], keys: tuple[str, ...]) -> list[Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                return parsed
    return []


def _parse_project_settings(payload: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(payload, dict):
        return [], {}
    colors = _json_list(payload, ("filament_colour", "filament_color", "filament_colours"))
    types = _json_list(payload, ("filament_type", "filament_types"))
    names = _json_list(payload, ("filament_settings_id", "filament_settings_ids", "filament_id"))
    count = max(len(colors), len(types), len(names))
    filaments: list[dict[str, Any]] = []
    for index in range(count):
        filaments.append({
            "extruder": index + 1,
            "name": _text(names[index] if index < len(names) else "", 180) or f"Filament {index + 1}",
            "material": _text(types[index] if index < len(types) else "", 80) or "unknown",
            "color": _normalise_color(colors[index] if index < len(colors) else None),
        })

    raw_x = payload.get("wipe_tower_x") or payload.get("prime_tower_x")
    raw_y = payload.get("wipe_tower_y") or payload.get("prime_tower_y")
    raw_multiplier = payload.get("flush_multiplier")
    purge = {
        "enabled": str(payload.get("enable_prime_tower", payload.get("prime_tower", "0"))).casefold() in {"1", "true", "yes"},
        "width_mm": _float(payload.get("prime_tower_width")),
        "brim_width_mm": _float(payload.get("prime_tower_brim_width")),
        "position_x": _float(raw_x) if not isinstance(raw_x, list) else None,
        "position_y": _float(raw_y) if not isinstance(raw_y, list) else None,
        "positions_x": [_float(item) for item in raw_x] if isinstance(raw_x, list) else [],
        "positions_y": [_float(item) for item in raw_y] if isinstance(raw_y, list) else [],
        "flush_multiplier": _float(raw_multiplier) if not isinstance(raw_multiplier, list) else (_float(raw_multiplier[0]) if raw_multiplier else None),
        "flush_multipliers": [_float(item) for item in raw_multiplier] if isinstance(raw_multiplier, list) else [],
        "flush_volumes_matrix": _json_list(payload, ("flush_volumes_matrix",)),
        "flush_volumes_vector": _json_list(payload, ("flush_volumes_vector",)),
    }
    return filaments, purge


def _json_plate(plates: dict[int, dict[str, Any]], filename: str, payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    index = _filename_plate_index(filename)
    raw_index = next((payload.get(key) for key in ("plate_index", "plate_idx", "plate_id", "index") if payload.get(key) is not None), None)
    parsed = _integer(raw_index)
    if parsed is not None:
        index = parsed if parsed == 0 else parsed - 1
    if index is None:
        return
    name = next((_text(payload.get(key)) for key in ("plate_name", "name", "title", "label") if _text(payload.get(key))), "")
    object_count = next((_integer(payload.get(key)) for key in ("object_count", "objects_count", "model_count", "part_count") if _integer(payload.get(key)) is not None), None)
    if object_count is None:
        for key in ("objects", "models", "parts"):
            value = payload.get(key)
            if isinstance(value, list):
                object_count = len(value)
                break
    _merge_plate(plates, index, name=name, object_count=object_count)


def inspect_model(filename: str, data: bytes) -> dict[str, Any]:
    """Return Bambu-aware plate, object, material and purge metadata."""
    if not filename.casefold().endswith(".3mf"):
        return {
            "format": "stl",
            "plate_count": 1,
            "plates": [{"plate_index": 0, "display_number": 1, "name": "Druckplatte 1", "object_count": None, "source": "3mf"}],
            "objects": [{
                "object_id": "stl-1",
                "parent_id": None,
                "name": PurePosixPath(filename).name,
                "plate_index": 0,
                "extruder": 1,
                "printable": True,
                "type": "model",
                "parts": [],
            }],
            "filaments": [],
            "purge_tower": {},
            "multimaterial": False,
        }

    plates: dict[int, dict[str, Any]] = {}
    objects: list[dict[str, Any]] = []
    filaments: list[dict[str, Any]] = []
    purge_tower: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > _MAX_ENTRIES:
                raise ValueError("3MF enthält eine ungültige Anzahl von Dateien")
            metadata_total = 0
            for info in infos:
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError("3MF enthält einen unsicheren Pfad")
                lowered = info.filename.casefold()
                file_index = _filename_plate_index(info.filename)
                if file_index is not None and PurePosixPath(info.filename).suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}:
                    _merge_plate(plates, file_index, thumbnail_path=info.filename)
                elif file_index is not None:
                    _merge_plate(plates, file_index)
                if not (lowered.endswith(".json") or lowered.endswith(".config") or lowered.endswith(".xml") or lowered.endswith(".model")):
                    continue
                if info.file_size > _MAX_METADATA_BYTES:
                    continue
                metadata_total += int(info.file_size)
                if metadata_total > _MAX_METADATA_BYTES:
                    break
                raw = archive.read(info)
                if lowered.endswith("project_settings.config") or lowered.endswith("project_settings.json"):
                    try:
                        parsed = json.loads(raw.decode("utf-8-sig"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        parsed = None
                    parsed_filaments, parsed_purge = _parse_project_settings(parsed)
                    if parsed_filaments:
                        filaments = parsed_filaments
                    if parsed_purge:
                        purge_tower = parsed_purge
                elif lowered.endswith("model_settings.config"):
                    parsed_objects, _mapping = _parse_model_settings(raw)
                    if parsed_objects:
                        objects = parsed_objects
                elif lowered.endswith(".json"):
                    try:
                        _json_plate(plates, info.filename, json.loads(raw.decode("utf-8-sig")))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue

    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("Die 3MF-Datei ist kein gültiges ZIP/3MF-Archiv") from exc

    if not plates:
        _merge_plate(plates, 0)
    if objects:
        counts: dict[int, int] = {}
        for item in objects:
            index = item.get("plate_index")
            if isinstance(index, int) and index >= 0:
                counts[index] = counts.get(index, 0) + 1
        for index, count in counts.items():
            _merge_plate(plates, index, object_count=count)
    ordered = [plates[index] for index in sorted(plates)]
    used_extruders = {
        int(value)
        for item in objects
        for value in [item.get("extruder"), *[part.get("extruder") for part in item.get("parts", [])]]
        if isinstance(value, int) and value > 0
    }
    return {
        "format": "3mf",
        "plate_count": len(ordered),
        "plates": ordered,
        "objects": objects,
        "filaments": filaments,
        "purge_tower": purge_tower,
        "multimaterial": len(used_extruders) > 1 or len(filaments) > 1,
        "used_extruders": sorted(used_extruders),
    }
