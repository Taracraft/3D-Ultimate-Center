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
_MAX_GRAPH_DEPTH = 32
_MAX_PARTS = 4096
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
        raise ValueError("3MF-Objektgeometrie ist ungueltig") from exc
    selected = [
        element for element in root.iter()
        if _local(element.tag) == "object" and str(element.attrib.get("id")) == object_id
    ]
    if len(selected) != 1:
        raise ValueError(f"3MF-Objekt {object_id} fehlt oder ist nicht eindeutig")
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    try:
        for element in selected[0].iter():
            local = _local(element.tag)
            if local == "vertex":
                point = tuple(float(element.attrib[axis]) for axis in ("x", "y", "z"))
                if not all(math.isfinite(value) for value in point):
                    raise ValueError("nonfinite vertex")
                vertices.append(point)
            elif local == "triangle":
                triangles.append(tuple(int(element.attrib[key]) for key in ("v1", "v2", "v3")))
    except (KeyError, ValueError, OverflowError) as exc:
        raise ValueError(f"3MF-Objekt {object_id} enthaelt ungueltige Meshdaten") from exc
    if not vertices or not triangles:
        raise ValueError(f"3MF-Objekt {object_id} enthaelt keine Dreiecke")
    if any(index < 0 or index >= len(vertices) for triangle in triangles for index in triangle):
        raise ValueError(f"3MF-Objekt {object_id} enthaelt ungueltige Dreiecksreferenzen")
    return vertices, triangles

def _model_settings(archive: zipfile.ZipFile) -> tuple[dict[str, dict[str, Any]], dict[int, list[tuple[str, int | None]]]]:
    try:
        root = ET.fromstring(_archive_bytes(archive, "Metadata/model_settings.config"))
    except (KeyError, ET.ParseError) as exc:
        raise ValueError("Bambu model_settings.config fehlt oder ist ungültig") from exc
    objects: dict[str, dict[str, Any]] = {}
    plates: dict[int, list[tuple[str, int | None]]] = {}
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
            ids: list[tuple[str, int | None]] = []
            for child in element:
                if _local(child.tag) != "model_instance":
                    continue
                instance_metadata = _metadata(child)
                object_id = instance_metadata.get("object_id")
                if object_id:
                    raw_instance = instance_metadata.get("instance_id")
                    if raw_instance is not None and re.fullmatch(r"[0-9]+", raw_instance) is None:
                        raise ValueError("3MF enthaelt eine ungueltige Instanznummer")
                    ids.append((object_id, None if raw_instance is None else int(raw_instance)))
            plates[plate_index] = ids
    return objects, plates


def _archive_bytes(archive: zipfile.ZipFile, path: str) -> bytes:
    if sum(info.filename == path for info in archive.infolist()) != 1:
        raise ValueError(f"3MF-Modell {path} fehlt oder ist nicht eindeutig")
    return archive.read(path)


def _model_path(value: str | None, current: str) -> str:
    raw = (value or current).replace("\\", "/").lstrip("/")
    path = PurePosixPath(raw)
    if ".." in path.parts or not raw.casefold().startswith("3d/") or not raw.casefold().endswith(".model"):
        raise ValueError("3MF enthaelt einen ungueltigen Komponentenpfad")
    return str(path)


def _read_model(
    archive: zipfile.ZipFile,
    path: str,
    cache: dict[str, tuple[bytes, ET.Element, dict[str, list[ET.Element]]]],
) -> tuple[bytes, ET.Element, dict[str, list[ET.Element]]]:
    if path not in cache:
        raw = _archive_bytes(archive, path)
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ValueError(f"3MF-Modell {path} ist ungueltig") from exc
        objects: dict[str, list[ET.Element]] = {}
        for resource in root:
            if _local(resource.tag) != "resources":
                continue
            for item in resource:
                if _local(item.tag) == "object":
                    objects.setdefault(str(item.attrib.get("id") or ""), []).append(item)
        cache[path] = (raw, root, objects)
    return cache[path]


