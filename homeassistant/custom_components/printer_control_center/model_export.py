"""Export geometry-only STL and 3MF payloads from uploaded 3MF containers."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import math
import struct
from typing import Iterable
import xml.etree.ElementTree as ET
import zipfile

_MAX_TRIANGLES = 2_000_000

# 3MF transform matrix order:
# m00 m01 m02 m10 m11 m12 m20 m21 m22 m30 m31 m32
# Coordinates are treated as row vectors according to the 3MF specification.
_IDENTITY = (
    1.0, 0.0, 0.0,
    0.0, 1.0, 0.0,
    0.0, 0.0, 1.0,
    0.0, 0.0, 0.0,
)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [
        child
        for child in list(element)
        if _local_name(child.tag) == name
    ]


def _first_child(element: ET.Element, name: str) -> ET.Element | None:
    for child in list(element):
        if _local_name(child.tag) == name:
            return child
    return None


def _parse_transform(raw: str | None) -> tuple[float, ...]:
    if not raw:
        return _IDENTITY
    values = [float(value) for value in raw.split()]
    if len(values) != 12:
        raise ValueError("Invalid 3MF transform")
    return tuple(values)


def _apply(
    transform: tuple[float, ...],
    point: tuple[float, float, float],
) -> tuple[float, float, float]:
    x, y, z = point
    return (
        x * transform[0] + y * transform[3] + z * transform[6] + transform[9],
        x * transform[1] + y * transform[4] + z * transform[7] + transform[10],
        x * transform[2] + y * transform[5] + z * transform[8] + transform[11],
    )


def _compose(
    first: tuple[float, ...],
    second: tuple[float, ...],
) -> tuple[float, ...]:
    """Return a transform that applies first and then second."""
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


def _normal(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
) -> tuple[float, float, float]:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 1e-12:
        return (0.0, 0.0, 0.0)
    return (nx / length, ny / length, nz / length)


@dataclass(frozen=True)
class Mesh:
    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class Component:
    object_id: str
    transform: tuple[float, ...]


@dataclass(frozen=True)
class ObjectDefinition:
    mesh: Mesh | None
    components: tuple[Component, ...]


def _read_model_xml(payload: bytes) -> ET.Element:
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            model_names = sorted(
                (
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(".model")
                ),
                key=lambda name: (
                    0 if name.lower() == "3d/3dmodel.model" else 1,
                    len(name),
                ),
            )
            if not model_names:
                raise ValueError("3MF container has no .model document")
            return ET.fromstring(archive.read(model_names[0]))
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid 3MF ZIP container") from exc
    except ET.ParseError as exc:
        raise ValueError("Invalid 3MF model XML") from exc


def _parse_objects(root: ET.Element) -> dict[str, ObjectDefinition]:
    resources = _first_child(root, "resources")
    if resources is None:
        raise ValueError("3MF resources section is missing")

    objects: dict[str, ObjectDefinition] = {}

    for object_node in _children(resources, "object"):
        object_id = str(object_node.attrib.get("id", "")).strip()
        if not object_id:
            continue

        mesh_node = _first_child(object_node, "mesh")
        mesh: Mesh | None = None

        if mesh_node is not None:
            vertices_node = _first_child(mesh_node, "vertices")
            triangles_node = _first_child(mesh_node, "triangles")
            if vertices_node is not None and triangles_node is not None:
                vertices = tuple(
                    (
                        float(vertex.attrib["x"]),
                        float(vertex.attrib["y"]),
                        float(vertex.attrib["z"]),
                    )
                    for vertex in _children(vertices_node, "vertex")
                )
                triangles = tuple(
                    (
                        int(triangle.attrib["v1"]),
                        int(triangle.attrib["v2"]),
                        int(triangle.attrib["v3"]),
                    )
                    for triangle in _children(triangles_node, "triangle")
                )
                mesh = Mesh(vertices=vertices, triangles=triangles)

        components_node = _first_child(object_node, "components")
        components: tuple[Component, ...] = ()

        if components_node is not None:
            components = tuple(
                Component(
                    object_id=str(component.attrib.get("objectid", "")).strip(),
                    transform=_parse_transform(component.attrib.get("transform")),
                )
                for component in _children(components_node, "component")
                if str(component.attrib.get("objectid", "")).strip()
            )

        objects[object_id] = ObjectDefinition(
            mesh=mesh,
            components=components,
        )

    if not objects:
        raise ValueError("3MF model contains no objects")

    return objects


def _build_items(root: ET.Element) -> list[Component]:
    build = _first_child(root, "build")
    if build is None:
        return []

    return [
        Component(
            object_id=str(item.attrib.get("objectid", "")).strip(),
            transform=_parse_transform(item.attrib.get("transform")),
        )
        for item in _children(build, "item")
        if str(item.attrib.get("objectid", "")).strip()
    ]


def _walk_object(
    objects: dict[str, ObjectDefinition],
    object_id: str,
    transform: tuple[float, ...],
    *,
    stack: tuple[str, ...] = (),
) -> Iterable[tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]]:
    if object_id in stack:
        raise ValueError("Recursive 3MF component graph")
    definition = objects.get(object_id)
    if definition is None:
        raise ValueError(f"Missing 3MF object: {object_id}")

    if definition.mesh is not None:
        mesh = definition.mesh
        for v1, v2, v3 in mesh.triangles:
            try:
                yield (
                    _apply(transform, mesh.vertices[v1]),
                    _apply(transform, mesh.vertices[v2]),
                    _apply(transform, mesh.vertices[v3]),
                )
            except IndexError as exc:
                raise ValueError("Invalid 3MF triangle vertex index") from exc

    for component in definition.components:
        yield from _walk_object(
            objects,
            component.object_id,
            _compose(component.transform, transform),
            stack=stack + (object_id,),
        )


def export_binary_stl(payload: bytes, *, label: str = "3D-Printer Control Center model") -> bytes:
    """Return a geometry-only binary STL representation of a 3MF payload."""
    root = _read_model_xml(payload)
    objects = _parse_objects(root)
    build_items = _build_items(root)

    if not build_items:
        build_items = [
            Component(object_id=object_id, transform=_IDENTITY)
            for object_id in objects
        ]

    triangles: list[tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]] = []

    for item in build_items:
        for triangle in _walk_object(objects, item.object_id, item.transform):
            triangles.append(triangle)
            if len(triangles) > _MAX_TRIANGLES:
                raise ValueError("3MF model exceeds STL export triangle limit")

    if not triangles:
        raise ValueError("3MF model contains no printable triangles")

    header = label.encode("ascii", errors="replace")[:80].ljust(80, b"\0")
    result = bytearray(header)
    result.extend(struct.pack("<I", len(triangles)))

    for a, b, c in triangles:
        nx, ny, nz = _normal(a, b, c)
        result.extend(
            struct.pack(
                "<12fH",
                nx, ny, nz,
                a[0], a[1], a[2],
                b[0], b[1], b[2],
                c[0], c[1], c[2],
                0,
            )
        )

    return bytes(result)



def _geometry_triangles(payload: bytes) -> list[tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]]:
    """Flatten a source 3MF build graph into geometry-only triangles."""
    root = _read_model_xml(payload)
    objects = _parse_objects(root)
    build_items = _build_items(root)

    if not build_items:
        build_items = [
            Component(object_id=object_id, transform=_IDENTITY)
            for object_id in objects
        ]

    triangles: list[tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]] = []

    for item in build_items:
        for triangle in _walk_object(objects, item.object_id, item.transform):
            triangles.append(triangle)
            if len(triangles) > _MAX_TRIANGLES:
                raise ValueError("3MF model exceeds export triangle limit")

    if not triangles:
        raise ValueError("3MF model contains no printable triangles")

    return triangles


def export_geometry_only_3mf(payload: bytes, *, label: str = "3D-Printer Control Center model") -> bytes:
    """Return a minimal geometry-only 3MF container suitable for slicer import."""
    triangles = _geometry_triangles(payload)

    vertices: list[tuple[float, float, float]] = []
    vertex_indices: dict[tuple[float, float, float], int] = {}
    indexed_triangles: list[tuple[int, int, int]] = []

    def vertex_index(point: tuple[float, float, float]) -> int:
        index = vertex_indices.get(point)
        if index is None:
            index = len(vertices)
            vertices.append(point)
            vertex_indices[point] = index
        return index

    for a, b, c in triangles:
        indexed_triangles.append((vertex_index(a), vertex_index(b), vertex_index(c)))

    namespace = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    xml_namespace = "http://www.w3.org/XML/1998/namespace"
    ET.register_namespace("", namespace)

    model = ET.Element(
        f"{{{namespace}}}model",
        {
            "unit": "millimeter",
            f"{{{xml_namespace}}}lang": "en-US",
        },
    )
    metadata = ET.SubElement(model, f"{{{namespace}}}metadata", {"name": "Title"})
    metadata.text = label
    resources = ET.SubElement(model, f"{{{namespace}}}resources")
    obj = ET.SubElement(resources, f"{{{namespace}}}object", {"id": "1", "type": "model"})
    mesh = ET.SubElement(obj, f"{{{namespace}}}mesh")
    xml_vertices = ET.SubElement(mesh, f"{{{namespace}}}vertices")
    for x, y, z in vertices:
        ET.SubElement(
            xml_vertices,
            f"{{{namespace}}}vertex",
            {"x": repr(x), "y": repr(y), "z": repr(z)},
        )
    xml_triangles = ET.SubElement(mesh, f"{{{namespace}}}triangles")
    for v1, v2, v3 in indexed_triangles:
        ET.SubElement(
            xml_triangles,
            f"{{{namespace}}}triangle",
            {"v1": str(v1), "v2": str(v2), "v3": str(v3)},
        )
    build = ET.SubElement(model, f"{{{namespace}}}build")
    ET.SubElement(build, f"{{{namespace}}}item", {"objectid": "1"})

    model_xml = ET.tostring(model, encoding="utf-8", xml_declaration=True)
    content_types = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        b'<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        b'</Types>'
    )
    relationships = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        b'</Relationships>'
    )

    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("3D/3dmodel.model", model_xml)
    return output.getvalue()