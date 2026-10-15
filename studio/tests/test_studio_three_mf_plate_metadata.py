"""Multi-plate metadata keeps logical objects unique and placements lossless."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def modules():
    fixture = _load("plate_metadata_fixture", ROOT / "tests" / "test_studio_three_mf_scene_instances.py")
    inspector = _load("plate_metadata_inspector", COMPONENT / "three_mf_inspector.py")
    scene = _load("plate_metadata_scene", COMPONENT / "three_mf_scene.py")
    return fixture, inspector, scene


def _with_filaments(files):
    return [
        *files,
        (
            "Metadata/project_settings.config",
            json.dumps(
                {
                    "filament_colour": ["#000000", "#FFFFFF"],
                    "filament_type": ["PLA", "PLA"],
                    "filament_settings_id": ["Black", "White"],
                }
            ),
        ),
    ]


def _metadata_ids_for_plate(result, plate_index: int) -> list[str]:
    return sorted(
        item["object_id"]
        for item in result["objects"]
        if plate_index in item.get("plate_indices", [])
    )


def test_object_family_across_plates_matches_scene_without_duplicate_object_ids(modules):
    fixture, inspector, scene = modules
    files = _with_filaments(
        fixture.project(plates=[[("10", "0"), ("20", "0")], [("10", "1")]])
    )
    data = fixture.archive(files)
    digest = hashlib.sha256(data).hexdigest()

    result = inspector.inspect_model("synthetic.3mf", data)
    scenes = [scene.extract_scene("synthetic.3mf", data, index) for index in (0, 1)]
    scene_ids = [sorted({item["object_id"] for item in value["instances"]}) for value in scenes]

    assert [item["object_id"] for item in result["objects"]] == ["10", "20"]
    assert len({item["object_id"] for item in result["objects"]}) == len(result["objects"])
    assert [_metadata_ids_for_plate(result, index) for index in (0, 1)] == scene_ids
    repeated = result["objects"][0]
    assert repeated["plate_index"] is None
    assert repeated["plate_indices"] == [0, 1]
    assert repeated["instances"] == [
        {"plate_index": 0, "instance_id": 0},
        {"plate_index": 1, "instance_id": 1},
    ]
    assert [plate["object_count"] for plate in result["plates"]] == [2, 1]
    assert [plate["logical_object_count"] for plate in result["plates"]] == [2, 1]
    assert [plate["instance_count"] for plate in result["plates"]] == [2, 1]
    assert [(item["extruder"], item["color"]) for item in result["filaments"]] == [
        (1, "#000000"),
        (2, "#FFFFFF"),
    ]
    assert result["used_extruders"] == [1, 2]
    assert hashlib.sha256(data).hexdigest() == digest


def test_same_plate_instances_count_separately_but_keep_one_logical_assignment_id(modules):
    fixture, inspector, _scene = modules
    data = fixture.archive(
        _with_filaments(
            fixture.project(plates=[[("10", "0"), ("10", "1"), ("20", "0")]])
        )
    )

    result = inspector.inspect_model("synthetic.3mf", data)
    repeated = result["objects"][0]

    assert [item["object_id"] for item in result["objects"]] == ["10", "20"]
    assert repeated["plate_index"] == 0
    assert repeated["plate_indices"] == [0]
    assert repeated["instance_count"] == 2
    assert repeated["instances"] == [
        {"plate_index": 0, "instance_id": 0},
        {"plate_index": 0, "instance_id": 1},
    ]
    assert result["plates"][0]["object_count"] == 3
    assert result["plates"][0]["instance_count"] == 3
    assert result["plates"][0]["logical_object_count"] == 2
    assert len({item["extruder"] for item in result["filaments"]}) == len(result["filaments"])


def test_partial_plate_metadata_uses_object_fallback_without_losing_known_instances(modules):
    fixture, inspector, _scene = modules
    files = fixture.project(plates=[[("10", "0")]])
    updated = []
    for name, data in files:
        if name == "Metadata/model_settings.config":
            root = ET.fromstring(data)
            object_twenty = next(item for item in root.findall("object") if item.attrib.get("id") == "20")
            ET.SubElement(
                object_twenty,
                "metadata",
                {"key": "plate_id", "value": "1"},
            )
            data = ET.tostring(root)
        updated.append((name, data))

    result = inspector.inspect_model("synthetic.3mf", fixture.archive(_with_filaments(updated)))
    by_id = {item["object_id"]: item for item in result["objects"]}

    assert by_id["10"]["instances"] == [{"plate_index": 0, "instance_id": 0}]
    assert by_id["20"]["instances"] == [{"plate_index": 0, "instance_id": None}]
    assert result["plates"][0]["object_count"] == 2
    assert result["plates"][0]["logical_object_count"] == 2


def test_single_plate_legacy_plate_index_and_part_materials_remain_compatible(modules):
    fixture, inspector, _scene = modules
    result = inspector.inspect_model(
        "synthetic.3mf",
        fixture.archive(
            _with_filaments(
                fixture.project(plates=[[("10", "0")], [("20", "0")]], repeat=False)
            )
        ),
    )

    assert [(item["object_id"], item["plate_index"]) for item in result["objects"]] == [
        ("10", 0),
        ("20", 1),
    ]
    assert [item["plate_indices"] for item in result["objects"]] == [[0], [1]]
    assert [part["extruder"] for item in result["objects"] for part in item["parts"]] == [2, 1]
