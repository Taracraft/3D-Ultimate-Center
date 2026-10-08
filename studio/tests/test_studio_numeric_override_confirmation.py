"""Behavioral regression checks for numeric override confirmation; no HA runtime."""
import ast
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import re
from typing import Any

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio/slicer_backend_router.py"
NAMES = {"_effective_numeric_process_settings", "_normalized_setting_values", "_settings_confirmed", "_normalized_material", "_normalized_color", "_materials_confirmed", "_profile_application"}
tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))
module = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in NAMES], type_ignores=[])
namespace = {"Any": Any, "re": re}
exec(compile(module, str(SOURCE), "exec"), namespace)
application = namespace["_profile_application"]


@pytest.mark.parametrize("override,native,baseline,custom", [
    ("layer_height_mm", "layer_height", .2, .12),
    ("outer_wall_speed_mm_s", "outer_wall_speed", 200, 80),
    ("inner_wall_speed_mm_s", "inner_wall_speed", 300, 120),
])
@pytest.mark.parametrize("case", ["correct", "old_value", "missing_proof", "wrong_proof", "no_override", "new_key", "wrong_material", "wrong_contract", "wrong_filament_temperature", "missing_filament_parameters", "unexecuted_temperature", "same_id_changed_payload"])
def test_numeric_override_confirmation(override, native, baseline, custom, case):
    job = {"process_overrides": {"selected_process_profile": {"profile_id": "test", "contract_sha256": "fixture", "settings": {native: str(baseline)}}, override: custom}, "material_plan": {"filaments": [{"selected_profile": {"id": "filament"}}]}}
    runtime = {"selected_process_profile": {"applied": True, "profile_id": "test", "contract_sha256": "fixture"}, "process_settings": {native: str(custom)}, "filaments": [{"selected_profile_id": "filament", "material": "PETG", "color": "#101010"}]}
    meta = {"gcode_profile_settings": {native: str(custom)}, "analysis": {"layer_count": 10, "materials": [{"material": "PETG", "color": "#101010"}]}}
    profile = job["material_plan"]["filaments"][0]["selected_profile"]
    profile["payload"] = {"nozzle_temperature": ["220"], "nozzle_temperature_initial_layer": ["220"]}
    runtime["filaments"][0]["selected_profile_sha256"] = hashlib.sha256(json.dumps(profile, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    runtime["filaments"][0]["parameter_settings"] = {"nozzle_temperature": ["220"], "nozzle_temperature_initial_layer": ["220"]}
    meta["gcode_profile_settings"].update(nozzle_temperature=["220"], nozzle_temperature_initial_layer=["220"])
    meta["heater_commands"] = [{"command": "M109", "channel": 1, "temperature_c": 220}]
    expected = case in {"correct", "no_override", "new_key"}
    if case == "old_value":
        meta["gcode_profile_settings"][native] = str(baseline)
    elif case == "missing_proof":
        runtime.pop("process_settings")
    elif case == "wrong_proof":
        runtime["process_settings"][native] = str(baseline)
    elif case == "no_override":
        job["process_overrides"][override] = None
        meta["gcode_profile_settings"][native] = str(baseline)
    elif case == "new_key":
        job["process_overrides"]["selected_process_profile"]["settings"] = {"wall_loops": "3"}
        meta["gcode_profile_settings"]["wall_loops"] = "3"
    elif case == "wrong_material":
        meta["analysis"]["materials"][0]["color"] = "#FF0000"
    elif case == "wrong_contract":
        runtime["selected_process_profile"]["contract_sha256"] = "other"
    if case == "wrong_filament_temperature":
        meta["gcode_profile_settings"]["nozzle_temperature"] = ["240"]
    elif case == "missing_filament_parameters":
        runtime["filaments"][0].pop("parameter_settings")
    elif case == "unexecuted_temperature":
        meta["heater_commands"] = []
    elif case == "same_id_changed_payload":
        job["material_plan"]["filaments"][0]["selected_profile"]["payload"]["nozzle_temperature"] = ["230"]
    before = deepcopy((job, runtime, meta))
    result = application(job, runtime, meta)
    assert result["gcode_confirmed"] is expected
    assert (job, runtime, meta) == before


def test_native_material_family_requires_explicit_parameter_proof():
    expected = [{"material": "PA-CF", "color": "#101010", "parameter_settings": {"filament_type": ["PA"]}}]
    observed = {"materials": [{"material": "PA", "color": "#101010"}]}
    assert namespace["_materials_confirmed"](expected, observed)
    expected[0]["parameter_settings"]["filament_type"] = ["PETG"]
    assert not namespace["_materials_confirmed"](expected, observed)
    expected[0].pop("parameter_settings")
    assert not namespace["_materials_confirmed"](expected, observed)
