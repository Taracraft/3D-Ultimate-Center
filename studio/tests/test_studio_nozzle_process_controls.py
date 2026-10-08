from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
COMPONENT = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio"
)
HOST = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "host"
    / "3d-printer-slicing-server"
)


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


NOZZLES = _module("studio_slicer_nozzle_profiles", COMPONENT / "slicer_nozzle_profiles.py")
MATERIALIZER = _module(
    "studio_materialize_bambu_multimaterial",
    COMPONENT / "materialize-bambu-multimaterial.py",
)


EXPECTED = {
    .2: (
        "BBL/machine/Bambu Lab A1 0.2 nozzle.json",
        "BBL/process/0.10mm Standard @BBL A1 0.2 nozzle.json",
        .04,
        .14,
        .1,
        120,
        150,
    ),
    .4: (
        "BBL/machine/Bambu Lab A1 0.4 nozzle.json",
        "BBL/process/0.20mm Standard @BBL A1.json",
        .08,
        .28,
        .2,
        200,
        300,
    ),
    .6: (
        "BBL/machine/Bambu Lab A1 0.6 nozzle.json",
        "BBL/process/0.30mm Strength @BBL A1 0.6 nozzle.json",
        .12,
        .42,
        .3,
        120,
        150,
    ),
    .8: (
        "BBL/machine/Bambu Lab A1 0.8 nozzle.json",
        "BBL/process/0.40mm Standard @BBL A1 0.8 nozzle.json",
        .16,
        .56,
        .4,
        120,
        150,
    ),
}


def _catalog(diameter: float, printer_diameter: float | None = None) -> dict:
    return {
        "selection": {
            "nozzle_profile_id": f"nozzle-{diameter:g}",
            "printer_profile_id": f"printer-{diameter:g}",
        },
        "profiles": [
            {
                "id": f"nozzle-{diameter:g}",
                "kind": "nozzle",
                "payload": {
                    "diameter_mm": diameter,
                    "printer": "Bambu Lab A1",
                },
            },
            {
                "id": f"printer-{diameter:g}",
                "kind": "printer",
                "payload": {
                    "model": "A1",
                    "nozzle_diameter_mm": (
                        diameter if printer_diameter is None else printer_diameter
                    ),
                },
            },
        ],
    }


def test_all_installed_a1_nozzle_contracts_are_exact() -> None:
    assert len(NOZZLES.A1_NOZZLE_CONTRACTS) == 4
    for diameter, expected in EXPECTED.items():
        contract = NOZZLES.a1_nozzle_contract(diameter)
        actual = (
            contract.machine_profile,
            contract.process_profile,
            contract.min_layer_height_mm,
            contract.max_layer_height_mm,
            contract.default_layer_height_mm,
            contract.default_outer_wall_speed_mm_s,
            contract.default_inner_wall_speed_mm_s,
        )
        assert actual == expected
        assert contract.max_wall_speed_mm_s == 500


@pytest.mark.parametrize("diameter", sorted(EXPECTED))
def test_selection_resolves_matching_a1_printer_and_nozzle(diameter: float) -> None:
    contract = NOZZLES.resolve_a1_nozzle_contract(
        _catalog(diameter),
        {"model": "Bambu Lab A1"},
    )
    assert contract.diameter_mm == diameter


def test_mismatched_printer_nozzle_and_a1_mini_are_rejected() -> None:
    with pytest.raises(NOZZLES.NozzleProfileError, match="unterschiedliche"):
        NOZZLES.resolve_a1_nozzle_contract(
            _catalog(.2, printer_diameter=.4),
            {"model": "Bambu Lab A1"},
        )
    with pytest.raises(NOZZLES.NozzleProfileError, match="ausschließlich"):
        NOZZLES.resolve_a1_nozzle_contract(
            _catalog(.4),
            {"model": "Bambu Lab A1 mini"},
        )


@pytest.mark.parametrize("diameter", sorted(EXPECTED))
def test_exact_layer_boundaries_and_wall_speeds_are_accepted(diameter: float) -> None:
    contract = NOZZLES.a1_nozzle_contract(diameter)
    validated = NOZZLES.validate_process_overrides(
        {
            "layer_height_mm": contract.min_layer_height_mm,
            "outer_wall_speed_mm_s": 1,
            "inner_wall_speed_mm_s": contract.max_wall_speed_mm_s,
        },
        contract,
    )
    assert validated["layer_height_mm"] == contract.min_layer_height_mm
    assert validated["outer_wall_speed_mm_s"] == 1
    assert validated["inner_wall_speed_mm_s"] == 500


@pytest.mark.parametrize("diameter", sorted(EXPECTED))
def test_out_of_range_layer_is_rejected_for_each_nozzle(diameter: float) -> None:
    contract = NOZZLES.a1_nozzle_contract(diameter)
    for invalid in (
        contract.min_layer_height_mm - .001,
        contract.max_layer_height_mm + .001,
    ):
        with pytest.raises(NOZZLES.NozzleProfileError, match="Schichthöhe"):
            NOZZLES.validate_process_overrides(
                {"layer_height_mm": invalid},
                contract,
            )


