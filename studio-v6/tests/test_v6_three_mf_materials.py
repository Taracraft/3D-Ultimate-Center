"""Regression tests for safe V6 multimaterial 3MF rewriting."""

from __future__ import annotations

from io import BytesIO
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
MATERIALS_PATH = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
    / "three_mf_materials.py"
)


def _load_materials_module():
    spec = importlib.util.spec_from_file_location(
        "v6_three_mf_materials",
        MATERIALS_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _archive(files: dict[str, bytes | str]) -> bytes:
    memory = BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(
                name,
                content.encode("utf-8") if isinstance(content, str) else content,
            )
    return memory.getvalue()


def _read_member(data: bytes, name: str) -> bytes:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        return archive.read(name)


def _metadata_value(element: ET.Element, key: str) -> str | None:
    for child in element:
        if child.tag.rsplit("}", 1)[-1].casefold() != "metadata":
            continue
        child_key = str(child.attrib.get("key") or child.attrib.get("name") or "")
        if child_key.casefold() == key.casefold():
            return str(child.attrib.get("value") or child.text or "")
    return None


def test_material_plan_rewrites_object_and_part_extruders() -> None:
    materials = _load_materials_module()
    source = _archive({
        "[Content_Types].xml": "<Types/>",
        "3D/3dmodel.model": "<model/>",
        "Metadata/model_settings.config": """
            <config>
              <object id="10">
                <metadata key="name" value="Gehäuse"/>
                <part id="10-1">
                  <metadata key="name" value="Logo"/>
                </part>
              </object>
            </config>
        """,
        "Metadata/project_settings.config": "{}",
    })

    filename, rewritten, summary = materials.apply_material_plan(
        "project.3mf",
        source,
        {
            "assignments": {"10": 2, "10-1": 3},
            "filaments": [],
            "purge_tower": {},
        },
    )

    assert filename == "project-v6-multimaterial.3mf"
    assert summary == {
        "applied": True,
        "assignment_count": 2,
        "filament_count": 0,
        "purge_tower_enabled": False,
    }
    root = ET.fromstring(_read_member(rewritten, "Metadata/model_settings.config"))
    object_node = next(element for element in root.iter() if element.attrib.get("id") == "10")
    part_node = next(element for element in root.iter() if element.attrib.get("id") == "10-1")
    assert _metadata_value(object_node, "extruder") == "2"
    assert _metadata_value(part_node, "extruder") == "3"


def test_filaments_and_purge_tower_are_written_to_project_settings() -> None:
    materials = _load_materials_module()
    source = _archive({
        "[Content_Types].xml": "<Types/>",
        "3D/3dmodel.model": "<model/>",
        "Metadata/model_settings.config": "<config/>",
    })

    _filename, rewritten, summary = materials.apply_material_plan(
        "colors.3mf",
        source,
        {
            "assignments": {},
            "filaments": [
                {"name": "PLA Rot", "material": "PLA", "color": "#FF0000"},
                {"name": "PETG Blau", "material": "PETG", "color": "0000FF"},
            ],
            "purge_tower": {
                "enabled": True,
                "width_mm": 42,
                "brim_width_mm": 3.5,
                "position_x": 215,
                "position_y": 190,
                "flush_multiplier": 1.25,
                "flush_volumes_matrix": [0, 120, 140, 0],
                "flush_volumes_vector": [120, 140],
            },
        },
    )

    settings = json.loads(
        _read_member(rewritten, "Metadata/project_settings.config").decode("utf-8")
    )
    assert settings["filament_colour"] == ["#FF0000FF", "#0000FFFF"]
    assert settings["filament_type"] == ["PLA", "PETG"]
    assert settings["filament_settings_id"] == ["PLA Rot", "PETG Blau"]
    assert settings["enable_prime_tower"] == "1"
    assert settings["prime_tower_width"] == "42.0"
    assert settings["prime_tower_brim_width"] == "3.5"
    assert settings["wipe_tower_x"] == "215.0"
    assert settings["wipe_tower_y"] == "190.0"
    assert settings["flush_multiplier"] == "1.25"
    assert settings["flush_volumes_matrix"] == [0, 120, 140, 0]
    assert settings["flush_volumes_vector"] == [120, 140]
    assert summary["filament_count"] == 2
    assert summary["purge_tower_enabled"] is True


def test_non_3mf_and_empty_plan_are_left_unchanged() -> None:
    materials = _load_materials_module()
    source = b"solid test\nendsolid test\n"

    filename, rewritten, summary = materials.apply_material_plan(
        "model.stl",
        source,
        {"assignments": {"1": 2}},
    )

    assert filename == "model.stl"
    assert rewritten == source
    assert summary == {"applied": False, "assignment_count": 0}


def test_missing_model_settings_rejects_assignments() -> None:
    materials = _load_materials_module()
    source = _archive({
        "[Content_Types].xml": "<Types/>",
        "3D/3dmodel.model": "<model/>",
    })

    try:
        materials.apply_material_plan(
            "broken.3mf",
            source,
            {"assignments": {"7": 2}},
        )
    except ValueError as error:
        assert "keine Bambu-Modellzuordnungen" in str(error)
    else:
        raise AssertionError("Assignments without model_settings.config were accepted")


def test_unknown_object_assignment_is_rejected() -> None:
    materials = _load_materials_module()
    source = _archive({
        "[Content_Types].xml": "<Types/>",
        "3D/3dmodel.model": "<model/>",
        "Metadata/model_settings.config": "<config><object id=\"1\"/></config>",
    })

    try:
        materials.apply_material_plan(
            "unknown.3mf",
            source,
            {"assignments": {"999": 4}},
        )
    except ValueError as error:
        assert "Keine der gewählten Objekt-/Teil-IDs" in str(error)
    else:
        raise AssertionError("Unknown object assignment was accepted")


def test_unsafe_member_path_is_rejected() -> None:
    materials = _load_materials_module()
    source = _archive({
        "../Metadata/model_settings.config": "<config><object id=\"1\"/></config>",
    })

    try:
        materials.apply_material_plan(
            "unsafe.3mf",
            source,
            {"assignments": {}},
        )
    except ValueError as error:
        assert "unsicheren Pfad" in str(error)
    else:
        raise AssertionError("Unsafe archive member was accepted")