from __future__ import annotations

import importlib.util
from pathlib import Path

COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "deploy/homeassistant/custom_components/ultimate_3d_studio"
)
SPEC = importlib.util.spec_from_file_location(
    "studio_materializer",
    COMPONENT / "materialize-bambu-multimaterial.py",
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_plate_one_uses_plate_specific_tower_coordinates() -> None:
    purge = {
        "width_mm": 60,
        "brim_width_mm": 3,
        "position_x": 205,
        "position_y": 205,
        "positions_x": [65.9645, 165, 165],
        "positions_y": [176.615, 250, 250],
    }
    result = module._tower_geometry(purge, {}, 0)
    assert result["position_x"] == 65.9645
    assert result["position_y"] == 176.615
    assert result["clamped"] is False
    assert result["bounds"]["max_x"] < 256
    assert result["bounds"]["max_y"] < 256


def test_outside_plate_coordinate_is_clamped_with_full_tower() -> None:
    purge = {
        "width_mm": 60,
        "brim_width_mm": 3,
        "positions_x": [165, 165],
        "positions_y": [250, 250],
    }
    result = module._tower_geometry(purge, {}, 1)
    assert result["requested_y"] == 250
    assert result["position_y"] == 189
    assert result["clamped"] is True
    assert result["bounds"]["max_y"] == 252


def test_process_writes_bambu_tower_option_names(tmp_path: Path) -> None:
    process_root = tmp_path / "profiles" / "BBL" / "process"
    filament_root = tmp_path / "profiles" / "BBL" / "filament"
    process_root.mkdir(parents=True)
    filament_root.mkdir(parents=True)
    process_source = process_root / "base.json"
    process_source.write_text('{"name":"Base","type":"process"}', encoding="utf-8")
    filament = filament_root / "Generic PLA @BBL A1.json"
    filament.write_text(
        '{"name":"Generic PLA @BBL A1","filament_type":["PLA"],'
        '"filament_diameter":["1.75"],"filament_density":["1.24"]}',
        encoding="utf-8",
    )
    contract_body = {
        "schema_version": 1,
        "profile_id": "local.process.test",
        "name": "Testprozess",
        "source": "local",
        "materialization_policy": "mapped_studio_process",
        "native_base_profile": "BBL/process/base.json",
        "settings": {"layer_height": .2},
    }
    overrides = {
        "selected_process_profile": {
            **contract_body,
            "contract_sha256": module._contract_digest(contract_body),
        }
    }
    process, _paths, _profiles, tower, proof = module._materialize_process(
        process_source,
        process_root,
        filament_root,
        [
            {"material": "PLA", "color": "#FF0000"},
            {"material": "PLA", "color": "#000000"},
        ],
        "a1",
        overrides,
        {
            "enabled": True,
            "width_mm": 60,
            "brim_width_mm": 3,
            "positions_x": [65.9645],
            "positions_y": [176.615],
        },
        0,
    )
    assert proof["applied"] is True
    assert proof["profile_id"] == "local.process.test"
    assert process["prime_tower_width"] == "60"
    assert process["prime_tower_brim_width"] == "3"
    assert process["wipe_tower_x"] == "65.9645"
    assert process["wipe_tower_y"] == "176.615"
    assert "prime_tower_position_x" not in process
    assert "prime_tower_position_y" not in process
    assert tower["bounds"]["max_y"] < 256
