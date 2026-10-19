"""Real snapshot functions, isolated telemetry; never communicates with a printer."""
from __future__ import annotations
import ast
from pathlib import Path
from typing import Any
from types import SimpleNamespace
import pytest
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio/filament_color_views.py"

def snapshot_source(external, slot=None):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))
    wanted = {"_temperature", "_hex_color", "_snapshot"}
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted)], type_ignores=[])
    namespace = {"Any": Any, "HomeAssistant": object, "_external_spool": lambda _h, _p: dict(external),
                 "_slots": lambda _p: [dict(slot)] if slot else [], "printer_model": lambda _p: "X1C"}
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), namespace)
    return namespace["_snapshot"]

def data(**changes):
    return {"available": True, "loaded": False, "entity_id": "sensor.test_external",
            "material": "PLA", "filament_id": "GFL99", "color": "#123456",
            "nozzle_temp_min": 190, "nozzle_temp_max": 240, "rfid_detected": False, **changes}

@pytest.mark.parametrize("loaded", [False, True])
def test_external_setting_uses_its_own_address_without_requiring_loading(loaded):
    result = snapshot_source(data(loaded=loaded))(object(), object(), "external_spool", "external")
    assert (result["ams_id"], result["tray_id"], result["target_id"]) == (255, 0, "external")
    assert result["current_color"] == "#123456"
    assert result["tray_info_idx"] == "GFL99"
    assert result["loaded"] is loaded

@pytest.mark.parametrize("target", ["", "0", "0:0", "another-external"])
def test_external_setting_rejects_ambiguous_target_identifier(target):
    with pytest.raises(ValueError):
        snapshot_source(data(loaded=True))(object(), object(), "external_spool", target)

@pytest.mark.parametrize("changes", [{"rfid_detected": True}])
def test_existing_telemetry_and_rfid_guards_remain(changes):
    with pytest.raises(ValueError):
        snapshot_source(data(**changes))(object(), object(), "external_spool", "external")

def test_ams_slot_stays_separate_and_address_is_unchanged():
    slot = {**data(), "global_id": "2:3", "unit_id": "2", "tray_id": "3", "slot_index": 11,
            "present": True, "active": False}
    result = snapshot_source(data(), slot)(object(), object(), "ams_slot", "2:3")
    assert (result["ams_id"], result["tray_id"], result["target_id"]) == (2, 3, "2:3")
    with pytest.raises(ValueError):
        snapshot_source(data(), slot)(object(), object(), "ams_slot", "1:0")

def test_source_revalidates_loaded_state_after_preview():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))
    tuples = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "protected" for t in node.targets)]
    assert len(tuples) == 1
    assert "loaded" in ast.literal_eval(tuples[0].value)



def test_external_setup_does_not_require_existing_material_metadata():
    snapshot = snapshot_source(data(available=False, material="", nozzle_temp_min=None, nozzle_temp_max=None))
    result = snapshot(object(), object(), "external_spool", "external")
    assert result["printer_model"] == "X1C"
    assert (result["ams_id"], result["tray_id"]) == (255, 0)

@pytest.mark.parametrize("changes", [{"material": ""}, {"nozzle_temp_min": None}, {"nozzle_temp_max": 180}])
def test_ams_still_requires_actual_material_temperature_metadata(changes):
    slot = {**data(**changes), "global_id":"2:3", "unit_id":"2", "tray_id":"3", "slot_index":11, "present":True}
    with pytest.raises(ValueError): snapshot_source(data(),slot)(object(),object(),"ams_slot","2:3")
