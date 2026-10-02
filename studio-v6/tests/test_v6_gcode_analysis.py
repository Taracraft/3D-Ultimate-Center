from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest

COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6"
)
PACKAGE = "ultimate_3d_studio_v6"
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


def test_unrealistic_short_gcode_time_is_marked_unreliable() -> None:
    source = (
        "; model printing time: 10m 0s; total estimated time: 12m 30s\n"
        "; filament_type = PLA\n"
        "; filament_diameter = 1.75\n"
        "; filament_density = 1.24\n"
        "; total filament length [mm] : 250000\n"
        "; total filament weight [g] : 750\n"
        "; total filament volume [cm^3] : 620\n"
        "; layer num/total_layer_count: 1/1000\n"
        "; layer_z = 0.2\n"
        "G90\nM83\n; FEATURE: Outer wall\nG1 X10 Y10 F6000\nG1 X20 Y10 E1 F1200\n"
    ).encode()
    result = analysis.analyze_gcode(source)
    assert result["time"]["reliable"] is False
    assert result["time"]["minimum_extrusion_seconds"] > 24 * 60 * 60
    assert "konservative" in result["time"]["warning"] or "Extrusionsminimum" in result["time"]["warning"]


def test_overhang_or_bridge_without_support_is_reported() -> None:
    source = (
        "; model printing time: 1h 0m 0s; total estimated time: 1h 2m 0s\n"
        "; filament_type = PLA\n"
        "; filament_diameter = 1.75\n"
        "; filament_density = 1.24\n"
        "G90\nM83\n"
        "; layer_z = 0.2\n"
        "; FEATURE: Overhang wall\n"
        "G1 X10 Y10 F6000\nG1 X20 Y10 E3 F1200\n"
        "; FEATURE: Bridge\n"
        "G1 X20 Y20 E2 F1200\n"
    ).encode()
    result = analysis.analyze_gcode(source)
    risk = result["support_risk"]
    assert risk["support_present"] is False
    assert risk["overhang_wall_move_count"] > 0
    assert risk["bridge_move_count"] > 0
    assert "keine Support" in risk["warning"]


def test_support_paths_suppress_overhang_warning() -> None:
    source = (
        "; model printing time: 1h 0m 0s; total estimated time: 1h 2m 0s\n"
        "; filament_type = PLA\n"
        "; filament_diameter = 1.75\n"
        "; filament_density = 1.24\n"
        "G90\nM83\n"
        "; layer_z = 0.2\n"
        "; FEATURE: Overhang wall\n"
        "G1 X10 Y10 F6000\nG1 X20 Y10 E3 F1200\n"
        "; FEATURE: Support interface\n"
        "G1 X20 Y20 E2 F1200\n"
    ).encode()
    result = analysis.analyze_gcode(source)
    risk = result["support_risk"]
    assert risk["support_present"] is True
    assert risk["warning"] is None