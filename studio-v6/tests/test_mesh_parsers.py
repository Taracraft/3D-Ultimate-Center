import struct
import zipfile

from core.mesh_parsers import parse_3mf, parse_obj, parse_stl


def test_ascii_stl_parser(tmp_path) -> None:
    path = tmp_path / "triangle.stl"
    path.write_text(
        """solid triangle
facet normal 0 0 1
 outer loop
  vertex 0 0 0
  vertex 10 0 0
  vertex 0 10 0
 endloop
endfacet
endsolid triangle
""",
        encoding="utf-8",
    )
    metadata = parse_stl(path)
    assert metadata.triangle_count == 1
    assert metadata.bounds.maximum.x == 10.0
    assert metadata.candidate_faces[0].area == 50.0


def test_binary_stl_parser(tmp_path) -> None:
    path = tmp_path / "triangle-binary.stl"
    header = b"binary".ljust(80, b"\0") + struct.pack("<I", 1)
    triangle = struct.pack(
        "<12fH",
        0, 0, 1,
        0, 0, 0,
        10, 0, 0,
        0, 10, 0,
        0,
    )
    path.write_bytes(header + triangle)
    metadata = parse_stl(path)
    assert metadata.triangle_count == 1
    assert metadata.bounds.maximum.y == 10.0


def test_obj_parser_triangulates_polygon(tmp_path) -> None:
    path = tmp_path / "quad.obj"
    path.write_text(
        "\n".join(
            (
                "v 0 0 0",
                "v 10 0 0",
                "v 10 10 0",
                "v 0 10 0",
                "f 1 2 3 4",
            )
        ),
        encoding="utf-8",
    )
    metadata = parse_obj(path)
    assert metadata.triangle_count == 2
    assert metadata.candidate_faces[0].area == 100.0


def test_3mf_parser(tmp_path) -> None:
    path = tmp_path / "triangle.3mf"
    model = """<?xml version='1.0' encoding='UTF-8'?>
<model xmlns='http://schemas.microsoft.com/3dmanufacturing/core/2015/02' unit='millimeter'>
  <resources><object id='1' type='model'><mesh>
    <vertices>
      <vertex x='0' y='0' z='0'/>
      <vertex x='10' y='0' z='0'/>
      <vertex x='0' y='10' z='0'/>
    </vertices>
    <triangles><triangle v1='0' v2='1' v3='2'/></triangles>
  </mesh></object></resources>
</model>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("3D/3dmodel.model", model)
    metadata = parse_3mf(path)
    assert metadata.triangle_count == 1
    assert metadata.bounds.maximum.x == 10.0