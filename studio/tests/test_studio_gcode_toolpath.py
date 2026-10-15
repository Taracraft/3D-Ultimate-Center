from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "deploy/homeassistant/custom_components/ultimate_3d_studio"
)
MODULE_NAME = "ultimate_3d_studio.gcode_toolpath"
SPEC = importlib.util.spec_from_file_location(MODULE_NAME, COMPONENT / "gcode_toolpath.py")
assert SPEC and SPEC.loader
toolpath = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = toolpath
SPEC.loader.exec_module(toolpath)


def parse(source: str) -> dict[str, object]:
    return toolpath.parse_toolpath(source.encode("utf-8"), start_layer=0, end_layer=20)


def test_start_gcode_is_not_counted_as_print_layer() -> None:
    result = parse(
        "\n".join(
            [
                "; filament_colour = #FF0000;#00FF00",
                "M83",
                "G1 X10 Y10 E1 ; calibration line",
                "; CHANGE_LAYER",
                "; Z_HEIGHT: 0.2",
                "; FEATURE: Brim",
                "G1 X20 Y20 E1",
                "; CHANGE_LAYER",
                "; Z_HEIGHT: 0.4",
                "; FEATURE: Outer wall",
                "G1 X30 Y20 E1",
                "; MACHINE_END_GCODE_START",
                "G1 X200 Y200 E20",
            ]
        )
    )
    assert result["layer_count"] == 2
    assert result["filament_colors"] == ["#FF0000", "#00FF00"]
    assert result["feature_first_layers"] == {"brim": 0, "model": 1}
    assert result["bounds"] == {
        "min_x": 10.0,
        "min_y": 10.0,
        "min_z": 0.2,
        "max_x": 30.0,
        "max_y": 20.0,
        "max_z": 0.4,
    }


def test_g92_absolute_extruder_reset_preserves_positive_paths() -> None:
    result = parse(
        "\n".join(
            [
                "M82",
                "; Z_HEIGHT: 0.2",
                "; FEATURE: Outer wall",
                "G1 X10 Y0 E5",
                "G92 E0",
                "G1 X20 Y0 E2",
            ]
        )
    )
    layers = result["chunk"]["layers"]
    assert len(layers) == 1
    assert len(layers[0]["segments"]) == 2
    assert layers[0]["extrusion_mm"] == 7.0


def test_arc_extrusion_is_interpolated_and_keeps_feature() -> None:
    result = parse(
        "\n".join(
            [
                "M83",
                "; Z_HEIGHT: 0.2",
                "; FEATURE: Support interface",
                "G1 X10 Y0",
                "G3 X0 Y10 I-10 J0 E2",
            ]
        )
    )
    layer = result["chunk"]["layers"][0]
    assert len(layer["segments"]) > 4
    assert set(segment[8] for segment in layer["segments"]) == {"support"}
    assert abs(layer["extrusion_mm"] - 2.0) < 0.001
