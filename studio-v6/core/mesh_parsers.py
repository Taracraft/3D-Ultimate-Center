"""Dependency-free mesh parsers for STL and OBJ plus 3MF metadata extraction."""

from __future__ import annotations

import math
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from .mesh import MeshFace, MeshMetadata
from .studio import Bounds3D, Vector3


@dataclass(slots=True)
class _Accumulator:
    triangle_count: int = 0
    vertex_count: int = 0
    min_x: float = math.inf
    min_y: float = math.inf
    min_z: float = math.inf
    max_x: float = -math.inf
    max_y: float = -math.inf
    max_z: float = -math.inf
    signed_volume: float = 0.0
    faces: list[MeshFace] | None = None

    def __post_init__(self) -> None:
        self.faces = []

    def add_triangle(self, a: Vector3, b: Vector3, c: Vector3) -> None:
        self.triangle_count += 1
        self.vertex_count += 3
        for point in (a, b, c):
            self.min_x = min(self.min_x, point.x)
            self.min_y = min(self.min_y, point.y)
            self.min_z = min(self.min_z, point.z)
            self.max_x = max(self.max_x, point.x)
            self.max_y = max(self.max_y, point.y)
            self.max_z = max(self.max_z, point.z)

        ab = Vector3(b.x - a.x, b.y - a.y, b.z - a.z)
        ac = Vector3(c.x - a.x, c.y - a.y, c.z - a.z)
        cross = Vector3(
            ab.y * ac.z - ab.z * ac.y,
            ab.z * ac.x - ab.x * ac.z,
            ab.x * ac.y - ab.y * ac.x,
        )
        magnitude = math.sqrt(cross.x**2 + cross.y**2 + cross.z**2)
        if magnitude > 0:
            normal = Vector3(cross.x / magnitude, cross.y / magnitude, cross.z / magnitude)
            area = magnitude / 2.0
            centroid = Vector3(
                (a.x + b.x + c.x) / 3.0,
                (a.y + b.y + c.y) / 3.0,
                (a.z + b.z + c.z) / 3.0,
            )
            self.faces.append(MeshFace(normal=normal, area=area, centroid=centroid))

        self.signed_volume += (
            a.x * (b.y * c.z - b.z * c.y)
            - a.y * (b.x * c.z - b.z * c.x)
            + a.z * (b.x * c.y - b.y * c.x)
        ) / 6.0

    def metadata(self) -> MeshMetadata:
        if self.triangle_count == 0:
            raise ValueError("mesh contains no triangles")
        return MeshMetadata(
            triangle_count=self.triangle_count,
            vertex_count=self.vertex_count,
            bounds=Bounds3D(
                minimum=Vector3(self.min_x, self.min_y, self.min_z),
                maximum=Vector3(self.max_x, self.max_y, self.max_z),
            ),
            volume_mm3=abs(self.signed_volume),
            manifold=None,
            watertight=None,
            candidate_faces=_merge_coplanar_faces(tuple(self.faces)),
        )


def parse_mesh(path: str | Path) -> MeshMetadata:
    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix == ".stl":
        return parse_stl(source)
    if suffix == ".obj":
        return parse_obj(source)
    if suffix == ".3mf":
        return parse_3mf(source)
    raise ValueError(f"unsupported mesh format: {suffix or '<none>'}")


def _is_binary_stl(header: bytes) -> bool:
    """Detect binary STL: ASCII STL headers start with 'solid' keyword."""
    text = header[:80].decode('ascii', errors='ignore')
    return not text.strip().startswith('solid')


def parse_stl(path: str | Path) -> MeshMetadata:
    source = Path(path)
    with source.open("rb") as stream:
        header = stream.read(84)
    if len(header) < 84:
        raise ValueError("STL file too small")
    if _is_binary_stl(header):
        count = struct.unpack_from("<I", header, 80)[0]
        return _parse_binary_stl(source, count)
    return _parse_ascii_stl(source)


