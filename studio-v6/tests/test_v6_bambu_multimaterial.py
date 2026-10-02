from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import zipfile

COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6"
)
SCRIPT = COMPONENT / "materialize-bambu-multimaterial.py"



def selected_process_contract() -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": 1,
        "profile_id": "local.process.a1_0_20_standard",
        "name": "A1 0,20 mm Standard",
        "source": "local",
        "materialization_policy": "mapped_v6_process",
        "native_base_profile": "BBL/process/0.20mm Standard @BBL A1.json",
        "settings": {
            "layer_height": 0.2,
            "wall_loops": 3,
            "sparse_infill_density": "15%",
            "outer_wall_speed": 70,
            "line_width": 0.3,
            "outer_wall_line_width": 0.3,
            "inner_wall_line_width": 0.3,
            "top_surface_line_width": 0.3,
            "support_line_width": 0.3,
            "sparse_infill_speed": 1,
            "internal_solid_infill_speed": 1,
            "top_surface_speed": 1,
            "initial_layer_speed": 1,
            "bridge_speed": 1,
            "support_top_z_distance": 0.3,
            "support_bottom_z_distance": 0.3,
            "support_object_xy_distance": 0.3,
            "support_interface_spacing": 0.3,
            "support_interface_top_layers": 2,
            "support_interface_bottom_layers": 2,

        },
    }
    digest = sha256(
        json.dumps(
            body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {**body, "contract_sha256": digest}


def write_profile(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_input_3mf(path: Path) -> None:
    model = """<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <resources>
    <object id="2" type="model" name="red-part"><mesh><vertices>
      <vertex x="0" y="0" z="0"/><vertex x="10" y="0" z="0"/><vertex x="0" y="10" z="0"/>
    </vertices><triangles><triangle v1="0" v2="1" v3="2"/></triangles></mesh></object>
    <object id="3" type="model" name="black-part"><mesh><vertices>
      <vertex x="0" y="0" z="1"/><vertex x="10" y="0" z="1"/><vertex x="0" y="10" z="1"/>
    </vertices><triangles><triangle v1="0" v2="1" v3="2"/></triangles></mesh></object>
  </resources>
  <build><item objectid="2"/><item objectid="3"/></build>
</model>"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("3D/3dmodel.model", model)


def test_materializes_two_ams_channels_and_assemble_manifest(tmp_path: Path) -> None:
    profile_root = tmp_path / "profiles"
    process_dir = profile_root / "BBL/process"
    filament_dir = profile_root / "BBL/filament"
    write_profile(process_dir / "Base Process.json", {
        "name": "Base Process",
        "type": "process",
        "from": "system",
        "filament_diameter": ["1.75"],
        "filament_density": ["1.24"],
        "filament_flow_ratio": ["1"],
        "filament_max_volumetric_speed": ["12"],
        "nozzle_temperature": ["210"],
        "nozzle_temperature_initial_layer": ["215"],
    })
    process_source = process_dir / "0.20mm Standard @BBL A1.json"
    write_profile(process_source, {
        "name": "0.20mm Standard @BBL A1",
        "type": "process",
        "from": "system",
        "inherits": "Base Process",
    })
    write_profile(filament_dir / "Generic PLA @base.json", {
        "name": "Generic PLA @base",
        "type": "filament",
        "from": "system",
        "filament_type": ["PLA"],
        "filament_diameter": ["1.75"],
        "filament_density": ["1.24"],
        "filament_flow_ratio": ["0.98"],
        "filament_max_volumetric_speed": ["18"],
        "nozzle_temperature": ["220"],
        "nozzle_temperature_initial_layer": ["225"],
        "filament_extruder_variant": ["Direct Drive Standard"],
    })
    write_profile(filament_dir / "Generic PLA @BBL A1.json", {
        "name": "Generic PLA @BBL A1",
        "type": "filament",
        "from": "system",
        "inherits": "Generic PLA @base",
        "setting_id": "GFSL99_04",
        "filament_id": "GFL99",
        "compatible_printers": ["Bambu Lab A1 0.4 nozzle"],
    })
    write_profile(filament_dir / "eSUN PLA+ @base.json", {
        "name": "eSUN PLA+ @base",
        "type": "filament",
        "from": "system",
        "filament_type": ["PLA"],
        "filament_diameter": ["1.75"],
        "filament_density": ["1.25"],
        "filament_flow_ratio": ["0.97"],
        "filament_max_volumetric_speed": ["20"],
        "nozzle_temperature": ["225"],
        "nozzle_temperature_initial_layer": ["230"],
        "filament_extruder_variant": ["Direct Drive Standard"],
    })
    write_profile(filament_dir / "eSUN PLA+ @BBL A1.json", {
        "name": "eSUN PLA+ @BBL A1",
        "type": "filament",
        "from": "system",
        "inherits": "eSUN PLA+ @base",
        "setting_id": "GFSL03_05",
        "filament_id": "GFL03",
        "compatible_printers": ["Bambu Lab A1 0.4 nozzle"],
    })

    source_3mf = tmp_path / "input.3mf"
    write_input_3mf(source_3mf)
    job = tmp_path / "job.json"
    job.write_text(json.dumps({
        "target_printer": {
            "name": "Bambu A1",
            "model": "A1",
            "physical_extruder_count": 1,
        },
        "process_overrides": {
            "adhesion_mode": "brim",
            "brim_width_mm": 6,
            "support_mode": "off",
            "layer_height_ranges": [
                {"min_z_mm": 0, "max_z_mm": 4.8, "layer_height_mm": 0.12},
                {"min_z_mm": 4.8, "max_z_mm": 12, "layer_height_mm": 0.2},
            ],
            "selected_process_profile": selected_process_contract(),
        },
        "material_plan": {
            "assignments": {"2": 1, "3": 2},
            "filaments": [
                {
                    "extruder": 1,
                    "display_slot": 1,
                    "filament_id": "GFL99",
                    "material": "PLA",
                    "color": "#F62021",
                },
                {
                    "extruder": 2,
                    "display_slot": 2,
                    "filament_id": "GFL03",
                    "material": "PLA",
                    "color": "#000000",
                },
            ],
            "purge_tower": {"enabled": True, "flush_multiplier": 1},
        },
    }), encoding="utf-8")

    process_output = tmp_path / "runtime-process.json"
    manifest_output = tmp_path / "assemble.json"
    summary_output = tmp_path / "summary.json"
    parts_dir = tmp_path / "parts"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--profile-root", str(profile_root),
            "--input", str(source_3mf),
            "--job", str(job),
            "--process-source", str(process_source),
            "--process-output", str(process_output),
            "--manifest-output", str(manifest_output),
            "--parts-dir", str(parts_dir),
            "--summary-output", str(summary_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr

    process = json.loads(process_output.read_text(encoding="utf-8"))
    assert process["filament_colour"] == ["#F62021", "#000000"]
    assert process["filament_ids"] == ["GFL99", "GFL03"]
    assert process["filament_settings_id"] == ["Generic PLA @BBL A1", "eSUN PLA+ @BBL A1"]
    assert process["filament_diameter"] == ["1.75", "1.75"]
    assert process["filament_density"] == ["1.24", "1.25"]
    assert process["filament_flow_ratio"] == ["0.98", "0.97"]
    assert process["nozzle_temperature"] == ["220", "225"]
    assert process["physical_extruder_map"] == ["0"]
    assert process["filament_map"] == ["1", "1"]
    assert process["flush_volumes_matrix"] == ["0", "280", "280", "0"]
    assert process["enable_prime_tower"] == "1"
    assert process["brim_type"] == "outer_only"
    assert process["brim_width"] == "6"
    assert process["layer_height"] == "0.2"
    assert process["wall_loops"] == 3
    assert process["sparse_infill_density"] == "15%"
    assert process["outer_wall_speed"] == 70

    manifest = json.loads(manifest_output.read_text(encoding="utf-8"))
    objects = manifest["plates"][0]["objects"]
    assert [item["filaments"] for item in objects] == [[1], [2]]
    assert manifest["plates"][0]["need_arrange"] is False
    assert manifest["plates"][0]["assembled_params"] == [
        {
            "assemble_index": 1,
            "height_ranges": [
                {
                    "min_z": 0.0,
                    "max_z": 4.8,
                    "range_params": {"layer_height": "0.12"},
                },
                {
                    "min_z": 4.8,
                    "max_z": 12.0,
                    "range_params": {"layer_height": "0.2"},
                },
            ],
        }
    ]
    assert manifest["plates"][0]["plate_params"] == {
        "filament_map_mode": "Manual",
        "filament_map": "1 1",
    }
    assert len(list(parts_dir.glob("*.stl"))) == 2
    assert all(path.stat().st_size == 134 for path in parts_dir.glob("*.stl"))

    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    for key, expected in selected_process_contract()["settings"].items():
        assert summary["process_settings"][key] == process[key]
        value = process[key][0] if isinstance(process[key], list) else process[key]
        assert str(value) == str(expected)

    assert summary["physical_extruder_count"] == 1
    assert summary["material_channel_count"] == 2
    assert summary["triangle_count"] == 2
    assert summary["selected_process_profile"]["applied"] is True
    assert summary["selected_process_profile"]["profile_id"] == "local.process.a1_0_20_standard"
    assert summary["selected_process_profile"]["applied_setting_count"] == len(selected_process_contract()["settings"])
    assert summary["variable_layer_heights"] == {
        "applied": True,
        "range_count": 2,
        "ranges": [
            {"min_z_mm": 0.0, "max_z_mm": 4.8, "layer_height_mm": 0.12},
            {"min_z_mm": 4.8, "max_z_mm": 12.0, "layer_height_mm": 0.2},
        ],
        "native_scope": "assembled_model_group_1",
    }
    assert [item["filament_id"] for item in summary["filaments"]] == ["GFL99", "GFL03"]
