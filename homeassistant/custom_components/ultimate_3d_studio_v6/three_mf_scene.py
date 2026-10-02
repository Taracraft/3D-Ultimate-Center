"""Extract editable per-part geometry from Bambu/Orca project 3MF files."""
from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
from typing import Any
import math
import re
import xml.etree.ElementTree as ET
import zipfile

_MAX_ENTRIES = 8192
_MAX_TRIANGLES = 2_000_000
_IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _metadata(element: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for child in element:
        if _local(child.tag) != "metadata":
            continue
        key = str(child.attrib.get("key") or child.attrib.get("name") or "").strip()
        value = str(child.attrib.get("value") or child.text or "").strip()
        if key:
            values[key.casefold()] = value
    return values


def _matrix(value: str | None) -> tuple[float, ...]:
    """Normalize 3MF 3x4 and Bambu/Orca 4x4 matrices.

    Internal layout stores three basis vectors followed by translation:
    xx,xy,xz, yx,yy,yz, zx,zy,zz, tx,ty,tz.
    """
    if not value or not value.strip():
        return _IDENTITY
    try:
        parts = [float(item) for item in re.split(r"[\s,;]+", value.strip()) if item]
    except ValueError as exc:
        raise ValueError("Ungültige 3MF-Transformationsmatrix") from exc
    if not all(math.isfinite(item) for item in parts):
        raise ValueError("Ungültige 3MF-Transformationsmatrix")
    if len(parts) == 12:
        return tuple(parts)
    if len(parts) == 16:
        if not (
            abs(parts[12]) < 1e-7
            and abs(parts[13]) < 1e-7
            and abs(parts[14]) < 1e-7
            and abs(parts[15] - 1.0) < 1e-7
        ):
            raise ValueError("Ungültige 3MF-Transformationsmatrix")
        return (
            parts[0], parts[4], parts[8],
            parts[1], parts[5], parts[9],
            parts[2], parts[6], parts[10],
            parts[3], parts[7], parts[11],
        )
    raise ValueError("Ungültige 3MF-Transformationsmatrix")


def _is_identity(matrix: tuple[float, ...], tolerance: float = 1e-7) -> bool:
    return all(abs(left - right) <= tolerance for left, right in zip(matrix, _IDENTITY, strict=True))


def _apply(matrix: tuple[float, ...], point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    return (
        matrix[0] * x + matrix[3] * y + matrix[6] * z + matrix[9],
        matrix[1] * x + matrix[4] * y + matrix[7] * z + matrix[10],
        matrix[2] * x + matrix[5] * y + matrix[8] * z + matrix[11],
    )


def _multiply(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    basis: list[float] = []
    origin = _apply(a, (0.0, 0.0, 0.0))
    for column in range(3):
        vector = (b[column * 3], b[column * 3 + 1], b[column * 3 + 2])
        transformed = _apply(a, vector)
        basis.extend((
            transformed[0] - origin[0],
            transformed[1] - origin[1],
            transformed[2] - origin[2],
        ))
    translated = _apply(a, (b[9], b[10], b[11]))
    return tuple(basis + [translated[0], translated[1], translated[2]])


def _parse_mesh(data: bytes, object_id: str) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("3MF-Objektgeometrie ist ungültig") from exc
    selected: ET.Element | None = None
    for element in root.iter():
        if _local(element.tag) == "object" and str(element.attrib.get("id")) == object_id:
            selected = element
            break
    if selected is None:
        for element in root.iter():
            if _local(element.tag) == "object":
                selected = element
                break
    if selected is None:
        raise ValueError(f"3MF-Objekt {object_id} enthält kein Mesh")
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    for element in selected.iter():
        local = _local(element.tag)
        if local == "vertex":
            vertices.append((float(element.attrib["x"]), float(element.attrib["y"]), float(element.attrib["z"])))
        elif local == "triangle":
            triangles.append((int(element.attrib["v1"]), int(element.attrib["v2"]), int(element.attrib["v3"])))
    if not vertices or not triangles:
        raise ValueError(f"3MF-Objekt {object_id} enthält keine Dreiecke")
    return vertices, triangles


def _model_settings(archive: zipfile.ZipFile) -> tuple[dict[str, dict[str, Any]], dict[int, list[str]]]:
    try:
        root = ET.fromstring(archive.read("Metadata/model_settings.config"))
    except (KeyError, ET.ParseError) as exc:
        raise ValueError("Bambu model_settings.config fehlt oder ist ungültig") from exc
    objects: dict[str, dict[str, Any]] = {}
    plates: dict[int, list[str]] = {}
    for element in root:
        local = _local(element.tag)
        if local == "object":
            metadata = _metadata(element)
            object_id = str(element.attrib.get("id") or metadata.get("object_id") or "")
            if not object_id:
                continue
            parts: dict[str, dict[str, Any]] = {}
            for child in element:
                if _local(child.tag) != "part":
                    continue
                part_metadata = _metadata(child)
                part_id = str(child.attrib.get("id") or part_metadata.get("object_id") or "")
                parts[part_id] = {
                    "part_id": part_id,
                    "name": part_metadata.get("name") or f"Teil {part_id}",
                    "extruder": int(part_metadata.get("extruder") or metadata.get("extruder") or 1),
                    "matrix": _matrix(part_metadata.get("matrix")),
                    "subtype": child.attrib.get("subtype") or "normal_part",
                }
            objects[object_id] = {
                "object_id": object_id,
                "name": metadata.get("name") or f"Objekt {object_id}",
                "extruder": int(metadata.get("extruder") or 1),
                "parts": parts,
            }
        elif local == "plate":
            metadata = _metadata(element)
            raw = metadata.get("plater_id") or metadata.get("plate_id") or "1"
            plate_index = max(0, int(raw) - 1)
            ids: list[str] = []
            for child in element:
                if _local(child.tag) != "model_instance":
                    continue
                object_id = _metadata(child).get("object_id")
                if object_id:
                    ids.append(object_id)
            plates[plate_index] = ids
    return objects, plates


def _main_model(archive: zipfile.ZipFile) -> tuple[dict[str, list[dict[str, Any]]], dict[str, tuple[float, ...]]]:
    try:
        root = ET.fromstring(archive.read("3D/3dmodel.model"))
    except (KeyError, ET.ParseError) as exc:
        raise ValueError("3D/3dmodel.model fehlt oder ist ungültig") from exc
    components: dict[str, list[dict[str, Any]]] = {}
    build: dict[str, tuple[float, ...]] = {}
    for element in root.iter():
        local = _local(element.tag)
        if local == "object":
            object_id = str(element.attrib.get("id") or "")
            values: list[dict[str, Any]] = []
            for child in element.iter():
                if _local(child.tag) != "component":
                    continue
                path = next((value for key, value in child.attrib.items() if key.rsplit("}", 1)[-1] == "path"), "")
                values.append({
                    "path": path.lstrip("/"),
                    "part_id": str(child.attrib.get("objectid") or ""),
                    "matrix": _matrix(child.attrib.get("transform")),
                })
            if values:
                components[object_id] = values
        elif local == "item":
            object_id = str(element.attrib.get("objectid") or "")
            if object_id:
                build[object_id] = _matrix(element.attrib.get("transform"))
    return components, build


def extract_scene(filename: str, data: bytes, plate_index: int) -> dict[str, Any]:
    if not filename.casefold().endswith(".3mf"):
        raise ValueError("Projekt-Szene ist nur für 3MF verfügbar")
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("Die 3MF-Datei ist ungültig") from exc
    with archive:
        if len(archive.infolist()) > _MAX_ENTRIES:
            raise ValueError("3MF enthält zu viele Dateien")
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("3MF enthält einen unsicheren Pfad")
        settings, plates = _model_settings(archive)
        components, build = _main_model(archive)
        selected_ids = plates.get(plate_index, [])
        instances: list[dict[str, Any]] = []
        triangle_total = 0
        bounds_min = [float("inf"), float("inf"), float("inf")]
        bounds_max = [float("-inf"), float("-inf"), float("-inf")]
        cache: dict[tuple[str, str], tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]] = {}

        for object_id in selected_ids:
            object_info = settings.get(object_id, {"name": f"Objekt {object_id}", "extruder": 1, "parts": {}})
            object_matrix = build.get(object_id, _IDENTITY)
            for component in components.get(object_id, []):
                part_id = component["part_id"]
                part_info = object_info.get("parts", {}).get(part_id, {})
                key = (component["path"], part_id)
                if key not in cache:
                    try:
                        mesh_data = archive.read(component["path"])
                    except KeyError as exc:
                        raise ValueError(f"3MF-Mesh fehlt: {component['path']}") from exc
                    cache[key] = _parse_mesh(mesh_data, part_id)
                vertices, triangles = cache[key]
                triangle_total += len(triangles)
                if triangle_total > _MAX_TRIANGLES:
                    raise ValueError("3MF-Projekt ist für die Browser-Szene zu komplex")

                component_matrix = component["matrix"]
                part_matrix = part_info.get("matrix", _IDENTITY)
                # Bambu Studio writes the same local part transform into both
                # the component transform and model_settings.config. Applying
                # both matrices doubles every part offset and explodes the
                # assembled object. The component transform is authoritative;
                # the settings matrix is only a compatibility fallback.
                local_matrix = part_matrix if _is_identity(component_matrix) else component_matrix
                combined = _multiply(object_matrix, local_matrix)
                transformed = [_apply(combined, vertex) for vertex in vertices]
                positions: list[float] = []
                for triangle in triangles:
                    for vertex_index in triangle:
                        point = transformed[vertex_index]
                        positions.extend(point)
                        for axis in range(3):
                            bounds_min[axis] = min(bounds_min[axis], point[axis])
                            bounds_max[axis] = max(bounds_max[axis], point[axis])
                instances.append({
                    "id": f"{object_id}:{part_id}",
                    "object_id": object_id,
                    "part_id": part_id,
                    "name": part_info.get("name") or object_info.get("name") or f"Teil {part_id}",
                    "extruder": int(part_info.get("extruder") or object_info.get("extruder") or 1),
                    "positions": positions,
                    "triangle_count": len(triangles),
                    "visible": True,
                })

        if not instances:
            raise ValueError(f"Druckplatte {plate_index + 1} enthält keine darstellbaren Objekte")

        # Bambu stores all project plates in one global coordinate system.
        # Convert the selected plate once into the local 256x256 studio space,
        # preserving the exact relative project arrangement of every part.
        center_x = (bounds_min[0] + bounds_max[0]) / 2
        center_y = (bounds_min[1] + bounds_max[1]) / 2
        floor_z = bounds_min[2]
        shift = (128 - center_x, 128 - center_y, -floor_z)
        for instance in instances:
            positions = instance["positions"]
            for index in range(0, len(positions), 3):
                positions[index] += shift[0]
                positions[index + 1] += shift[1]
                positions[index + 2] += shift[2]
        return {
            "filename": filename,
            "plate_index": plate_index,
            "plate_display_number": plate_index + 1,
            "instances": instances,
            "triangle_count": triangle_total,
            "bounds": {
                "min": [bounds_min[0] + shift[0], bounds_min[1] + shift[1], 0],
                "max": [bounds_max[0] + shift[0], bounds_max[1] + shift[1], bounds_max[2] + shift[2]],
            },
            "plate_size": [256, 256],
        }