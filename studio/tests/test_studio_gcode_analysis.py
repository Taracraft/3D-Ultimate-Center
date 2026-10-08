from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest

COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "deploy/homeassistant/custom_components/ultimate_3d_studio"
)
PACKAGE = "ultimate_3d_studio"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault(PACKAGE, package)
SPEC = importlib.util.spec_from_file_location(
    f"{PACKAGE}.gcode_analysis",
    COMPONENT / "gcode_analysis.py",
)
assert SPEC and SPEC.loader
analysis = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = analysis
SPEC.loader.exec_module(analysis)


def sample(*, tower_y: float = 170.0) -> bytes:
    return (
        "; model printing time: 10m 0s; total estimated time: 12m 30s\n"
        "; filament_colour = #FF0000;#000000\n"
        "; filament_settings_id = Red PLA;Black PLA\n"
        "; filament_type = PLA;PLA\n"
        "; filament_diameter = 1.75;1.75\n"
        "; filament_density = 1.24;1.24\n"
        "; total filament length [mm] : 1000;500\n"
        "; total filament weight [g] : 3;1.5\n"
        "; layer num/total_layer_count: 1/2\n"
        "; layer_z = 0.2\n"
        "G90\nM83\nT0\n"
        "; FEATURE: Outer wall\n"
        "G1 X10 Y10 F6000\nG1 X20 Y10 E2 F1200\n"
        "; FEATURE: Inner wall\n"
        "G1 X20 Y20 E3 F1200\n"
        "T1\n"
        "; FEATURE: Prime tower\n"
        "; WIPE_TOWER_START\n"
        "G1 X267 Y128 F18000\n"
        "; FLUSH_START\n"
        "G1 E20 F300\n"
        "; FLUSH_END\n"
        f"G1 X100 Y{tower_y} F6000\n"
        f"G1 X160 Y{tower_y} E4 F1200\n"
        "; WIPE_TOWER_END\n"
        "; FEATURE: Support interface\n"
        "G1 X40 Y40 E1 F1200\n"
        "; layer num/total_layer_count: 2/2\n"
    ).encode()


def test_detailed_material_feature_and_time_analysis() -> None:
    result = analysis.analyze_gcode(sample())
    assert result["time"]["total_seconds"] == 750
    assert result["time"]["model_seconds"] == 600
    assert result["time"]["preparation_seconds"] == 150
    assert result["time"]["consistency"]["status"] == "ok"
    assert result["layer_count"] == 2
    assert result["filament_change_count"] == 1
    assert result["material_channel_count"] == 2
    assert result["totals"]["weight_g"] == 4.5
    assert len(result["materials"]) == 2
    keys = {item["key"] for item in result["features"]}
    assert {
        "outer_wall",
        "inner_wall",
        "prime_tower",
        "support_interface",
        "flush_waste",
    } <= keys
    assert all(item["time_seconds"] >= 0 for item in result["features"])
    assert result["tower_safety"]["inside_plate"] is True
    assert result["tower_safety"]["bounds"] == {
        "min_x": 100.0,
        "min_y": 170.0,
        "max_x": 160.0,
        "max_y": 170.0,
    }
    assert result["tower_safety"]["source"] == (
        "räumliche Extrusionslinien innerhalb WIPE_TOWER, ohne FLUSH"
    )


def test_tower_outside_plate_is_rejected() -> None:
    result = analysis.analyze_gcode(sample(tower_y=260))
    assert result["tower_safety"]["inside_plate"] is False
    with pytest.raises(ValueError, match="außerhalb"):
        analysis.assert_prime_tower_inside(result)


def test_selected_profile_settings_are_extracted_from_gcode_header() -> None:
    data = (
        "; layer_height = 0.20\n"
        "; wall_loops = 3\n"
        "; sparse_infill_density = 15%\n"
        "; unrelated_setting = secret\n"
        "G1 X1 Y1\n"
    ).encode()
    result = analysis.extract_gcode_settings(
        data,
        ["layer_height", "wall_loops", "sparse_infill_density"],
    )
    assert result == {
        "layer_height": ["0.20"],
        "wall_loops": ["3"],
        "sparse_infill_density": ["15%"],
    }
    assert "unrelated_setting" not in result


def test_time_consistency_reports_missing_header_fields() -> None:
    result = analysis.analyze_gcode(b"; layer num/total_layer_count: 1/1\nG90\nM83\n")
    assert result["time"]["consistency"]["status"] == "missing"
    assert result["time"]["consistency"]["source"] == "bambu_gcode_header"

def test_duration_seconds_parses_days() -> None:
    """Regression: Bambu Studio uses `3d 0h 24m 38s`; days must be parsed."""
    assert analysis._duration_seconds("3d 0h 24m 38s") == 3 * 86400 + 24 * 60 + 38
    assert analysis._duration_seconds("2d 12h 0m 0s") == 2 * 86400 + 12 * 3600
    assert analysis._duration_seconds("24m 38s") == 24 * 60 + 38
    assert analysis._duration_seconds("12h 30m") == 12 * 3600 + 30 * 60
    assert analysis._duration_seconds(None) is None
    assert analysis._duration_seconds("unknown") is None

# Mock HA modules for router tests
import sys as _sys
import types as _types

_sys.modules.setdefault("homeassistant", _types.ModuleType("homeassistant"))
_sys.modules.setdefault("homeassistant.config_entries", _types.ModuleType("homeassistant.config_entries"))
_sys.modules.setdefault("homeassistant.core", _types.ModuleType("homeassistant.core"))
_sys.modules.setdefault("homeassistant.helpers", _types.ModuleType("homeassistant.helpers"))
_sys.modules.setdefault("homeassistant.helpers.aiohttp_client", _types.ModuleType("homeassistant.helpers.aiohttp_client"))

