"""Regression tests for the standalone Studio Bambu telemetry normalizer."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
COMPONENT_DIR = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio"
)
TELEMETRY_PATH = COMPONENT_DIR / "telemetry.py"
ISSUES_PATH = COMPONENT_DIR / "printer_issues.py"


def _load_file(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_telemetry_module():
    package_name = "ultimate_3d_studio"
    package = types.ModuleType(package_name)
    package.__path__ = [str(COMPONENT_DIR)]
    sys.modules[package_name] = package
    _load_file(f"{package_name}.printer_issues", ISSUES_PATH)
    return _load_file(f"{package_name}.telemetry", TELEMETRY_PATH)


def _realistic_a1_bmcu_payload() -> dict[str, object]:
    return {
        "print": {
            "tray_now": "255",
            "ams": {
                "ams": [
                    {
                        "id": "0",
                        "humidity": "5",
                        "temp": "25.7",
                        "tray": [
                            {"id": "0"},
                            {
                                "id": "1",
                                "tray_type": "PLA",
                                "tray_color": "000000FF",
                                "nozzle_temp_min": "190",
                                "nozzle_temp_max": "240",
                                "remain": "0",
                                "tag_uid": "0000000000000000",
                            },
                            {
                                "id": "2",
                                "tray_type": "ABS",
                                "tray_color": "F72323FF",
                                "nozzle_temp_min": "240",
                                "nozzle_temp_max": "280",
                                "remain": "0",
                                "tag_uid": "0000000000000000",
                            },
                            {"id": "3"},
                        ],
                    }
                ]
            },
        }
    }


def test_a1_bmcu_four_slots_and_two_occupied() -> None:
    telemetry = _load_telemetry_module()
    result = telemetry.normalize_ams(_realistic_a1_bmcu_payload())
    assert result["available"] is True
    assert result["kind"] == "ams_lite_compatible"
    assert result["unit_count"] == 1
    assert result["slot_count"] == 4
    assert result["occupied_slot_count"] == 2
    assert [slot["present"] for slot in result["slots"]] == [False, True, True, False]


def test_bambu_255_sentinel_means_no_active_slot() -> None:
    telemetry = _load_telemetry_module()
    result = telemetry.normalize_ams(_realistic_a1_bmcu_payload())
    assert result["active_tray"] is None
    assert result["active_tray_raw"] == "255"
    assert all(slot["active"] is False for slot in result["slots"])


def test_color_and_material_values_are_normalized() -> None:
    telemetry = _load_telemetry_module()
    result = telemetry.normalize_ams(_realistic_a1_bmcu_payload())
    pla = result["slots"][1]
    abs_slot = result["slots"][2]
    assert pla["material"] == "PLA"
    assert pla["color"] == "#000000"
    assert pla["nozzle_temp_min"] == 190.0
    assert pla["nozzle_temp_max"] == 240.0
    assert abs_slot["material"] == "ABS"
    assert abs_slot["color"] == "#F72323"


def test_zero_remaining_placeholder_is_not_reported_as_empty_spool() -> None:
    telemetry = _load_telemetry_module()
    result = telemetry.normalize_ams(_realistic_a1_bmcu_payload())
    for slot in (result["slots"][1], result["slots"][2]):
        assert slot["remaining_percent_raw"] == 0.0
        assert slot["remaining_percent"] is None
        assert slot["remaining_reliable"] is False


def test_real_remaining_value_stays_available() -> None:
    telemetry = _load_telemetry_module()
    payload = _realistic_a1_bmcu_payload()
    payload["print"]["ams"]["ams"][0]["tray"][1]["remain"] = "63"
    result = telemetry.normalize_ams(payload)
    slot = result["slots"][1]
    assert slot["remaining_percent_raw"] == 63.0
    assert slot["remaining_percent"] == 63.0
    assert slot["remaining_reliable"] is True


def test_hms_attr_and_code_become_full_bambu_hms_code() -> None:
    telemetry = _load_telemetry_module()
    state = telemetry.BambuTelemetryState()
    state.update({
        "print": {
            "gcode_state": "PAUSE",
            "hms": [{"attr": 0x03000000, "code": (2 << 16) | 0x0001}],
        }
    })
    assert len(state.hms) == 1
    issue = state.hms[0]
    assert issue["code"] == "HMS_0300-0000-0002-0001"
    assert issue["code_compact"] == "0300000000020001"
    assert issue["severity"] == "error"
    assert issue["blocking"] is True
    assert issue["help_url"].startswith("https://wiki.bambulab.com/")


def test_unknown_hms_payload_is_preserved_instead_of_dropped() -> None:
    telemetry = _load_telemetry_module()
    state = telemetry.BambuTelemetryState()
    state.update({"print": {"hms": [{"hms_code": "HMS_CUSTOM", "message": "Test"}]}})
    assert state.hms[0]["code"] == "HMS_CUSTOM"
    assert state.hms[0]["message"] == "Test"


def test_print_error_creates_resumable_issue_while_printer_is_paused() -> None:
    telemetry = _load_telemetry_module()
    state = telemetry.BambuTelemetryState()
    state.update({
        "print": {
            "gcode_state": "PAUSE",
            "print_error": 0x03008003,
            "print_error_message": "Filament wurde nicht erkannt",
        }
    })
    assert state.error_code == 0x03008003
    assert state.issues[0]["code"] == "0300-8003"
    assert state.issues[0]["resume_supported"] is True
    assert state.issues[0]["message"] == "Filament wurde nicht erkannt"


def test_issue_is_not_marked_resumable_while_printer_is_running() -> None:
    telemetry = _load_telemetry_module()
    state = telemetry.BambuTelemetryState()
    state.update({"print": {"gcode_state": "RUNNING", "print_error": 0x03008003}})
    assert state.issues[0]["resume_supported"] is False


def test_live_print_fields_use_bambu_layer_speed_and_target_keys() -> None:
    telemetry = _load_telemetry_module()
    state = telemetry.BambuTelemetryState()
    state.update({"print": {"layer_num": 38, "total_layer_num": 1118, "spd_lvl": 2, "nozzle_target_temper": 210, "bed_target_temper": 65, "wifi_signal": -47}})
    assert state.current_layer == 38
    assert state.total_layers == 1118
    assert state.speed_level == 2
    assert state.nozzle_target_temperature == 210
    assert state.bed_target_temperature == 65
    assert state.wifi_signal == -47

def test_invalid_speed_level_is_not_exposed_as_live_speed() -> None:
    telemetry = _load_telemetry_module()
    state = telemetry.BambuTelemetryState()
    state.update({"print": {"spd_lvl": 9}})
    assert state.speed_level is None


def test_current_parse_and_ams_firmware_codes_have_clear_german_text() -> None:
    telemetry = _load_telemetry_module()
    state = telemetry.BambuTelemetryState()
    state.update({
        "print": {
            "gcode_state": "FAILED",
            "print_error": 0x05004003,
            "hms": [{"attr": 83887104, "code": 65604}],
        }
    })

    issues = {issue["code"]: issue for issue in state.issues}
    assert issues["0500-4003"]["known_code"] is True
    assert issues["0500-4003"]["title"] == "Druckdatei konnte nicht verarbeitet werden"
    assert "nicht parsen" in issues["0500-4003"]["message"]
    assert issues["HMS_0500-0400-0001-0044"]["title"] == "AMS-/BMCU-Firmware nicht kompatibel"
    assert "Firmwarestände" in issues["HMS_0500-0400-0001-0044"]["message"]