def test_standard_values_remain_absent_and_custom_values_preserve_profile_type() -> None:
    overrides: dict[str, object] = {}
    process = {
        "layer_height": "0.2",
        "outer_wall_speed": ["200"],
        "inner_wall_speed": ["300"],
    }
    for override_key, process_key, minimum, maximum in (
        ("layer_height_mm", "layer_height", .04, .56),
        ("outer_wall_speed_mm_s", "outer_wall_speed", 1, 500),
        ("inner_wall_speed_mm_s", "inner_wall_speed", 1, 500),
    ):
        assert MATERIALIZER._required_override_number(
            overrides, override_key, minimum, maximum
        ) is None
        assert process[process_key] in ("0.2", ["200"], ["300"])

    assert MATERIALIZER._as_profile_value("80", process["outer_wall_speed"]) == ["80"]
    assert MATERIALIZER._as_profile_value("120", process["inner_wall_speed"]) == ["120"]
    assert MATERIALIZER._as_profile_value("0.12", process["layer_height"]) == "0.12"


def test_frontend_has_standard_controls_and_only_sends_custom_values() -> None:
    api = (FRONTEND / "plate-slice-api.ts").read_text(encoding="utf-8-sig")
    contract = (FRONTEND / "nozzle-process-contract.ts").read_text(encoding="utf-8-sig")
    ui = (FRONTEND / "studio-profile-ui.ts").read_text(encoding="utf-8-sig")
    workspace = (FRONTEND / "studio-mega-workspace-v2.ts").read_text(
        encoding="utf-8-sig"
    )
    for field in (
        "layer_height_mm",
        "outer_wall_speed_mm_s",
        "inner_wall_speed_mm_s",
    ):
        assert f"overrides.{field} !== null" in api
        assert f'query.set("{field}"' in api
        assert f'data-process-override="{field}"' in ui
    assert "Standard ·" in ui
    assert 'from "./nozzle-process-contract.js"' in ui
    assert "profilebar-process-field" not in ui
    assert "<small>Leer = Standardprofil</small>" not in ui
    assert 'title="Leer = Standardprofil' in ui
    assert 'import "./direct-print-panel.js"' not in contract
    assert "processOverrideValidationError" in workspace
    assert "#selectedNozzleDiameter()" in workspace
    panel = (FRONTEND / "studio-process-options-panel.ts").read_text(encoding="utf-8-sig")
    mega_ui = (FRONTEND / "studio-mega-ui-v2.ts").read_text(encoding="utf-8-sig")
    assert 'from "./nozzle-process-contract.js"' in panel
    assert "nozzleLayerHeightPresetValues" in panel
    assert "nearestLayerHeightPreset" in panel
    assert "nozzleLayerHeightBounds" in panel
    assert "Schichthoehe fuer ${bounds.label}" in panel
    assert 'min="${bounds.minimum}" max="${bounds.maximum}"' in panel
    assert "[data-layer-height-preset]" in panel
    assert '"nozzle-diameter"' in panel
    assert 'nozzle-diameter="${state.activeNozzleDiameter ?? ""}"' in mega_ui
    assert 'preview-z-mm="${state.visibleLayerZ ?? ""}"' in mega_ui
    assert "activeNozzleDiameter: this.#selectedNozzleDiameter()" in workspace
    assert "visibleLayerZ: plate.layers[plate.visibleLayer]?.z ?? null" in workspace
    assert '"preview-z-mm"' in panel
    assert "activeIndex" in panel
    assert "range-curve-bar " in panel


def test_native_dispatcher_selects_profiles_from_validated_job_only() -> None:
    for path in (
        HOST / "dispatch-job.sh",
        COMPONENT / "dispatch-job-options.sh",
    ):
        source = path.read_text(encoding="utf-8-sig")
        assert "MACHINE=$(jq -r '.native_machine_profile // empty'" in source
        assert "PROCESS=$(jq -r '.native_process_profile // empty'" in source
        assert "Native A1 nozzle profile contract is invalid." in source
        assert "Materialized nozzle diameter does not match" in source
        for machine, process, *_ in EXPECTED.values():
            assert machine in source
            assert process in source


def test_no_computer_runtime_dependency_is_added() -> None:
    joined = "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in (
            COMPONENT / "slicer_backend_router.py",
            COMPONENT / "slicer_plate_views_v2.py",
            HOST / "server.py",
            HOST / "dispatch-job.sh",
        )
    ).casefold()
    for forbidden in (
        "pc-worker",
        "pc-slicer",
        "localhost:5000",
        "127.0.0.1:5000",
    ):
        assert forbidden not in joined
    assert "127.0.0.1:8099" in joined


def test_contract_payload_is_json_serializable() -> None:
    for diameter in EXPECTED:
        encoded = json.dumps(
            NOZZLES.contract_payload(NOZZLES.a1_nozzle_contract(diameter))
        )
        assert f'"nozzle_diameter_mm": {diameter}' in encoded
