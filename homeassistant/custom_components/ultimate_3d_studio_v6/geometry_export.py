"""Geometry-only STL export for single- and multi-document 3MF assets."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import math
from pathlib import PurePosixPath
import struct
from typing import Iterable
import xml.etree.ElementTree as ET
import zipfile

_MAX_TRIANGLES = 2_000_000
_IDENTITY = (
    1.0, 0.0, 0.0,
    0.0, 1.0, 0.0,
    0.0, 0.0, 1.0,
    0.0, 0.0, 0.0,
)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _local_attributes(element: ET.Element) -> dict[str, str]:
    return {_local_name(key): value for key, value in element.attrib.items()}


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) == name]


def _first_child(element: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in list(element) if _local_name(child.tag) == name), None)


def _parse_transform(raw: str | None) -> tuple[float, ...]:
    if not raw:
        return _IDENTITY
    values = tuple(float(value) for value in raw.split())
    if len(values) != 12:
        raise ValueError("Invalid 3MF transform")
    return values


def _apply(transform: tuple[float, ...], point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    return (
        x * transform[0] + y * transform[3] + z * transform[6] + transform[9],
        x * transform[1] + y * transform[4] + z * transform[7] + transform[10],
        x * transform[2] + y * transform[5] + z * transform[8] + transform[11],
    )


def _compose(first: tuple[float, ...], second: tuple[float, ...]) -> tuple[float, ...]:
    """Apply first, then second, preserving 3MF row-vector transform semantics."""
    origin = _apply(second, _apply(first, (0.0, 0.0, 0.0)))
    ex = _apply(second, _apply(first, (1.0, 0.0, 0.0)))
    ey = _apply(second, _apply(first, (0.0, 1.0, 0.0)))
    ez = _apply(second, _apply(first, (0.0, 0.0, 1.0)))
    return (
        ex[0] - origin[0], ex[1] - origin[1], ex[2] - origin[2],
        ey[0] - origin[0], ey[1] - origin[1], ey[2] - origin[2],
        ez[0] - origin[0], ez[1] - origin[1], ez[2] - origin[2],
        origin[0], origin[1], origin[2],
    )


def _normal(a: tuple[float, float, float], b: tuple[float, float, float], c: tuple[float, float, float]) -> tuple[float, float, float]:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    return (0.0, 0.0, 0.0) if length <= 1e-12 else (nx / length, ny / length, nz / length)


def _normalize_document_path(current_document: str, raw_path: str | None) -> str:
    if not raw_path:
        return current_document
    normalized = raw_path.replace("\\", "/")
    if normalized.startswith("/"):
        candidate = PurePosixPath(normalized.lstrip("/"))
    else:
        candidate = PurePosixPath(current_document).parent / normalized
    parts: list[str] = []
    for part in candidate.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError("3MF component path leaves package root")
            parts.pop()
            continue
        parts.append(part)
    if not parts:
        raise ValueError("Invalid 3MF component document path")
    return PurePosixPath(*parts).as_posix()


@dataclass(frozen=True)
class _Mesh:
    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class _Component:
    document: str
    object_id: str
    transform: tuple[float, ...]


@dataclass(frozen=True)
class _ObjectDefinition:
    mesh: _Mesh | None
    components: tuple[_Component, ...]


ObjectKey = tuple[str, str]


def _read_model_documents(payload: bytes) -> tuple[dict[str, ET.Element], str]:
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            model_names = sorted(
                (name.replace("\\", "/").lstrip("/") for name in archive.namelist() if name.lower().endswith(".model")),
                key=lambda name: (0 if name.casefold() == "3d/3dmodel.model" else 1, len(name), name.casefold()),
            )
            if not model_names:
                raise ValueError("3MF container has no model document")
            documents: dict[str, ET.Element] = {}
            actual_names = {name.replace("\\", "/").lstrip("/").casefold(): name for name in archive.namelist()}
            for normalized in model_names:
                archive_name = actual_names.get(normalized.casefold(), normalized)
                documents[normalized] = ET.fromstring(archive.read(archive_name))
            main = next((name for name in model_names if name.casefold() == "3d/3dmodel.model"), model_names[0])
            return documents, main
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid 3MF ZIP container") from exc
    except ET.ParseError as exc:
        raise ValueError("Invalid 3MF model XML") from exc


def _parse_objects(documents: dict[str, ET.Element]) -> dict[ObjectKey, _ObjectDefinition]:
    result: dict[ObjectKey, _ObjectDefinition] = {}
    known_documents = {name.casefold(): name for name in documents}
    for document_name, root in documents.items():
        resources = _first_child(root, "resources")
        if resources is None:
            continue
        for node in _children(resources, "object"):
            attributes = _local_attributes(node)
            object_id = str(attributes.get("id", "")).strip()
            if not object_id:
                continue
            mesh_node = _first_child(node, "mesh")
            mesh: _Mesh | None = None
            if mesh_node is not None:
                vertices_node = _first_child(mesh_node, "vertices")
                triangles_node = _first_child(mesh_node, "triangles")
                if vertices_node is not None and triangles_node is not None:
                    vertices = tuple(
                        (
                            float(_local_attributes(item)["x"]),
                            float(_local_attributes(item)["y"]),
                            float(_local_attributes(item)["z"]),
                        )
                        for item in _children(vertices_node, "vertex")
                    )
                    triangles = tuple(
                        (
                            int(_local_attributes(item)["v1"]),
                            int(_local_attributes(item)["v2"]),
                            int(_local_attributes(item)["v3"]),
                        )
                        for item in _children(triangles_node, "triangle")
                    )
                    mesh = _Mesh(vertices, triangles)
            components_node = _first_child(node, "components")
            components: tuple[_Component, ...] = ()
            if components_node is not None:
                parsed: list[_Component] = []
                for item in _children(components_node, "component"):
                    component_attributes = _local_attributes(item)
                    target_id = str(component_attributes.get("objectid", "")).strip()
                    if not target_id:
                        continue
                    target_document = _normalize_document_path(document_name, component_attributes.get("path"))
                    target_document = known_documents.get(target_document.casefold(), target_document)
                    parsed.append(_Component(
                        target_document,
                        target_id,
                        _parse_transform(component_attributes.get("transform")),
                    ))
                components = tuple(parsed)
            result[(document_name, object_id)] = _ObjectDefinition(mesh, components)
    if not result:
        raise ValueError("3MF model contains no objects")
    return result


def _build_items(main_document: str, root: ET.Element) -> list[_Component]:
    build = _first_child(root, "build")
    if build is None:
        return []
    result: list[_Component] = []
    for item in _children(build, "item"):
        attributes = _local_attributes(item)
        object_id = str(attributes.get("objectid", "")).strip()
        if not object_id:
            continue
        result.append(_Component(
            _normalize_document_path(main_document, attributes.get("path")),
            object_id,
            _parse_transform(attributes.get("transform")),
        ))
    return result


def _walk(
    objects: dict[ObjectKey, _ObjectDefinition],
    key: ObjectKey,
    transform: tuple[float, ...],
    stack: tuple[ObjectKey, ...] = (),
) -> Iterable[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]]:
    if key in stack:
        raise ValueError("Recursive 3MF component graph")
    definition = objects.get(key)
    if definition is None:
        raise ValueError(f"Missing 3MF object: {key[0]}#{key[1]}")
    if definition.mesh is not None:
        for v1, v2, v3 in definition.mesh.triangles:
            try:
                yield (
                    _apply(transform, definition.mesh.vertices[v1]),
                    _apply(transform, definition.mesh.vertices[v2]),
                    _apply(transform, definition.mesh.vertices[v3]),
                )
            except IndexError as exc:
                raise ValueError("Invalid 3MF triangle index") from exc
    for component in definition.components:
        yield from _walk(
            objects,
            (component.document, component.object_id),
            _compose(component.transform, transform),
            stack + (key,),
        )


def export_binary_stl(payload: bytes, label: str = "Ultimate 3D Studio V6 model") -> bytes:
    documents, main_document = _read_model_documents(payload)
    objects = _parse_objects(documents)
    build_items = _build_items(main_document, documents[main_document])
    if not build_items:
        build_items = [
            _Component(document, object_id, _IDENTITY)
            for document, object_id in objects
            if document == main_document
        ]
    triangles: list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]] = []
    known_documents = {name.casefold(): name for name in documents}
    for item in build_items:
        document = known_documents.get(item.document.casefold(), item.document)
        for triangle in _walk(objects, (document, item.object_id), item.transform):
            triangles.append(triangle)
            if len(triangles) > _MAX_TRIANGLES:
                raise ValueError("3MF model exceeds STL export triangle limit")
    if not triangles:
        raise ValueError("3MF model contains no printable triangles")
    result = bytearray(label.encode("ascii", errors="replace")[:80].ljust(80, b"\0"))
    result.extend(struct.pack("<I", len(triangles)))
    for a, b, c in triangles:
        nx, ny, nz = _normal(a, b, c)
        result.extend(struct.pack(
            "<12fH",
            nx, ny, nz,
            a[0], a[1], a[2],
            b[0], b[1], b[2],
            c[0], c[1], c[2],
            0,
        ))
    return bytes(result)
