from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
)


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


NOZZLES = _module(
    "v6_process_contract_nozzles",
    COMPONENT / "slicer_nozzle_profiles.py",
)
CONTRACTS = _module(
    "v6_process_profile_contract",
    COMPONENT / "process_profile_contract.py",
)


def _catalog(profile: dict[str, object]) -> dict[str, object]:
    return {
        "selection": {"process_profile_id": profile["id"]},
        "profiles": [profile],
    }


def test_local_profile_is_mapped_completely_and_hashed() -> None:
    profile = {
        "id": "local.process.a1_0_12_hq",
        "kind": "process",
        "name": "A1 0,12 mm High Quality",
        "source": "local",
        "payload": {
            "layer_height_mm": .12,
            "first_layer_height_mm": .20,
            "walls": 3,
            "top_shell_layers": 6,
            "bottom_shell_layers": 5,
            "infill_percent": 15,
            "outer_wall_speed_mm_s": 50,
            "inner_wall_speed_mm_s": 100,
            "travel_speed_mm_s": 450,
            "profile_origin": "V6 curated local catalog",
            "cloud_sync_protected": True,
        },
    }
    result = CONTRACTS.resolve_selected_process_contract(
        _catalog(profile),
        NOZZLES.a1_nozzle_contract(.2),
    )
    assert result["profile_id"] == profile["id"]
    assert result["native_base_profile"].endswith(
        "0.10mm Standard @BBL A1 0.2 nozzle.json"
    )
    assert result["settings"] == {
        "layer_height": .12,
        "initial_layer_print_height": .20,
        "wall_loops": 3,
        "top_shell_layers": 6,
        "bottom_shell_layers": 5,
        "sparse_infill_density": "15%",
        "outer_wall_speed": 50,
        "inner_wall_speed": 100,
        "travel_speed": 450,
    }
    assert len(result["contract_sha256"]) == 64


def test_variable_layer_height_ranges_are_nozzle_validated() -> None:
    result = NOZZLES.validate_process_overrides(
        {
            "layer_height_ranges": [
                {"min_z_mm": 0, "max_z_mm": 5, "layer_height_mm": .12},
                {"min_z": 5, "max_z": 12, "layer_height": .2},
            ],
        },
        NOZZLES.a1_nozzle_contract(.4),
    )
    assert result["layer_height_ranges"] == [
        {"min_z_mm": 0.0, "max_z_mm": 5.0, "layer_height_mm": .12},
        {"min_z_mm": 5.0, "max_z_mm": 12.0, "layer_height_mm": .2},
    ]


@pytest.mark.parametrize(
    "ranges",
    [
        [{"min_z_mm": 0, "max_z_mm": 4, "layer_height_mm": True}],
        [{"min_z_mm": 0, "max_z_mm": 4, "layer_height_mm": .2}],
        [
            {"min_z_mm": 0, "max_z_mm": 5, "layer_height_mm": .1},
            {"min_z_mm": 4, "max_z_mm": 8, "layer_height_mm": .1},
        ],
        [{"min_z_mm": 0, "max_z_mm": 300, "layer_height_mm": .1}],
    ],
)
def test_variable_layer_height_ranges_reject_invalid_values(ranges: list[dict[str, object]]) -> None:
    with pytest.raises(NOZZLES.NozzleProfileError):
        NOZZLES.validate_process_overrides(
            {"layer_height_ranges": ranges},
            NOZZLES.a1_nozzle_contract(.2),
        )


def test_process_outside_selected_nozzle_is_rejected() -> None:
    profile = {
        "id": "local.process.a1_0_20_standard",
        "kind": "process",
        "name": "A1 0,20 mm Standard",
        "source": "local",
        "payload": {"layer_height_mm": .20},
    }
    with pytest.raises(
        CONTRACTS.ProcessProfileContractError,
        match="Düsenbereich",
    ):
        CONTRACTS.resolve_selected_process_contract(
            _catalog(profile),
            NOZZLES.a1_nozzle_contract(.2),
        )


