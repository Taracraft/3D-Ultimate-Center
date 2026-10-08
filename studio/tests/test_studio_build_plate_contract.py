from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio"
MODULE_PATH = COMPONENT / "build_plate_contract.py"

spec = importlib.util.spec_from_file_location("studio_build_plate_contract", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def catalog(surface: str) -> dict[str, object]:
    profile_id = f"build_plate.{surface}"
    return {
        "selection": {"build_plate_profile_id": profile_id},
        "profiles": [{
            "id": profile_id,
            "kind": "build_plate",
            "name": surface,
            "payload": {"surface": surface, "width_mm": 256, "depth_mm": 256},
        }],
    }


@pytest.mark.parametrize(
    ("surface", "bed_type"),
    [
        ("cool_plate", "Cool Plate"),
        ("engineering_plate", "Engineering Plate"),
        ("smooth_pei", "High Temp Plate"),
        ("textured_pei", "Textured PEI Plate"),
        ("cool_plate_super_tack", "Supertack Plate"),
    ],
)
def test_all_bambu_studio_plate_choices_map_to_native_bed_types(
    surface: str,
    bed_type: str,
) -> None:
    result = module.selected_build_plate_options(catalog(surface))
    assert result["build_plate_surface"] == surface
    assert result["bambu_bed_type"] == bed_type
    assert result["build_plate_width_mm"] == 256
    assert result["build_plate_depth_mm"] == 256


def test_unknown_build_plate_surface_is_rejected() -> None:
    with pytest.raises(ValueError, match="nicht unterstützt"):
        module.selected_build_plate_options(catalog("unknown_surface"))


def test_every_native_bed_type_uses_the_correct_filament_temperature_field() -> None:
    helper_source = (COMPONENT / "bed-temperature-contract.sh").read_text(encoding="utf-8")
    expected = {
        "Textured PEI Plate": "textured_plate_temp_initial_layer",
        "High Temp Plate": "hot_plate_temp_initial_layer",
        "Cool Plate": "cool_plate_temp_initial_layer",
        "Engineering Plate": "eng_plate_temp_initial_layer",
        "Supertack Plate": "supertack_plate_temp_initial_layer",
    }
    for bed_type, temperature_key in expected.items():
        assert f"'{bed_type}') echo {temperature_key}" in helper_source


def test_server_and_worker_are_wired_to_the_contract() -> None:
    view_source = (COMPONENT / "slicer_plate_views_v2.py").read_text(encoding="utf-8")
    helper_source = (COMPONENT / "bed-temperature-contract.sh").read_text(encoding="utf-8")
    dispatcher_source = (COMPONENT / "dispatch-job-options.sh").read_text(encoding="utf-8")
    assert "build_plate_options = selected_build_plate_options(catalog)" in view_source
    assert "options.update(build_plate_options)" in view_source
    assert "apply_bed_type_contract" in helper_source
    assert "validate_bed_type_contract" in helper_source
    assert "M140 S" in helper_source and "M190 S" in helper_source
    assert "curr_bed_type:$bed_type" in dispatcher_source
