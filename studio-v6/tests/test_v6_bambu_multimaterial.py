from __future__ import annotations

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
            "support_mode": "normal",
            "support_build_plate_only": False,
            "support_threshold_angle": 12,
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
    assert process["enable_support"] == "1"
    assert process["support_type"] == "normal(auto)"
    assert process["support_on_build_plate_only"] == "0"
    assert process["support_threshold_angle"] == "12"

    manifest = json.loads(manifest_output.read_text(encoding="utf-8"))
    objects = manifest["plates"][0]["objects"]
    assert [item["filaments"] for item in objects] == [[1], [2]]
    assert manifest["plates"][0]["need_arrange"] is False
    assert manifest["plates"][0]["plate_params"] == {
        "filament_map_mode": "Manual",
        "filament_map": "1 1",
    }
    assert len(list(parts_dir.glob("*.stl"))) == 2
    assert all(path.stat().st_size == 134 for path in parts_dir.glob("*.stl"))

    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    assert summary["physical_extruder_count"] == 1
    assert summary["material_channel_count"] == 2
    assert summary["triangle_count"] == 2
    assert [item["filament_id"] for item in summary["filaments"]] == ["GFL99", "GFL03"]
