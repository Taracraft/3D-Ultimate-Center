"""Audit regressions: selected filament values, job integrity and physical limits."""
from copy import deepcopy
import importlib.util
from io import BytesIO
from pathlib import Path
import sys

import pytest

C = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6"


def load(name):
    spec = importlib.util.spec_from_file_location("v6_repair_" + name, C / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


filament = load("filament_parameter_contract")
execution = load("slicer_execution_contract")
validation = load("gcode_artifact_validation")


def selected():
    return {"id": "petg", "payload": {"native_profile_name": "Generic PETG HF @BBL A1",
            "nozzle_temperature_c": [230, 250], "recommended_nozzle_temperature_c": 240,
            "first_layer_nozzle_temperature_c": 245, "bed_temperature_c": 70,
            "first_layer_bed_temperature_c": 75, "cooling_fan_min_percent": 30,
            "cooling_fan_max_percent": 70, "retraction_length_mm": .8}}


def complete(extra):
    lines = ["M1002 gcode_claim_action : 1", "G392 S0", "M104 S220", "M140 S60", "M109 S220", "M190 S60",
             "M620 S0A", "M621 S0A", "M1002 judge_flag g29_before_print_flag", "G29 A1",
             "M1002 judge_flag extrude_cali_flag", "M983 A0", "; WIPE NOZZLE", "M900 C", extra]
    lines.extend("G1 X1 Y1 E0.1" for _ in range(100))
    lines.extend(["M104 S0", "M140 S0"])
    return BytesIO(("\n".join(lines) + "\n").encode())


def test_range_is_not_a_temperature_setpoint_and_first_layer_is_distinct():
    result = filament.preflight_filament_settings(selected()["payload"])
    assert result["nozzle_temperature"] == ["240"]
    assert result["nozzle_temperature_initial_layer"] == ["245"]
    assert result["textured_plate_temp"] == ["70"]
    assert result["textured_plate_temp_initial_layer"] == ["75"]
    assert result["fan_min_speed"] == ["30"]
    assert result["fan_max_speed"] == ["70"]
    assert result["filament_retraction_length"] == ["0.8"]
    assert "nozzle_temperature_c" not in result


def test_explicit_native_user_values_take_precedence_over_curated_aliases():
    payload = selected()["payload"]
    payload.update(nozzle_temperature=["242"], nozzle_temperature_initial_layer=["247"],
                   textured_plate_temp_initial_layer=["78"], fan_min_speed=["35"])
    result = filament.preflight_filament_settings(payload)
    assert result["nozzle_temperature"] == ["242"]
    assert result["nozzle_temperature_initial_layer"] == ["247"]
    assert result["textured_plate_temp_initial_layer"] == ["78"]
    assert result["fan_min_speed"] == ["35"]


def test_generic_bed_recommendation_does_not_enable_unsupported_cool_plate():
    result = filament.preflight_filament_settings(selected()["payload"])
    with pytest.raises(ValueError, match="unterstützt Cool Plate nicht"):
        filament.check_filament_temperatures(result, execution.a1_hardware_limits("A1"), "Cool Plate")


@pytest.mark.parametrize("field,value", [("nozzle_temperature", ["350"]), ("textured_plate_temp_initial_layer", ["120"])])
def test_worker_rechecks_effective_temperatures_after_preflight(field, value):
    result = filament.preflight_filament_settings(selected()["payload"])
    result[field] = value
    with pytest.raises(ValueError, match="überschreitet"):
        filament.check_filament_temperatures(result, execution.a1_hardware_limits("A1"), "Textured PEI Plate")


@pytest.mark.parametrize("change", ["filament", "machine_gcode", "plate", "process", "native_machine", "report"])
def test_contract_binds_all_selected_values_not_only_profile_ids(change):
    plan = {"filaments": [{"selected_profile": selected()}]}
    report = {"status": "compatible", "filaments": [{"selected_profile_sha256": execution.digest(selected())}]}
    report["contract_sha256"] = execution.digest(report)
    target = {"model": "A1", "native_machine_profile": "machine.json", "machine_gcode_contract": {"settings": {"machine_start_gcode": "M104 S220"}}, "compatibility_contract": report}
    overrides = {"require_execution_contract": True, "build_plate_width_mm": 256, "selected_process_profile": {"settings": {"layer_height": ".2"}}}
    overrides["execution_contract"] = execution.bind_execution_contract(target, overrides, plan)
    job = {"target_printer": target, "process_overrides": overrides, "material_plan": plan, "native_machine_profile": "machine.json"}
    assert execution.validate_execution_contract(job)
    mutated = deepcopy(job)
    if change == "filament": mutated["material_plan"]["filaments"][0]["selected_profile"]["payload"]["recommended_nozzle_temperature_c"] = 350
    if change == "machine_gcode": mutated["target_printer"]["machine_gcode_contract"]["settings"]["machine_start_gcode"] = "M104 S350"
    if change == "plate": mutated["process_overrides"]["build_plate_width_mm"] = 300
    if change == "process": mutated["process_overrides"]["selected_process_profile"]["settings"]["layer_height"] = ".6"
    if change == "native_machine": mutated["native_machine_profile"] = "other.json"
    if change == "report": mutated["target_printer"]["compatibility_contract"]["filaments"][0]["selected_profile_sha256"] = "other"
    with pytest.raises(ValueError): execution.validate_execution_contract(mutated)


@pytest.mark.parametrize("size", [0, -1, 300, float("nan"), float("inf"), True])
def test_invalid_a1_plate_dimensions_fail_closed(size):
    with pytest.raises(ValueError): execution.validate_plate_dimensions({"build_plate_width_mm": size}, (256, 256))


def test_larger_printer_dimensions_are_not_globally_limited_to_a1():
    assert execution.validate_plate_dimensions({"build_plate_width_mm": 300, "build_plate_depth_mm": 300}, (350, 350)) == (300, 300)
    assert execution.a1_hardware_limits("A1 mini") is None
    assert execution.a1_hardware_limits("H2D") is None


@pytest.mark.parametrize("command", ["M104 S350", "M109 R350", "M104S350", "N12 M104 S350", "M140 S120", "M190 R120", "M104 SNaN", "M104 S-1", "M109 S220 H350", "M620.1 E F10 T350"])
def test_final_artifact_rejects_unsafe_heater_commands_including_custom_gcode(command):
    with pytest.raises(validation.GCodeValidationError):
        validation.validate_rendered_bambu_gcode(complete(command), hardware_limits=execution.a1_hardware_limits("A1"))


def test_known_a1_header_enforces_limits_even_without_supplied_job_context():
    with pytest.raises(validation.GCodeValidationError, match="höchstens 300"):
        validation.validate_rendered_bambu_gcode(complete("M104 S350\n; printer_model = Bambu Lab A1"))


def test_larger_printer_can_have_its_own_verified_temperature_limits():
    report = validation.validate_rendered_bambu_gcode(complete("M104 S350"), hardware_limits={"max_nozzle_temperature_c": 400, "max_bed_temperature_c": 150})
    assert report.temperature_limits_verified
    assert report.max_commanded_nozzle_temperature_c == 350


def test_regular_extrusion_cannot_escape_the_selected_printer_area():
    extra = "M83\nG1 X100 Y100\n; MACHINE_START_GCODE_END\nG1 X270 Y100 E1"
    with pytest.raises(validation.GCodeValidationError, match="physische X-Grenze"):
        validation.validate_rendered_bambu_gcode(complete(extra), hardware_limits=execution.a1_hardware_limits("A1"))


def test_final_worker_rejects_silent_cli_parameter_loss():
    with pytest.raises(validation.GCodeValidationError, match="nicht unverändert übernommen"):
        validation.validate_rendered_bambu_gcode(complete("; nozzle_temperature = 220"),
                                                runtime_parameters=[{"nozzle_temperature": ["240"]}])
    report = validation.validate_rendered_bambu_gcode(complete("T0\nM104 S240\n; nozzle_temperature = 240"),
                                                     runtime_parameters=[{"nozzle_temperature": ["240"]}])
    assert report.filament_parameter_contract_verified


def test_empty_cloud_process_overlay_uses_only_the_verified_native_base(tmp_path):
    worker_path = C / "materialize-bambu-multimaterial.py"
    spec = importlib.util.spec_from_file_location("v6_repair_worker", worker_path)
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    process_dir = tmp_path / "BBL/process"
    process_dir.mkdir(parents=True)
    source = process_dir / "0.20mm Standard @BBL A1.json"
    source.write_text('{"layer_height":"0.2"}')
    contract = {"schema_version": 1, "profile_id": "cloud.base", "name": "Native base", "source": "bambu_cloud",
                "materialization_policy": "exact_bambu_cloud_overlay", "native_base_profile": "BBL/process/" + source.name,
                "settings": {}}
    contract["contract_sha256"] = execution.digest(contract)
    output, proof = worker._apply_selected_process_profile({"layer_height": ".2"}, source, process_dir, {"selected_process_profile": contract})
    assert output == {"layer_height": ".2"}
    assert proof["applied"] and proof["applied_setting_count"] == 0
    contract["native_base_profile"] = "BBL/process/other.json"
    contract["contract_sha256"] = execution.digest({k: v for k, v in contract.items() if k != "contract_sha256"})
    with pytest.raises(ValueError, match="Basisprofil"):
        worker._apply_selected_process_profile({}, source, process_dir, {"selected_process_profile": contract})


@pytest.mark.parametrize("clockwise", [False, True])
def test_full_circle_checks_interior_extrema(clockwise):
    start = {"X": 255.0, "Y": 100.0, "Z": 1.0}
    bounds = validation._arc_bounds("G2 I1 J0 E1", start, start, clockwise)
    assert bounds["X"] == (255.0, 257.0)


def test_native_short_arc_is_accepted_but_outside_bulge_is_rejected():
    safe = "M83\nG1 X114.046 Y114.052 Z.44\n; MACHINE_START_GCODE_END\nG2 X114.046 Y114.052 I-.035 J.062 E.00625"
    assert validation.validate_rendered_bambu_gcode(complete(safe), hardware_limits=execution.a1_hardware_limits("A1")).checked_print_extrusion_moves >= 1
    unsafe = "M83\nG1 X255 Y100 Z1\n; MACHINE_START_GCODE_END\nG2 X255 Y100 I1 J0 E1"
    with pytest.raises(validation.GCodeValidationError, match="physische X-Grenze"):
        validation.validate_rendered_bambu_gcode(complete(unsafe), hardware_limits=execution.a1_hardware_limits("A1"))


@pytest.mark.parametrize("command", ["G2 X10 Y10 R1", "G3 X10 Y10 I0 J0", "G2 X10 Y10 I1 P2"])
def test_unsupported_or_inconsistent_arcs_fail_closed(command):
    with pytest.raises(validation.GCodeValidationError):
        validation._arc_bounds(command, {"X": 0., "Y": 0., "Z": 0.}, {"X": 10., "Y": 10., "Z": 0.}, True)


def test_shared_bed_rejects_conflicting_material_targets():
    a = {"textured_plate_temp": [55], "textured_plate_temp_initial_layer": [60]}
    b = {"textured_plate_temp": [70], "textured_plate_temp_initial_layer": [75]}
    with pytest.raises(ValueError, match="unterschiedliche Betttemperaturen"):
        filament.validate_shared_bed_temperatures([a, b], "Textured PEI Plate")
    filament.validate_shared_bed_temperatures([a, dict(a)], "Textured PEI Plate")


@pytest.mark.parametrize("command", ["M104 S220", "M109 S220 H240", "T1\nM104 S240"])
def test_parameter_header_cannot_replace_executed_channel_temperature(command):
    with pytest.raises(validation.GCodeValidationError, match="nicht als Heizbefehl ausgeführt"):
        validation.validate_rendered_bambu_gcode(complete("T0\n" + command + "\n; nozzle_temperature = 240"), runtime_parameters=[{"nozzle_temperature": ["240"]}])


@pytest.mark.parametrize("move", ["G1X270Y100E1", "N100 G1X270Y100E1", "G1 X+270 Y100 E1"])
def test_compact_numbered_and_signed_moves_obey_printer_area(move):
    with pytest.raises(validation.GCodeValidationError, match="physische X-Grenze"):
        validation.validate_rendered_bambu_gcode(complete("M83\nG1 X100 Y100\n; MACHINE_START_GCODE_END\n" + move), hardware_limits=execution.a1_hardware_limits("A1"))


def test_non_finite_motion_and_homing_inside_print_fail_closed():
    for move in ["G1 XNaN Y100 E1", "G1 XInf E1", "G28 X"]:
        with pytest.raises(validation.GCodeValidationError):
            validation.validate_rendered_bambu_gcode(complete("; MACHINE_START_GCODE_END\n" + move), hardware_limits=execution.a1_hardware_limits("A1"))


def test_a1_has_no_chamber_heater_and_does_not_claim_a_chamber_proof():
    payload=selected()['payload']
    settings=filament.preflight_filament_settings(payload)
    settings['chamber_temperatures']=['0']
    assert 'chamber_temperatures' not in filament.parameter_proof(settings,payload)['parameter_settings']
    settings['chamber_temperatures']=['1']
    with pytest.raises(ValueError):
        filament.check_filament_temperatures(settings,execution.a1_hardware_limits('A1'),'Textured PEI Plate')
