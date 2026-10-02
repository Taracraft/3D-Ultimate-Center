from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
)
PACKAGE = "v6_compatibility_test_package"


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = types.ModuleType(PACKAGE)
package.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE] = package
_module(f"{PACKAGE}.a1_filament_catalog", COMPONENT / "a1_filament_catalog.py")
_module(f"{PACKAGE}.filament_profile_mapping", COMPONENT / "filament_profile_mapping.py")
NOZZLES = _module(
    f"{PACKAGE}.slicer_nozzle_profiles",
    COMPONENT / "slicer_nozzle_profiles.py",
)
CONTRACT = _module(
    f"{PACKAGE}.slicer_compatibility_contract",
    COMPONENT / "slicer_compatibility_contract.py",
)


def _filament_profile(
    *,
    profile_id: str = "local.filament.generic_pla",
    name: str = "Generic PLA",
    material: str = "PLA",
    nozzle: list[int] | None = None,
    bed: int = 55,
    enclosure: str = "optional",
    hardened: bool = False,
    ams: bool = True,
) -> dict[str, object]:
    return {
        "id": profile_id,
        "kind": "filament",
        "name": name,
        "source": "local",
        "payload": {
            "vendor": "Generic",
            "material": material,
            "nozzle_temperature_c": nozzle or [190, 230],
            "bed_temperature_c": bed,
            "enclosure": enclosure,
            "hardened_nozzle_required": hardened,
            "ams_lite_compatible": ams,
            "profile_completeness": "validated_complete",
            "slicing_supported": True,
            "native_profile_name": f"Generic {material} @BBL A1",
        },
    }


def _catalog(
    filament: dict[str, object],
    *,
    nozzle_material: str = "hardened_steel",
    diameter: float = .4,
) -> dict[str, object]:
    return {
        "selection": {
            "nozzle_profile_id": "nozzle",
            "filament_profile_ids": [filament["id"]],
        },
        "profiles": [
            {
                "id": "nozzle",
                "kind": "nozzle",
                "name": "A1 nozzle",
                "payload": {
                    "diameter_mm": diameter,
                    "material": nozzle_material,
                    "printer": "Bambu Lab A1",
                },
            },
            filament,
        ],
    }


def _plan(
    *,
    source: str = "authoritative_ams_runtime",
    material: str = "PLA",
    filament_id: str = "GFL99",
) -> dict[str, object]:
    return {
        "source": source,
        "assignments": {"1": 1},
        "filaments": [{
            "extruder": 1,
            "name": material,
            "material": material,
            "color": "#101010",
            "filament_id": filament_id,
        }],
        "purge_tower": {"enabled": False},
    }


PLATE = {
    "build_plate_surface": "textured_pei",
    "bambu_bed_type": "Textured PEI Plate",
}
PRINTER = {
    "id": "local.printer.bambu_a1_0_4",
    "kind": "printer",
    "name": "Bambu Lab A1",
    "payload": {
        "model": "A1",
        "max_nozzle_temperature_c": 300,
        "max_bed_temperature_c": 100,
    },
}


def _validate(
    filament: dict[str, object],
    *,
    plan: dict[str, object] | None = None,
    nozzle_material: str = "hardened_steel",
    diameter: float = .4,
    plate: dict[str, object] | None = None,
):
    return CONTRACT.validate_slicer_compatibility(
        _catalog(
            filament,
            nozzle_material=nozzle_material,
            diameter=diameter,
        ),
        NOZZLES.a1_nozzle_contract(diameter),
        plan or _plan(material=str(filament["payload"]["material"])),
        plate or PLATE,
        PRINTER,
    )


def test_valid_ams_contract_attaches_profile_and_is_hashed() -> None:
    resolved, report = _validate(_filament_profile())
    assert resolved["filaments"][0]["selected_profile"]["id"] == (
        "local.filament.generic_pla"
    )
    assert report["status"] == "compatible"
    assert report["material_source"] == "ams_slot"
    assert report["filaments"][0]["manual_target_confirmed"] is True
    assert len(report["contract_sha256"]) == 64


def test_regular_tpu_is_external_only_but_tpu_for_ams_is_allowed() -> None:
    tpu = _filament_profile(
        profile_id="local.filament.generic_tpu",
        name="Generic TPU",
        material="TPU",
        nozzle=[200, 250],
        bed=45,
        ams=True,
    )
    external = _plan(
        source="authoritative_external_spool_runtime",
        material="TPU",
        filament_id="GFU99",
    )
    _, report = _validate(tpu, plan=external)
    assert report["material_source"] == "external_spool"

    with pytest.raises(
        CONTRACT.CompatibilityContractError,
        match="nicht für die Materialquelle AMS",
    ):
        _validate(tpu, plan=_plan(material="TPU", filament_id="GFU99"))

    tpu_ams = _filament_profile(
        profile_id="local.filament.tpu_ams",
        name="Generic TPU for AMS",
        material="TPU",
        nozzle=[200, 250],
        bed=45,
        ams=True,
    )
    _, report = _validate(
        tpu_ams,
        plan=_plan(material="TPU", filament_id="GFU98"),
    )
    assert report["material_source"] == "ams_slot"