def _main_model(
    archive: zipfile.ZipFile,
    cache: dict[str, tuple[bytes, ET.Element, dict[str, list[ET.Element]]]],
) -> dict[str, list[dict[str, Any]]]:
    _, root, _ = _read_model(archive, "3D/3dmodel.model", cache)
    build: dict[str, list[dict[str, Any]]] = {}
    for section in root:
        if _local(section.tag) != "build":
            continue
        for item in section:
            if _local(item.tag) != "item":
                continue
            object_id = str(item.attrib.get("objectid") or "")
            path = next((value for key, value in item.attrib.items() if _local(key) == "path"), None)
            build.setdefault(object_id, []).append({
                "path": _model_path(path, "3D/3dmodel.model"),
                "matrix": _matrix(item.attrib.get("transform")),
            })
    return build


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
        model_cache: dict[str, tuple[bytes, ET.Element, dict[str, list[ET.Element]]]] = {}
        build = _main_model(archive, model_cache)
        instances: list[dict[str, Any]] = []
        triangle_total = 0
        bounds_min = [float("inf"), float("inf"), float("inf")]
        bounds_max = [float("-inf"), float("-inf"), float("-inf")]
        mesh_cache: dict[tuple[str, str], tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]] = {}
        selected: set[tuple[str, int]] = set()

        for object_id, instance_id in plates.get(plate_index, []):
            builds = build.get(object_id, [])
            if instance_id is None:
                if len(builds) != 1:
                    raise ValueError(f"3MF-Instanz fuer Objekt {object_id} ist nicht eindeutig")
                instance_id = 0
            if instance_id >= len(builds):
                raise ValueError(f"3MF-Instanz fuer Objekt {object_id} fehlt")
            selection = (object_id, instance_id)
            if selection in selected:
                raise ValueError("3MF-Druckplatte enthaelt eine doppelte Instanzzuordnung")
            selected.add(selection)
            object_info = settings.get(object_id, {"name": f"Objekt {object_id}", "extruder": 1, "parts": {}})
            build_item = builds[instance_id]
            first_instance = len(instances)

            def flatten(
                model_path: str,
                mesh_id: str,
                transform: tuple[float, ...],
                stack: tuple[tuple[str, str], ...],
                route: tuple[int, ...],
                inherited_part: dict[str, Any] | None = None,
            ) -> None:
                nonlocal triangle_total
                key = (model_path, mesh_id)
                if key in stack or len(stack) >= _MAX_GRAPH_DEPTH:
                    raise ValueError("3MF enthaelt einen zyklischen oder zu tiefen Komponentengraphen")
                raw, _, objects = _read_model(archive, model_path, model_cache)
                matches = objects.get(mesh_id, [])
                if len(matches) != 1:
                    raise ValueError(f"3MF-Objekt {mesh_id} fehlt oder ist nicht eindeutig")
                node = matches[0]
                meshes = [child for child in node if _local(child.tag) == "mesh"]
                components = [
                    component for child in node if _local(child.tag) == "components"
                    for component in child if _local(component.tag) == "component"
                ]
                if len(meshes) > 1 or (meshes and components) or (not meshes and not components):
                    raise ValueError(f"3MF-Objekt {mesh_id} besitzt keine eindeutige Geometrie")
                if meshes:
                    if key not in mesh_cache:
                        mesh_cache[key] = _parse_mesh(raw, mesh_id)
                    vertices, triangles = mesh_cache[key]
                    triangle_total += len(triangles)
                    if triangle_total > _MAX_TRIANGLES or len(instances) >= _MAX_PARTS:
                        raise ValueError("3MF-Projekt ist fuer die Browser-Szene zu komplex")
                    part_info = inherited_part or object_info.get("parts", {}).get(mesh_id, {})
                    part_id = str(part_info.get("part_id") or mesh_id)
                    transformed = [_apply(transform, vertex) for vertex in vertices]
                    if not all(math.isfinite(value) for point in transformed for value in point):
                        raise ValueError("3MF-Transformation erzeugt ungueltige Koordinaten")
                    positions: list[float] = []
                    for triangle in triangles:
                        for vertex_index in triangle:
                            point = transformed[vertex_index]
                            positions.extend(point)
                            for axis in range(3):
                                bounds_min[axis] = min(bounds_min[axis], point[axis])
                                bounds_max[axis] = max(bounds_max[axis], point[axis])
                    identity = f"{object_id}:{part_id}"
                    if len(builds) > 1:
                        identity += f":instance:{instance_id}"
                    instances.append({
                        "id": identity,
                        "object_id": object_id,
                        "instance_id": instance_id,
                        "part_id": part_id,
                        "name": part_info.get("name") or object_info.get("name") or f"Teil {part_id}",
                        "extruder": int(part_info.get("extruder") or object_info.get("extruder") or 1),
                        "positions": positions,
                        "triangle_count": len(triangles),
                        "visible": True,
                        "_route": ".".join(str(index) for index in route) or "root",
                    })
                    return
                for index, component in enumerate(components):
                    child_id = str(component.attrib.get("objectid") or "")
                    path = next((value for name, value in component.attrib.items() if _local(name) == "path"), None)
                    child_path = _model_path(path, model_path)
                    part_info = inherited_part
                    if part_info is None:
                        part_info = object_info.get("parts", {}).get(child_id)
                    local_matrix = _matrix(component.attrib.get("transform"))
                    # Settings repeat Bambu part transforms. Apply their fallback
                    # once when this branch first acquires its part metadata.
                    if inherited_part is None and part_info is not None and _is_identity(local_matrix):
                        local_matrix = part_info.get("matrix", _IDENTITY)
                    combined = _multiply(transform, local_matrix)
                    if not all(math.isfinite(value) for value in combined):
                        raise ValueError("3MF-Transformation erzeugt ungueltige Koordinaten")
                    flatten(child_path, child_id, combined, (*stack, key), (*route, index), part_info)

            flatten(build_item["path"], object_id, build_item["matrix"], (), ())
            counts: dict[str, int] = {}
            for instance in instances[first_instance:]:
                counts[instance["id"]] = counts.get(instance["id"], 0) + 1
            for instance in instances[first_instance:]:
                route = instance.pop("_route")
                if counts[instance["id"]] > 1:
                    instance["id"] += f":component:{route}"

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
