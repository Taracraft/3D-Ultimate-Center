import struct
from pathlib import Path
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


def _write_large_stl(path: Path, triangle_count: int = 50_000) -> None:
    """Create deterministic parser input inside the test's isolated directory."""
    header = b"Large STL test model for performance testing".ljust(80, b"\0")
    triangle = struct.Struct("<12fH")
    with path.open("xb") as stream:
        stream.write(header)
        stream.write(struct.pack("<I", triangle_count))
        for index in range(triangle_count):
            z = (index / 500) * 0.2
            stream.write(triangle.pack(0, 0, 1, 0, 0, z, 0.5, 0, z, 0, 0.5, z, 0))


def test_large_stl_from_file(tmp_path: Path) -> None:
    """Test parsing of a large STL file with 50000 triangles."""
    from core.mesh_parsers import parse_stl
    
    stl_path = tmp_path / "large_model.stl"
    _write_large_stl(stl_path)
    assert stl_path.stat().st_size == 84 + 50_000 * 50
    
    metadata = parse_stl(stl_path)
    
    # Should have all triangles
    assert metadata.triangle_count == 50000
    assert metadata.vertex_count == 150000
    
    # Bounds should be reasonable
    assert metadata.bounds.minimum.x >= 0
    assert metadata.bounds.maximum.x <= 1.0
    assert metadata.bounds.minimum.y >= 0
    assert metadata.bounds.maximum.y <= 1.0
    # Z should span about 20mm (50000 triangles / 500 per layer * 0.2mm)
    assert metadata.bounds.maximum.z > 10.0
    assert metadata.bounds.minimum.z == 0.0
    
    # candidate_faces are coplanar-merged, so fewer than 50000
    assert len(metadata.candidate_faces) > 0
    assert sum(face.area for face in metadata.candidate_faces) > 0


def test_large_stl_performance(tmp_path: Path) -> None:
    """Test parsing of 50000 triangles spanning approximately 20 millimeters."""
    import struct
    from core.mesh_parsers import parse_stl
    
    stl_path = tmp_path / "large_model_test.stl"
    _write_large_stl(stl_path)
    assert stl_path.stat().st_size == 84 + 50_000 * 50

    metadata = parse_stl(stl_path)
    
    # Should have all triangles
    assert metadata.triangle_count == 50000
    assert metadata.vertex_count == 150000
    
    # Bounds should be reasonable (1mm x 1mm x ~20mm)
    assert metadata.bounds.minimum.x >= 0
    assert metadata.bounds.maximum.x <= 1.0
    assert metadata.bounds.minimum.y >= 0
    assert metadata.bounds.maximum.y <= 1.0
    # Z should span about 20mm (50000 / 500 * 0.2)
    assert metadata.bounds.maximum.z > 15.0
    assert metadata.bounds.minimum.z == 0.0
    
    # candidate_faces are coplanar-merged, so fewer than 50000
    assert len(metadata.candidate_faces) > 0
    total_area = sum(face.area for face in metadata.candidate_faces)
    assert total_area > 0


def test_large_stl_fixture_is_deterministic_and_exactly_sized(tmp_path: Path) -> None:
    first, second = tmp_path / "first.stl", tmp_path / "second.stl"
    _write_large_stl(first, triangle_count=10)
    _write_large_stl(second, triangle_count=10)
    assert first.read_bytes() == second.read_bytes()
    assert first.stat().st_size == 84 + 10 * 50
    assert struct.unpack_from("<I", first.read_bytes(), 80)[0] == 10
    assert parse_stl(first).triangle_count == 10