def test_cloud_profile_can_use_validated_base_without_own_overlay() -> None:
    profile = {
        "id": "cloud.process.base_only",
        "kind": "process",
        "name": "Cloud base only",
        "source": "bambu_cloud",
        "payload": {
            "inherits": "0.20mm Standard @BBL A1",
            "_bambu_cloud": {"private": "metadata"},
        },
    }
    result = CONTRACTS.resolve_selected_process_contract(
        _catalog(profile),
        NOZZLES.a1_nozzle_contract(.4),
    )
    assert result["settings"] == {}
    assert result["materialization_policy"] == "exact_bambu_cloud_overlay"
    assert result["native_base_profile"].endswith(
        "0.20mm Standard @BBL A1.json"
    )


def test_cloud_profile_must_inherit_exact_native_nozzle_base() -> None:
    profile = {
        "id": "cloud.process.good",
        "kind": "process",
        "name": "Cloud exact",
        "source": "bambu_cloud",
        "payload": {
            "inherits": "0.20mm Standard @BBL A1",
            "wall_loops": "4",
            "_bambu_cloud": {"private": "metadata"},
        },
    }
    result = CONTRACTS.resolve_selected_process_contract(
        _catalog(profile),
        NOZZLES.a1_nozzle_contract(.4),
    )
    assert result["settings"] == {"wall_loops": "4"}
    with pytest.raises(
        CONTRACTS.ProcessProfileContractError,
        match="validierten Düsenprofil",
    ):
        CONTRACTS.resolve_selected_process_contract(
            _catalog(profile),
            NOZZLES.a1_nozzle_contract(.2),
        )


def test_unknown_local_setting_is_never_silently_dropped() -> None:
    profile = {
        "id": "local.process.unknown",
        "kind": "process",
        "name": "Unbekannt",
        "source": "local",
        "payload": {
            "layer_height_mm": .2,
            "not_materialized_yet": 42,
        },
    }
    with pytest.raises(
        CONTRACTS.ProcessProfileContractError,
        match="nicht materialisierbare",
    ):
        CONTRACTS.resolve_selected_process_contract(
            _catalog(profile),
            NOZZLES.a1_nozzle_contract(.4),
        )


def test_nozzle_specific_a1_metadata_is_validated_not_materialized() -> None:
    profile = {
        "id": "local.process.a1_0_6_0_30_standard",
        "kind": "process",
        "name": "Bambu Lab A1 · 0,6 mm Düse · 0,30 mm Standard",
        "source": "local",
        "payload": {
            "printer_vendor": "Bambu Lab",
            "printer_model": "A1",
            "target_printer": "Bambu Lab A1",
            "a1_specific": True,
            "nozzle_diameter_mm": .6,
            "material_class": "PETG",
            "layer_height_mm": .3,
            "walls": 3,
        },
    }
    result = CONTRACTS.resolve_selected_process_contract(
        _catalog(profile),
        NOZZLES.a1_nozzle_contract(.6),
    )
    assert result["settings"] == {
        "layer_height": .3,
        "wall_loops": 3,
    }


def test_nozzle_specific_metadata_mismatch_is_rejected() -> None:
    profile = {
        "id": "local.process.a1_0_4_0_20_standard",
        "kind": "process",
        "name": "Bambu Lab A1 · 0,4 mm Düse · 0,20 mm Standard",
        "source": "local",
        "payload": {
            "printer_vendor": "Bambu Lab",
            "printer_model": "A1",
            "target_printer": "Bambu Lab A1",
            "a1_specific": True,
            "nozzle_diameter_mm": .4,
            "layer_height_mm": .2,
        },
    }
    with pytest.raises(
        CONTRACTS.ProcessProfileContractError,
        match="Düsendurchmesser",
    ):
        CONTRACTS.resolve_selected_process_contract(
            _catalog(profile),
            NOZZLES.a1_nozzle_contract(.6),
        )



