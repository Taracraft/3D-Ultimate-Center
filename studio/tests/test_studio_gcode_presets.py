from __future__ import annotations
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

C = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio"
spec = importlib.util.spec_from_file_location("studio_gcode_presets", C / "gcode_preset_contract.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def catalog():
    return {"selection": {}, "profiles": deepcopy(list(G.GCODE_DEFAULT_PROFILES))}


def test_defaults_reconstruct_both_user_originals_without_reordering():
    contract = G.resolve_gcode_presets(catalog(), "A1")
    original = json.loads((C / "a1_gcode_defaults.json").read_text())
    assert contract["settings"]["machine_start_gcode"] == original["machine_start_gcode"]
    assert contract["settings"]["machine_end_gcode"] == original["machine_end_gcode"]
    assert contract["settings"]["machine_end_gcode"].count("M971 S11 C11 O0") == 30
    assert contract["settings"]["machine_end_gcode"].rstrip().endswith("M18 X Y Z")
    assert "{filament_type[initial_no_support_extruder]}" in contract["settings"]["machine_start_gcode"]
    assert set(G.FILAMENT_GCODE_DEFAULTS) == {"filament_start_gcode", "filament_end_gcode"}
    assert G.FILAMENT_GCODE_DEFAULTS["filament_end_gcode"].strip() == "; filament end gcode"


def test_modified_sound_and_silent_end_keep_machine_epilogue():
    c = catalog()
    p = c["profiles"][0]
    p["id"] = "local.sound.modified"
    p["payload"]["start_sound_gcode"] = "; my sound\nM1006 W"
    c["selection"]["gcode_preset_ids"] = {"start_sound": p["id"], "end_sound": ""}
    result = G.resolve_gcode_presets(c, "Bambu Lab A1")
    assert result["settings"]["machine_start_gcode"].count("; my sound") == 1
    assert "M1006" not in result["settings"]["machine_end_gcode"]
    assert result["settings"]["machine_end_gcode"].rstrip().endswith("M18 X Y Z")
    assert result["sha256"] != G.resolve_gcode_presets(catalog(), "A1")["sha256"]


@pytest.mark.parametrize("bad", ["filament", "wrong_slot", "missing", "wrong_model"])
def test_mismatched_templates_fail_before_any_worker_job(bad):
    c = catalog()
    p = c["profiles"][0]
    if bad == "filament": p["kind"] = "filament"
    if bad == "wrong_slot": p["payload"]["gcode_slot"] = "end_sound"
    if bad == "missing": c["profiles"].remove(p)
    if bad == "wrong_model": p["payload"]["printer_model"] = "A1 mini"
    with pytest.raises(ValueError):
        G.resolve_gcode_presets(c, "A1")


def test_native_materializer_applies_exact_machine_code_and_rejects_tampering(tmp_path):
    machine = tmp_path / "BBL/machine/Bambu Lab A1 0.4 nozzle.json"
    machine.parent.mkdir(parents=True)
    machine.write_text(json.dumps({"name": "A1", "nozzle_diameter": ["0.4"], "machine_start_gcode": "old"}))
    contract = G.resolve_gcode_presets(catalog(), "A1")
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"target_printer": {"machine_gcode_contract": contract}}))
    output = tmp_path / "runtime.json"
    args = [sys.executable, str(C / "materialize-bambu-machine.py"), str(tmp_path), str(machine.relative_to(tmp_path)), str(output), str(job)]
    subprocess.run(args, check=True, capture_output=True)
    applied = json.loads(output.read_text())
    assert applied["nozzle_diameter"] == ["0.4"]
    assert {key: applied[key] for key in contract["settings"]} == contract["settings"]
    contract["settings"]["machine_start_gcode"] += "\nM400"
    job.write_text(json.dumps({"target_printer": {"machine_gcode_contract": contract}}))
    failed = subprocess.run(args, capture_output=True)
    assert failed.returncode != 0


def test_a1_presets_are_never_implicitly_applied_to_other_printers():
    assert G.resolve_gcode_presets(catalog(), "A1 mini") is None
    c = catalog()
    c["selection"]["gcode_preset_ids"] = {"gcode_1": "builtin.a1.gcode_1"}
    with pytest.raises(ValueError):
        G.resolve_gcode_presets(c, "P1S")


def test_filament_sections_are_materialized_only_on_filament_profiles():
    spec = importlib.util.spec_from_file_location("studio_gcode_filament_materializer", C / "materialize-bambu-multimaterial.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = {"name": "PLA", "filament_start_gcode": ["old start"], "filament_end_gcode": ["old end"], "nozzle_temperature": ["220"]}
    filament = {"selected_profile": {"name": "My PLA", "payload": dict(G.FILAMENT_GCODE_DEFAULTS)}}
    result = module._apply_selected_profile_payload(original, filament)
    assert result["filament_start_gcode"] == [G.FILAMENT_GCODE_DEFAULTS["filament_start_gcode"]]
    assert result["filament_end_gcode"] == [G.FILAMENT_GCODE_DEFAULTS["filament_end_gcode"]]
    assert result["nozzle_temperature"] == ["220"]
    assert "machine_start_gcode" not in result
    assert original["filament_start_gcode"] == ["old start"]