def test_ams_lite_profile_flag_is_enforced_for_all_a1_ams_channels() -> None:
    profile = _filament_profile(ams=False)
    with pytest.raises(
        CONTRACT.CompatibilityContractError,
        match="nicht für das AMS Lite",
    ):
        _validate(profile)


def test_abrasive_profile_requires_hardened_nozzle() -> None:
    profile = _filament_profile(
        name="Generic PLA-CF",
        material="PLA-CF",
        nozzle=[210, 250],
        hardened=True,
    )
    with pytest.raises(CONTRACT.CompatibilityContractError, match="gehärtete Düse"):
        _validate(
            profile,
            nozzle_material="stainless_steel",
            plan=_plan(material="PLA-CF", filament_id="GFL98"),
        )
    _, report = _validate(
        profile,
        plan=_plan(material="PLA-CF", filament_id="GFL98"),
    )
    assert report["filaments"][0]["hardened_nozzle_required"] is True


def test_open_frame_and_temperature_limits_fail_closed() -> None:
    required = _filament_profile(
        name="Generic ABS",
        material="ABS",
        nozzle=[240, 280],
        bed=95,
        enclosure="required",
    )
    with pytest.raises(CONTRACT.CompatibilityContractError, match="Open-Frame"):
        _validate(
            required,
            plan=_plan(material="ABS", filament_id="GFB99"),
        )

    too_hot = _filament_profile(nozzle=[290, 310])
    with pytest.raises(
        CONTRACT.CompatibilityContractError,
        match="maximale A1-Düsentemperatur",
    ):
        _validate(too_hot)


def test_explicit_plate_and_nozzle_restrictions_are_enforced() -> None:
    profile = _filament_profile()
    profile["payload"]["compatible_build_plate_surfaces"] = ["smooth_pei"]
    with pytest.raises(CONTRACT.CompatibilityContractError, match="Druckplatte"):
        _validate(profile)

    profile = _filament_profile()
    profile["payload"]["minimum_nozzle_diameter_mm"] = .6
    with pytest.raises(CONTRACT.CompatibilityContractError, match="zu klein"):
        _validate(profile, diameter=.4)


def test_unmaterializable_profile_and_unresolved_source_are_rejected() -> None:
    profile = _filament_profile()
    profile["payload"]["slicing_supported"] = False
    with pytest.raises(
        CONTRACT.CompatibilityContractError,
        match="kein vollständig materialisierbares",
    ):
        _validate(profile)

    with pytest.raises(CONTRACT.CompatibilityContractError, match="nicht aufgelöst"):
        _validate(profile, plan=_plan(source="ams"))


def test_view_runs_preflight_before_native_job_submission() -> None:
    source = (COMPONENT / "slicer_plate_views_v2.py").read_text(
        encoding="utf-8-sig"
    )
    assert "validate_slicer_compatibility(" in source
    assert source.index("validate_slicer_compatibility(") < source.index(
        "async_create_plate_job("
    )
    assert 'job["compatibility_contract"] = compatibility_contract' in source


def test_cloud_a1_machine_uses_only_exact_local_temperature_authority() -> None:
    cloud = {
        "id": "cloud.printer.a1",
        "kind": "printer",
        "name": "Bambu Lab A1 0.4 nozzle",
        "source": "bambu_cloud",
        "payload": {"model": "A1", "custom_machine_setting": "preserved"},
    }
    nozzle = {
        "id": "local.nozzle.a1_0_4_hardened",
        "kind": "nozzle",
        "name": "A1 0.4 hardened",
        "source": "local",
        "payload": {"diameter_mm": 0.4, "material": "hardened_steel"},
    }
    authority = {
        "id": "local.printer.bambu_a1_0_4",
        "kind": "printer",
        "name": "Bambu Lab A1 · 0,4 mm",
        "source": "local",
        "payload": {
            "model": "A1",
            "nozzle_diameter_mm": 0.4,
            "max_nozzle_temperature_c": 300,
            "max_bed_temperature_c": 100,
        },
    }
    catalog = {
        "selection": {"nozzle_profile_id": nozzle["id"]},
        "profiles": [cloud, nozzle, authority],
    }
    resolved = CONTRACT.printer_profile_with_validated_limits(catalog, cloud)
    assert resolved["payload"]["max_nozzle_temperature_c"] == 300
    assert resolved["payload"]["max_bed_temperature_c"] == 100
    assert resolved["payload"]["temperature_limits_source_profile_id"] == authority["id"]
    assert resolved["payload"]["custom_machine_setting"] == "preserved"
    assert "max_nozzle_temperature_c" not in cloud["payload"]


def test_cloud_a1_machine_limit_resolution_fails_closed_without_exact_nozzle_match() -> None:
    cloud = {
        "id": "cloud.printer.a1",
        "kind": "printer",
        "name": "Bambu Lab A1",
        "source": "bambu_cloud",
        "payload": {"model": "A1"},
    }
    nozzle = {
        "id": "nozzle.0.6",
        "kind": "nozzle",
        "name": "A1 0.6",
        "source": "local",
        "payload": {"diameter_mm": 0.6},
    }
    catalog = {
        "selection": {"nozzle_profile_id": nozzle["id"]},
        "profiles": [cloud, nozzle],
    }
    with pytest.raises(
        CONTRACT.CompatibilityContractError,
        match="keine eindeutige validierte",
    ):
        CONTRACT.printer_profile_with_validated_limits(catalog, cloud)