def test_advanced_editor_values_are_materialized_without_loss():
    values = {
        "line_width_mm": 0.3,
        "outer_wall_line_width_mm": 0.3,
        "inner_wall_line_width_mm": 0.3,
        "top_surface_line_width_mm": 0.3,
        "support_line_width_mm": 0.3,
        "sparse_infill_speed_mm_s": 1,
        "internal_solid_infill_speed_mm_s": 1,
        "top_surface_speed_mm_s": 1,
        "initial_layer_speed_mm_s": 1,
        "bridge_speed_mm_s": 1,
        "gap_infill_speed_mm_s": 1,
        "solid_infill_speed_mm_s": 1,
        "ironing_speed_mm_s": 1,
        "support_speed_mm_s": 1,
        "support_interface_speed_mm_s": 1,
        "bridge_flow_ratio": 0.95,
        "support_top_z_distance_mm": 0.3,
        "support_bottom_z_distance_mm": 0.3,
        "support_object_xy_distance_mm": 0.3,
        "support_interface_spacing_mm": 0.3,
        "support_interface_top_layers": 2,
        "support_interface_bottom_layers": 2,
        "infill_pattern": "gyroid",
        "wall_sequence": "inner outer",
        "seam_position": "aligned",
    }
    profile = {"id": "local.advanced", "kind": "process", "name": "Advanced", "source": "local", "payload": values}
    result = CONTRACTS.resolve_selected_process_contract(_catalog(profile), NOZZLES.a1_nozzle_contract(.4))
    assert result["settings"] == {
        "line_width": 0.3,
        "outer_wall_line_width": 0.3,
        "inner_wall_line_width": 0.3,
        "top_surface_line_width": 0.3,
        "support_line_width": 0.3,
        "sparse_infill_speed": 1,
        "internal_solid_infill_speed": 1,
        "top_surface_speed": 1,
        "initial_layer_speed": 1,
        "bridge_speed": 1,
        "gap_infill_speed": 1,
        "solid_infill_speed": 1,
        "ironing_speed": 1,
        "support_speed": 1,
        "support_interface_speed": 1,
        "bridge_flow": 0.95,
        "support_top_z_distance": 0.3,
        "support_bottom_z_distance": 0.3,
        "support_object_xy_distance": 0.3,
        "support_interface_spacing": 0.3,
        "support_interface_top_layers": 2,
        "support_interface_bottom_layers": 2,
        "infill_pattern": "gyroid",
        "wall_sequence": "inner outer",
        "seam_position": "aligned",
    }
    assert profile["payload"] == values


@pytest.mark.parametrize("key, minimum, integer", [(key, *rule) for key, rule in CONTRACTS._ADVANCED_NUMERIC_RULES.items()])
def test_advanced_editor_rejects_invalid_values(key, minimum, integer):
    invalid = [True, None, "", float("inf"), float("nan"), minimum - .01]
    if integer:
        invalid.append(1.5)
    for value in invalid:
        profile = {"id": "local.invalid", "kind": "process", "name": "Invalid", "source": "local", "payload": {key: value}}
        with pytest.raises(CONTRACTS.ProcessProfileContractError):
            CONTRACTS.resolve_selected_process_contract(_catalog(profile), NOZZLES.a1_nozzle_contract(.4))

def test_support_build_plate_only_accepts_string_false_for_model_contact() -> None:
    contract = NOZZLES.a1_nozzle_contract(0.4)
    result = NOZZLES.validate_process_overrides(
        {
            "support_mode": "tree",
            "support_style": "tree_organic",
            "support_build_plate_only": "false",
            "support_threshold_angle": 20,
        },
        contract,
    )
    assert result["support_style"] == "tree_organic"
    assert result["support_build_plate_only"] is False
    assert result["support_threshold_angle"] == 20


