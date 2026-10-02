"""Resolve logical objects and linked mesh instances in production 3MF files."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import math
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET
import zipfile


CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PRODUCTION_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
NS = {"m": CORE_NS}
ROOT_MODEL = "3D/3dmodel.model"
MAX_MODEL_PARTS = 4096
MAX_GRAPH_DEPTH = 32

Matrix = tuple[tuple[float, float, float, float], ...]


@dataclass(frozen=True, slots=True)
class MeshInstance:
    """One flattened mesh with its top-level logical object identity."""

    logical_object_id: str
    mesh_object_id: str
    name: str
    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]


_IDENTITY: Matrix = (
    (1.0, 0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)


def _archive_path(value: object, *, default: str = ROOT_MODEL) -> str:
    raw = str(value or default).strip().replace("\\", "/").lstrip("/")
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise ValueError("Die 3MF enthält einen unsicheren Modellpfad.")
    normalized = str(path)
    if not normalized.casefold().startswith("3d/") or not normalized.casefold().endswith(".model"):
        raise ValueError("Die 3MF verweist auf ein ungültiges Produktionsmodell.")
    return normalized


def _matrix(value: object) -> Matrix:
    raw = str(value or "").strip()
    if not raw:
        return _IDENTITY
    try:
        values = [float(item) for item in raw.split()]
    except ValueError as exc:
        raise ValueError("Die 3MF enthält eine ungültige Objekttransformation.") from exc
    if len(values) != 12 or not all(math.isfinite(item) for item in values):
        raise ValueError("Die 3MF enthält eine ungültige Objekttransformation.")
    a, b, c, d, e, f, g, h, i, j, k, l = values
    return (
        (a, b, c, 0.0),
        (d, e, f, 0.0),
        (g, h, i, 0.0),
        (j, k, l, 1.0),
    )


def _multiply(left: Matrix, right: Matrix) -> Matrix:
    return tuple(
        tuple(
            sum(left[row][index] * right[index][column] for index in range(4))
            for column in range(4)
        )
        for row in range(4)
    )


def _transform(vertex: tuple[float, float, float], matrix: Matrix) -> tuple[float, float, float]:
    x, y, z = vertex
    return (
        x * matrix[0][0] + y * matrix[1][0] + z * matrix[2][0] + matrix[3][0],
        x * matrix[0][1] + y * matrix[1][1] + z * matrix[2][1] + matrix[3][1],
        x * matrix[0][2] + y * matrix[1][2] + z * matrix[2][2] + matrix[3][2],
    )


def _production_path(element: ET.Element) -> str | None:
    return element.attrib.get(f"{{{PRODUCTION_NS}}}path") or next(
        (value for key, value in element.attrib.items() if key.rsplit("}", 1)[-1] == "path"),
        None,
    )


def _model_root(archive: zipfile.ZipFile, path: str, cache: dict[str, ET.Element]) -> ET.Element:
    normalized = _archive_path(path)
    if normalized not in cache:
        try:
            cache[normalized] = ET.fromstring(archive.read(normalized))
        except KeyError as exc:
            raise ValueError(f"Das verknüpfte 3MF-Modell '{normalized}' fehlt.") from exc
        except ET.ParseError as exc:
            raise ValueError(f"Das verknüpfte 3MF-Modell '{normalized}' ist ungültig.") from exc
    return cache[normalized]


def _object_map(root: ET.Element) -> dict[str, ET.Element]:
    return {
        str(item.attrib.get("id") or ""): item
        for item in root.findall("m:resources/m:object", NS)
        if str(item.attrib.get("id") or "")
    }


def _object_color(root: ET.Element, item: ET.Element) -> str:
    group_id = str(item.attrib.get("pid") or "")
    index = str(item.attrib.get("pindex") or "")
    if not group_id or not index:
        return ""
    group = next(
        (node for node in root.findall("m:resources/m:basematerials", NS) if str(node.attrib.get("id") or "") == group_id),
        None,
    )
    if group is None:
        return ""
    try:
        base = group.findall("m:base", NS)[int(index)]
    except (ValueError, IndexError):
        return ""
    return str(base.attrib.get("displaycolor") or "")


def _logical_elements(root: ET.Element) -> list[ET.Element]:
    objects = _object_map(root)
    result: list[ET.Element] = []
    seen: set[str] = set()
    for build_item in root.findall("m:build/m:item", NS):
        object_id = str(build_item.attrib.get("objectid") or "")
        item = objects.get(object_id)
        if item is not None and object_id not in seen:
            result.append(item)
            seen.add(object_id)
    for object_id, item in objects.items():
        if object_id not in seen and (
            item.find("m:mesh", NS) is not None
            or item.find("m:components", NS) is not None
        ):
            result.append(item)
    return result


def logical_mesh_objects(data: bytes) -> list[tuple[str, str]]:
    """Return top-level assignable object IDs and their unambiguous color."""
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            cache: dict[str, ET.Element] = {}
            root = _model_root(archive, ROOT_MODEL, cache)
            result: list[tuple[str, str]] = []
            for item in _logical_elements(root):
                object_id = str(item.attrib.get("id") or "")
                colors: set[str] = set()

                def collect(model_path: str, node: ET.Element, stack: tuple[tuple[str, str], ...]) -> None:
                    key = (model_path, str(node.attrib.get("id") or ""))
                    if key in stack or len(stack) >= MAX_GRAPH_DEPTH:
                        raise ValueError("Die 3MF enthält einen zyklischen Objektgraphen.")
                    model_root = _model_root(archive, model_path, cache)
                    color = _object_color(model_root, node)
                    if color:
                        colors.add(color)
                    objects = _object_map(model_root)
                    for component in node.findall("m:components/m:component", NS):
                        child_path = _archive_path(_production_path(component), default=model_path)
                        child_root = _model_root(archive, child_path, cache)
                        child = _object_map(child_root).get(str(component.attrib.get("objectid") or ""))
                        if child is None:
                            raise ValueError("Die 3MF verweist auf ein fehlendes Komponentenobjekt.")
                        collect(child_path, child, (*stack, key))

                collect(ROOT_MODEL, item, ())
                result.append((object_id, next(iter(colors)) if len(colors) == 1 else ""))
            return result
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("Die 3MF-Geometrie konnte nicht gelesen werden.") from exc


def mesh_instances(input_3mf: Path) -> list[MeshInstance]:
    """Flatten direct and production-extension meshes with composed transforms."""
    try:
        with zipfile.ZipFile(input_3mf) as archive:
            cache: dict[str, ET.Element] = {}
            root = _model_root(archive, ROOT_MODEL, cache)
            objects = _object_map(root)
            build_items = root.findall("m:build/m:item", NS)
            starts: list[tuple[str, ET.Element, Matrix]] = []
            for build_item in build_items:
                object_id = str(build_item.attrib.get("objectid") or "")
                item = objects.get(object_id)
                if item is not None:
                    starts.append((object_id, item, _matrix(build_item.attrib.get("transform"))))
            if not starts:
                starts = [
                    (str(item.attrib.get("id") or ""), item, _IDENTITY)
                    for item in _logical_elements(root)
                ]

            result: list[MeshInstance] = []

            def flatten(
                logical_id: str,
                model_path: str,
                node: ET.Element,
                transform: Matrix,
                stack: tuple[tuple[str, str], ...],
            ) -> None:
                key = (model_path, str(node.attrib.get("id") or ""))
                if key in stack or len(stack) >= MAX_GRAPH_DEPTH:
                    raise ValueError("Die 3MF enthält einen zyklischen Objektgraphen.")
                mesh = node.find("m:mesh", NS)
                if mesh is not None:
                    vertices = tuple(
                        _transform(
                            (float(item.attrib["x"]), float(item.attrib["y"]), float(item.attrib["z"])),
                            transform,
                        )
                        for item in mesh.findall("m:vertices/m:vertex", NS)
                    )
                    triangles = tuple(
                        (int(item.attrib["v1"]), int(item.attrib["v2"]), int(item.attrib["v3"]))
                        for item in mesh.findall("m:triangles/m:triangle", NS)
                    )
                    if not vertices or not triangles:
                        raise ValueError("Die 3MF enthält ein leeres Meshobjekt.")
                    result.append(MeshInstance(
                        logical_object_id=logical_id,
                        mesh_object_id=str(node.attrib.get("id") or ""),
                        name=str(node.attrib.get("name") or f"Objekt {logical_id}"),
                        vertices=vertices,
                        triangles=triangles,
                    ))
                    if len(result) > MAX_MODEL_PARTS:
                        raise ValueError("Die 3MF enthält zu viele Meshobjekte.")
                model_root = _model_root(archive, model_path, cache)
                for component in node.findall("m:components/m:component", NS):
                    child_path = _archive_path(_production_path(component), default=model_path)
                    child_root = _model_root(archive, child_path, cache)
                    child = _object_map(child_root).get(str(component.attrib.get("objectid") or ""))
                    if child is None:
                        raise ValueError("Die 3MF verweist auf ein fehlendes Komponentenobjekt.")
                    combined = _multiply(_matrix(component.attrib.get("transform")), transform)
                    flatten(logical_id, child_path, child, combined, (*stack, key))

            for logical_id, item, transform in starts:
                flatten(logical_id, ROOT_MODEL, item, transform, ())
            if not result:
                raise ValueError("Die 3MF enthält keine Meshobjekte.")
            return result
    except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("Die 3MF-Geometrie konnte nicht gelesen werden.") from exc