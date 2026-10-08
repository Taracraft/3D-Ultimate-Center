"""Tests for slicer warning and metrics functions (HA-independent)."""
from __future__ import annotations


# Exercise the deployed implementations. A copied test implementation previously
# hid a NameError in the real floating-object warning path.
import ast
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio/slicer_backend_router.py"
NAMES = {"_build_detailed_warning", "_engine_result_metrics"}
tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))
module = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in NAMES], type_ignores=[])
namespace = {"Any": Any}
exec(compile(module, str(SOURCE), "exec"), namespace)
_build_detailed_warning = namespace["_build_detailed_warning"]
_engine_result_metrics = namespace["_engine_result_metrics"]


def test_build_detailed_warning_returns_none_when_no_original_warning():
    """Wenn keine Warnung existiert, soll None zurückgegeben werden."""
    plate = {"feature_type_times": {}, "objects": []}
    result = _build_detailed_warning(plate, None)
    assert result is None


def test_build_detailed_warning_returns_original_when_no_bridge_or_overhang():
    """Wenn keine Bridges oder Overhangs vorhanden sind, wird die ursprüngliche Warnung zurückgegeben."""
    plate = {
        "feature_type_times": {},
        "objects": [],
        "warning_message": "Allgemeine Warnung"
    }
    result = _build_detailed_warning(plate, "Allgemeine Warnung")
    assert result == "Allgemeine Warnung"


def test_build_detailed_warning_with_bridge_time():
    """Testet Bridge-Zeitberechnung."""
    plate = {
        "feature_type_times": {"bridge": 5840.0},
        "objects": [],
        "warning_message": "Warning: floating regions detected"
    }
    result = _build_detailed_warning(plate, "Warning: floating regions detected")
    assert "Bridge: 1h 37m 20s" in result
    assert "floating regions detected" in result


def test_build_detailed_warning_with_floating_object():
    """Testet detaillierte Objektwarnung mit Position und Größe."""
    plate = {
        "feature_type_times": {"bridge": 100.0},
        "objects": [
            {
                "name": "v2",
                "id": 5,
                "warning_message": "It seems object v2 has floating regions.",
                "bbox": {"x": 38.0, "y": 8.0, "width": 180.0, "depth": 240.0, "height": 223.5}
            }
        ],
        "warning_message": "Floating regions detected"
    }
    result = _build_detailed_warning(plate, "Floating regions detected")
    assert "Floating regions detected:" in result
    assert "v2" in result
    assert "Position (38.0, 8.0)mm" in result
    assert "Size 180.0x240.0x223.5mm" in result


def test_engine_result_metrics_returns_detailed_warning():
    """Testet dass _engine_result_metrics die detaillierte Warnung verwendet."""
    engine_result = {
        "return_code": 0,
        "error_string": "Success.",
        "layer_height": 0.2,
        "plate_index": 0,
        "sliced_plates": [
            {
                "id": 1,
                "feature_type_times": {"bridge": 5840.0, "overhang wall": 540.0},
                "filaments": [{"id": 1, "total_used_g": 10.5}],
                "total_predication": 300000.0,
                "main_predication": 260000.0,
                "sliced_time": 32000,
                "filament_change_times": 0,
                "triangle_count": 100000,
                "objects": [
                    {
                        "name": "test_object",
                        "id": 1,
                        "warning_message": "Floating region detected",
                        "bbox": {"x": 100.0, "y": 100.0, "width": 50.0, "depth": 50.0, "height": 30.0}
                    }
                ],
                "warning_message": "Warning: floating regions detected"
            }
        ]
    }
    
    result = _engine_result_metrics(engine_result, requested_plate_index=0)
    
    assert "floating regions detected" in result["warning"]
    assert "Bridge: 1h 37m 20s" in result["warning"]
    assert "Overhang: 9m 00s" in result["warning"]
    assert "Position (100.0, 100.0)mm" in result["warning"]
    assert "Size 50.0x50.0x30.0mm" in result["warning"]