def test_process_override_contract_is_wired_from_frontend_to_native_materializer() -> None:
    frontend = (ROOT / "frontend" / "plate-slice-api.ts").read_text(encoding="utf-8-sig")
    panel = (ROOT / "frontend" / "studio-process-options-panel.ts").read_text(encoding="utf-8-sig")
    views = (COMPONENT / "slicer_plate_views_v2.py").read_text(encoding="utf-8-sig")
    materializer = (COMPONENT / "materialize-bambu-multimaterial.py").read_text(encoding="utf-8-sig")

    expected = {
        "layer_height_mm": "layer_height",
        "first_layer_height_mm": "initial_layer_print_height",
        "walls": "wall_loops",
        "top_shell_layers": "top_shell_layers",
        "bottom_shell_layers": "bottom_shell_layers",
        "infill_percent": "sparse_infill_density",
        "outer_wall_speed_mm_s": "outer_wall_speed",
        "inner_wall_speed_mm_s": "inner_wall_speed",
        "travel_speed_mm_s": "travel_speed",
        "line_width_mm": "line_width",
        "outer_wall_line_width_mm": "outer_wall_line_width",
        "inner_wall_line_width_mm": "inner_wall_line_width",
        "top_surface_line_width_mm": "top_surface_line_width",
        "support_line_width_mm": "support_line_width",
        "sparse_infill_speed_mm_s": "sparse_infill_speed",
        "internal_solid_infill_speed_mm_s": "internal_solid_infill_speed",
        "top_surface_speed_mm_s": "top_surface_speed",
        "initial_layer_speed_mm_s": "initial_layer_speed",
        "bridge_speed_mm_s": "bridge_speed",
        "gap_infill_speed_mm_s": "gap_infill_speed",
        "solid_infill_speed_mm_s": "solid_infill_speed",
        "ironing_speed_mm_s": "ironing_speed",
        "support_speed_mm_s": "support_speed",
        "support_interface_speed_mm_s": "support_interface_speed",
        "bridge_flow_ratio": "bridge_flow",
        "support_top_z_distance_mm": "support_top_z_distance",
        "support_bottom_z_distance_mm": "support_bottom_z_distance",
        "support_object_xy_distance_mm": "support_object_xy_distance",
        "support_interface_spacing_mm": "support_interface_spacing",
        "support_interface_top_layers": "support_interface_top_layers",
        "support_interface_bottom_layers": "support_interface_bottom_layers",
    }

    assert "for (const field of PROCESS_EDITOR_FIELDS)" in frontend
    assert "[data-process-editor-field]" in panel
    assert "_PROCESS_OVERRIDE_QUERY_RULES" in views
    assert "_PROCESS_OVERRIDE_MAP" in materializer
    assert "set(_PROCESS_OVERRIDE_MAP.values())" in materializer
    assert "processEditorRows(value, nozzleDiameter)" in panel
    assert "for (const field of PROCESS_EDITOR_FIELDS)" in frontend
    for frontend_key, native_key in expected.items():
        assert frontend_key in views
        assert frontend_key in materializer
        assert native_key in materializer


def test_support_interface_bottom_layers_must_be_integer() -> None:
    profile = {
        "id": "local.bad-bottom-layers",
        "kind": "process",
        "name": "Bad Bottom Layers",
        "source": "local",
        "payload": {"support_interface_bottom_layers": 1.5},
    }
    with pytest.raises(CONTRACTS.ProcessProfileContractError, match="support_interface_bottom_layers"):
        CONTRACTS.resolve_selected_process_contract(_catalog(profile), NOZZLES.a1_nozzle_contract(.4))


def test_empty_legacy_sound_fields_do_not_block_local_process() -> None:
    profile = {"id": "local.test", "name": "A1 0.20 Test", "kind": "process", "source": "local", "payload": {
        "layer_height_mm": .20, "start_sound_gcode": "", "end_sound_gcode": " ",
        "custom_gcode_1": "", "custom_gcode_2": ""}}
    result = CONTRACTS.resolve_selected_process_contract(_catalog(profile), NOZZLES.a1_nozzle_contract(.4))
    assert result["settings"] == {"layer_height": .20}
    profile["payload"]["custom_gcode_1"] = "M400"
    with pytest.raises(CONTRACTS.ProcessProfileContractError, match="custom_gcode_1"):
        CONTRACTS.resolve_selected_process_contract(_catalog(profile), NOZZLES.a1_nozzle_contract(.4))
