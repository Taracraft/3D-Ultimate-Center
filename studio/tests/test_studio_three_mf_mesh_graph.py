from __future__ import annotations

from io import BytesIO
import importlib.util
from pathlib import Path
import sys
import struct
import zipfile

import pytest

COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "deploy/homeassistant/custom_components/ultimate_3d_studio"
)
SPEC = importlib.util.spec_from_file_location(
    "ultimate_3d_studio_three_mf_mesh_graph_test",
    COMPONENT / "three_mf_mesh_graph.py",
)
assert SPEC and SPEC.loader
GRAPH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GRAPH
SPEC.loader.exec_module(GRAPH)
logical_mesh_objects = GRAPH.logical_mesh_objects
mesh_instances = GRAPH.mesh_instances


def linked_model(component_path: str = "/3D/Objects/part.model") -> bytes:
    root = f"""<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
       xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
       requiredextensions="p">
  <resources>
    <object id="2" type="model"><components>
      <component objectid="1" p:path="{component_path}"
                 transform="1 0 0 0 1 0 0 0 1 0 20 0"/>
    </components></object>
  </resources>
  <build><item objectid="2" transform="1 0 0 0 1 0 0 0 1 10 0 30"/></build>
</model>"""
    nested = """<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <resources>
    <basematerials id="5"><base name="black" displaycolor="#000000"/></basematerials>
    <object id="1" name="linked-part" type="model" pid="5" pindex="0"><mesh>
      <vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/></vertices>
      <triangles><triangle v1="0" v2="1" v3="2"/></triangles>
    </mesh></object>
  </resources>
</model>"""
    target = BytesIO()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("3D/3dmodel.model", root)
        archive.writestr("3D/Objects/part.model", nested)
    return target.getvalue()


def test_linked_model_keeps_logical_id_color_and_composed_transform(tmp_path: Path) -> None:
    data = linked_model()
    assert logical_mesh_objects(data) == [("2", "#000000")]
    source = tmp_path / "linked.3mf"
    source.write_bytes(data)
    parts = mesh_instances(source)
    assert len(parts) == 1
    assert parts[0].logical_object_id == "2"
    assert parts[0].mesh_object_id == "1"
    assert parts[0].name == "linked-part"
    assert parts[0].triangles == ((0, 1, 2),)
    assert parts[0].triangle_material_indices == (None,)
    assert parts[0].vertices == (
        (10.0, 20.0, 30.0),
        (11.0, 20.0, 30.0),
        (10.0, 21.0, 30.0),
    )


def test_linked_model_rejects_archive_path_traversal() -> None:
    data = linked_model("../../Objects/part.model")
    with pytest.raises(ValueError, match="unsicheren Modellpfad"):
        logical_mesh_objects(data)


def test_single_filament_defaults_unassigned_linked_object_to_channel_one(
    tmp_path: Path,
) -> None:
    source = tmp_path / "linked.3mf"
    source.write_bytes(linked_model())
    spec = importlib.util.spec_from_file_location(
        "ultimate_3d_studio_materializer_single_filament_test",
        COMPONENT / "materialize-bambu-multimaterial.py",
    )
    assert spec and spec.loader
    materializer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = materializer
    spec.loader.exec_module(materializer)

    objects, triangles, paint_summary = materializer._extract_parts(
        source,
        tmp_path / "parts",
        {},
        default_channel=1,
        plate_width_mm=5,
        plate_depth_mm=5,
    )

    assert triangles == 1
    assert paint_summary == {"painted_triangle_count": 0, "painted_material_channel_count": 0}
    assert [item["filaments"] for item in objects] == [[1]]
    stl_files = list((tmp_path / "parts").glob("*.stl"))
    assert len(stl_files) == 1
    first_vertex = struct.unpack_from("<3f", stl_files[0].read_bytes(), 96)
    assert first_vertex == pytest.approx((2.0, 2.0, 30.0))


def test_painted_triangle_properties_split_native_assemble_parts(tmp_path: Path) -> None:
    model = """<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <resources>
    <basematerials id="1"><base name="red" displaycolor="#FF0000"/><base name="blue" displaycolor="#0000FF"/></basematerials>
    <object id="7" name="painted" type="model" pid="1" pindex="0"><mesh>
      <vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/><vertex x="1" y="1" z="0"/></vertices>
      <triangles><triangle v1="0" v2="1" v3="2" pid="1" p1="0"/><triangle v1="1" v2="3" v3="2" pid="1" p1="1"/></triangles>
    </mesh></object>
  </resources><build><item objectid="7"/></build>
</model>"""
    source = tmp_path / "painted.3mf"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("3D/3dmodel.model", model)
    parts = mesh_instances(source)
    assert parts[0].triangle_material_indices == (0, 1)
    spec = importlib.util.spec_from_file_location(
        "ultimate_3d_studio_materializer_painted_triangles_test",
        COMPONENT / "materialize-bambu-multimaterial.py",
    )
    assert spec and spec.loader
    materializer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = materializer
    spec.loader.exec_module(materializer)
    objects, triangles, paint_summary = materializer._extract_parts(
        source, tmp_path / "parts", {"7": 1}, material_channel_count=2,
        plate_width_mm=5, plate_depth_mm=5,
    )
    assert triangles == 2
    assert [item["filaments"] for item in objects] == [[1], [2]]
    assert paint_summary == {"painted_triangle_count": 2, "painted_material_channel_count": 2}
    assert len(list((tmp_path / "parts").glob("*.stl"))) == 2


def test_painted_triangle_rejects_inactive_material_channel(tmp_path: Path) -> None:
    model = """<?xml version="1.0" encoding="UTF-8"?>
<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><resources>
<basematerials id="1"><base name="red" displaycolor="#FF0000"/><base name="blue" displaycolor="#0000FF"/></basematerials>
<object id="7" type="model" pid="1" pindex="0"><mesh><vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/></vertices><triangles><triangle v1="0" v2="1" v3="2" pid="1" p1="1"/></triangles></mesh></object>
</resources><build><item objectid="7"/></build></model>"""
    source = tmp_path / "invalid-painted.3mf"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("3D/3dmodel.model", model)
    spec = importlib.util.spec_from_file_location(
        "ultimate_3d_studio_materializer_painted_channel_reject_test",
        COMPONENT / "materialize-bambu-multimaterial.py",
    )
    assert spec and spec.loader
    materializer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = materializer
    spec.loader.exec_module(materializer)
    with pytest.raises(ValueError, match="keinen aktiven Materialkanal"):
        materializer._extract_parts(
            source, tmp_path / "parts", {"7": 1}, material_channel_count=1,
            plate_width_mm=5, plate_depth_mm=5,
        )
