"""First-layer values must reach Bambu's native options without silent loss."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, COMPONENT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MATERIALIZER = load("v6_first_layer_materializer", "materialize-bambu-multimaterial.py")
NOZZLES = load("v6_first_layer_nozzles", "slicer_nozzle_profiles.py")
CONTRACT = load("v6_first_layer_process_contract", "process_profile_contract.py")


@pytest.mark.parametrize("diameter", [.2, .4, .6, .8])
def test_first_layer_native_values(diameter):
    height, width = round(diameter * .7, 2), round(diameter * 1.5, 2)
    overrides = {"nozzle_diameter_mm": diameter, "layer_height_mm": height,
                 "first_layer_height_mm": height, "initial_layer_line_width_mm": width,
                 "infill_direction_deg": 135, "initial_layer_infill_speed_mm_s": 30}
    native = {"initial_layer_infill_speed": ["60"]}
    MATERIALIZER._apply_process_overrides(native, overrides)
    for name, expected in [("layer_height", height), ("initial_layer_print_height", height),
                           ("initial_layer_line_width", width), ("infill_direction", 135)]:
        assert float(native[name]) == expected
    assert list(map(float, native["initial_layer_infill_speed"])) == [30]
    profile = {"id": "local.first-layer-test", "kind": "process", "source": "local", "name": "TaraCraft", "payload": overrides}
    result = CONTRACT.resolve_selected_process_contract({"selection": {"process_profile_id": profile["id"]}, "profiles": [profile]}, NOZZLES.a1_nozzle_contract(diameter))
    assert result["settings"]["initial_layer_line_width"] == width
    assert result["settings"]["infill_direction"] == 135


@pytest.mark.parametrize("key,value", [
    ("initial_layer_line_width_mm", .9), ("initial_layer_line_width_mm", True),
    ("infill_direction_deg", 181), ("infill_direction_deg", -1),
    ("infill_direction_deg", float("nan")), ("initial_layer_infill_speed_mm_s", 501),
])
def test_invalid_first_layer_overrides_fail_closed(key, value):
    with pytest.raises(ValueError):
        MATERIALIZER._apply_process_overrides({}, {"nozzle_diameter_mm": .4, key: value})
    profile = {"id": "local.first-layer-invalid", "kind": "process", "source": "local", "name": "Invalid", "payload": {key: value}}
    with pytest.raises(ValueError):
        CONTRACT.resolve_selected_process_contract({"selection": {"process_profile_id": profile["id"]}, "profiles": [profile]}, NOZZLES.a1_nozzle_contract(.4))