def _parse_binary_stl(path: Path, triangle_count: int) -> MeshMetadata:
    accumulator = _Accumulator()
    with path.open("rb") as stream:
        stream.seek(84)
        for _ in range(triangle_count):
            record = stream.read(50)
            if len(record) != 50:
                raise ValueError("truncated binary STL")
            values = struct.unpack("<12fH", record)
            a = Vector3(values[3], values[4], values[5])
            b = Vector3(values[6], values[7], values[8])
            c = Vector3(values[9], values[10], values[11])
            accumulator.add_triangle(a, b, c)
    return accumulator.metadata()


def _parse_ascii_stl(path: Path) -> MeshMetadata:
    accumulator = _Accumulator()
    vertices: list[Vector3] = []
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line.startswith("vertex "):
            continue
        parts = line.split()
        if len(parts) != 4:
            continue
        vertices.append(Vector3(float(parts[1]), float(parts[2]), float(parts[3])))
        if len(vertices) == 3:
            accumulator.add_triangle(vertices[0], vertices[1], vertices[2])
            vertices.clear()
    return accumulator.metadata()


def parse_obj(path: str | Path) -> MeshMetadata:
    vertices: list[Vector3] = []
    accumulator = _Accumulator()
    for raw_line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if line.startswith("v "):
            parts = line.split()
            if len(parts) >= 4:
                vertices.append(Vector3(float(parts[1]), float(parts[2]), float(parts[3])))
        elif line.startswith("f "):
            indexes = []
            for token in line.split()[1:]:
                raw_index = token.split("/", 1)[0]
                index = int(raw_index)
                indexes.append(index - 1 if index > 0 else len(vertices) + index)
            for offset in range(1, len(indexes) - 1):
                accumulator.add_triangle(
                    vertices[indexes[0]],
                    vertices[indexes[offset]],
                    vertices[indexes[offset + 1]],
                )
    return accumulator.metadata()


def parse_3mf(path: str | Path) -> MeshMetadata:
    accumulator = _Accumulator()
    with zipfile.ZipFile(path) as archive:
        model_names = [name for name in archive.namelist() if name.endswith(".model")]
        if not model_names:
            raise ValueError("3MF archive contains no model document")
        root = ElementTree.fromstring(archive.read(model_names[0]))
    namespace = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    for mesh in root.findall(".//m:mesh", namespace):
        vertices = [
            Vector3(float(node.attrib["x"]), float(node.attrib["y"]), float(node.attrib["z"]))
            for node in mesh.findall("./m:vertices/m:vertex", namespace)
        ]
        for triangle in mesh.findall("./m:triangles/m:triangle", namespace):
            accumulator.add_triangle(
                vertices[int(triangle.attrib["v1"])],
                vertices[int(triangle.attrib["v2"])],
                vertices[int(triangle.attrib["v3"])],
            )
    return accumulator.metadata()


def _merge_coplanar_faces(faces: tuple[MeshFace, ...]) -> tuple[MeshFace, ...]:
    groups: dict[tuple[int, int, int], list[MeshFace]] = {}
    for face in faces:
        key = (
            round(face.normal.x * 1000),
            round(face.normal.y * 1000),
            round(face.normal.z * 1000),
        )
        groups.setdefault(key, []).append(face)

    merged: list[MeshFace] = []
    for grouped in groups.values():
        total_area = sum(face.area for face in grouped)
        if total_area <= 0:
            continue
        centroid = Vector3(
            sum(face.centroid.x * face.area for face in grouped) / total_area,
            sum(face.centroid.y * face.area for face in grouped) / total_area,
            sum(face.centroid.z * face.area for face in grouped) / total_area,
        )
        merged.append(
            MeshFace(
                normal=grouped[0].normal,
                area=total_area,
                centroid=centroid,
            )
        )
    return tuple(sorted(merged, key=lambda face: face.area, reverse=True)[:64])
