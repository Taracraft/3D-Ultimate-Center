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
PACKAGE_NAME = "ultimate_3d_studio_v6"
MODULE_NAME = f"{PACKAGE_NAME}.filament_profile_mapping"

package = sys.modules.setdefault(PACKAGE_NAME, types.ModuleType(PACKAGE_NAME))
package.__path__ = [str(COMPONENT)]
spec = importlib.util.spec_from_file_location(
    MODULE_NAME,
    COMPONENT / "filament_profile_mapping.py",
    submodule_search_locations=[str(COMPONENT)],
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def profile(profile_id: str, name: str, material: str) -> dict[str, object]:
    return {
        "id": profile_id,
        "kind": "filament",
        "name": name,
        "source": "local",
        "payload": {"material": material, "vendor": "eSUN"},
    }


def catalog(selected: list[str], *profiles: dict[str, object]) -> dict[str, object]:
    return {
        "selection": {"filament_profile_ids": selected},
        "profiles": list(profiles),
    }


def filament(slot: int, material: str, color: str) -> dict[str, object]:
    return {
        "extruder": slot + 1,
        "slot_index": slot,
        "display_slot": slot + 1,
        "material": material,
        "color": color,
        "name": f"AMS {slot + 1}: {material}",
    }


def test_single_pla_profile_is_reused_for_two_pla_colors() -> None:
    esun = profile("esun-pla-plus", "eSUN PLA+ @BBL A1 PLA HS", "PLA")
    filaments = [filament(0, "PLA", "#F62021"), filament(1, "PLA", "#000000")]

    result = module.attach_selected_profiles(catalog(["esun-pla-plus"], esun), filaments)

    assert [item["selected_profile"]["id"] for item in result] == [
        "esun-pla-plus",
        "esun-pla-plus",
    ]


def test_profile_order_is_authoritative_when_counts_match() -> None:
    red = profile("red-profile", "Red PLA Profile", "PLA")
    black = profile("black-profile", "Black PLA Profile", "PLA")
    filaments = [filament(0, "PLA", "#F62021"), filament(1, "PLA", "#000000")]

    result = module.attach_selected_profiles(
        catalog(["red-profile", "black-profile"], red, black),
        filaments,
    )

    assert [item["selected_profile"]["id"] for item in result] == [
        "red-profile",
        "black-profile",
    ]


def test_positional_material_conflict_is_rejected() -> None:
    pla = profile("pla-profile", "PLA Profile", "PLA")
    petg = profile("petg-profile", "PETG Profile", "PETG")
    filaments = [filament(0, "PETG", "#111111"), filament(1, "PLA", "#222222")]

    with pytest.raises(ValueError, match="passt nicht zum Material"):
        module.attach_selected_profiles(
            catalog(["pla-profile", "petg-profile"], pla, petg),
            filaments,
        )

def test_single_stale_abs_selection_falls_back_to_matching_active_pla_profile() -> None:
    stale_abs = profile("esun-abs", "eSUN ABS @BBL A1", "ABS")
    active_pla = profile("esun-pla-plus", "eSUN PLA+ @BBL A1 PLA HS", "PLA")
    filaments = [filament(0, "PLA", "#101010")]
    filaments[0]["name"] = "AMS 1: eSUN PLA+ Schwarz"
    filaments[0]["filament_id"] = "GFL99"

    result = module.attach_selected_profiles(
        catalog(["esun-abs"], stale_abs, active_pla),
        filaments,
    )

    assert result[0]["selected_profile"]["id"] == "esun-pla-plus"
    assert result[0]["selected_profile"]["name"] == "eSUN PLA+ @BBL A1 PLA HS"


def test_single_stale_abs_selection_still_fails_when_no_matching_active_profile_exists() -> None:
    stale_abs = profile("esun-abs", "eSUN ABS @BBL A1", "ABS")
    petg = profile("esun-petg", "eSUN PETG @BBL A1", "PETG")
    filaments = [filament(0, "PLA", "#101010")]
    filaments[0]["name"] = "AMS 1: eSUN PLA+ Schwarz"

    with pytest.raises(ValueError, match="passt nicht zum Material"):
        module.attach_selected_profiles(
            catalog(["esun-abs"], stale_abs, petg),
            filaments,
        )



def test_live_abs_plus_pla_selection_uses_only_the_active_pla_channel() -> None:
    stale_abs = profile(
        "local.filament.esun_abs",
        "eSUN ABS",
        "ABS",
    )
    active_pla = profile(
        "cloud.filament.pfus907bcf946d6bd6",
        "eSUN PLA+ @BBL A1 PLA HS",
        "",
    )
    active_pla["source"] = "bambu_cloud"
    filaments = [filament(0, "PLA", "#101010")]
    filaments[0]["name"] = "AMS 1: eSUN PLA+ Schwarz"
    filaments[0]["filament_id"] = "GFL99"

    result = module.attach_selected_profiles(
        catalog(
            [
                "local.filament.esun_abs",
                "cloud.filament.pfus907bcf946d6bd6",
            ],
            stale_abs,
            active_pla,
        ),
        filaments,
    )

    assert result[0]["selected_profile"]["id"] == "cloud.filament.pfus907bcf946d6bd6"
    assert result[0]["selected_profile"]["source"] == "bambu_cloud"


def test_unused_extra_profile_is_ignored_after_all_used_materials_resolve() -> None:
    pla = profile("pla-profile", "PLA Profile", "PLA")
    petg = profile("petg-profile", "PETG Profile", "PETG")
    unused_abs = profile("unused-abs", "Unused ABS Profile", "ABS")
    filaments = [filament(0, "PLA", "#111111"), filament(1, "PETG", "#222222")]

    result = module.attach_selected_profiles(
        catalog(
            ["unused-abs", "pla-profile", "petg-profile"],
            unused_abs,
            pla,
            petg,
        ),
        filaments,
    )

    assert [item["selected_profile"]["id"] for item in result] == [
        "pla-profile",
        "petg-profile",
    ]


@pytest.mark.parametrize("case_index", range(100))
def test_unused_stale_profile_matrix_never_blocks_the_used_material(
    case_index: int,
) -> None:
    materials = ("PLA", "PETG", "ABS", "ASA", "TPU", "PA", "PC")
    active_material = materials[case_index % len(materials)]
    stale_count = 1 + (case_index % 4)
    stale_materials = [
        materials[(case_index + offset + 1) % len(materials)]
        for offset in range(stale_count)
    ]
    stale_materials = [
        material if material != active_material else materials[(materials.index(material) + 1) % len(materials)]
        for material in stale_materials
    ]
    matching = profile(
        f"active-{case_index}",
        f"Active {active_material} Profile {case_index}",
        active_material,
    )
    stale_profiles = [
        profile(
            f"stale-{case_index}-{offset}",
            f"Unused {material} Profile {case_index}-{offset}",
            material,
        )
        for offset, material in enumerate(stale_materials)
    ]
    insertion = case_index % (len(stale_profiles) + 1)
    selected_profiles = [
        *stale_profiles[:insertion],
        matching,
        *stale_profiles[insertion:],
    ]
    channel = filament(
        case_index % 4,
        active_material,
        f"#{case_index:06x}"[-7:],
    )

    result = module.attach_selected_profiles(
        catalog(
            [str(item["id"]) for item in selected_profiles],
            matching,
            *stale_profiles,
        ),
        [channel],
    )

    assert result[0]["selected_profile"]["id"] == f"active-{case_index}"
    assert result[0]["material"] == active_material


def test_unused_stale_profile_does_not_make_two_active_profiles_unambiguous() -> None:
    stale_abs = profile("stale-abs", "Unused ABS Profile", "ABS")
    pla_fast = profile("pla-fast", "PLA Fast Profile", "PLA")
    pla_quality = profile("pla-quality", "PLA Quality Profile", "PLA")

    with pytest.raises(ValueError):
        module.attach_selected_profiles(
            catalog(
                ["stale-abs", "pla-fast", "pla-quality"],
                stale_abs,
                pla_fast,
                pla_quality,
            ),
            [filament(0, "PLA", "#101010")],
        )
