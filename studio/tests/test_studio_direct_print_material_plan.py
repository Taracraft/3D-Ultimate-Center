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
PACKAGE_NAME = "ultimate_3d_studio"
MODULE_NAME = f"{PACKAGE_NAME}.direct_print_material_plan"

package = sys.modules.setdefault(PACKAGE_NAME, types.ModuleType(PACKAGE_NAME))
package.__path__ = [str(COMPONENT)]
spec = importlib.util.spec_from_file_location(
    MODULE_NAME,
    COMPONENT / "direct_print_material_plan.py",
    submodule_search_locations=[str(COMPONENT)],
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def slots(*indices: int):
    return [
        {"slot_index": index, "present": True}
        for index in indices
    ]


def job(*filaments: dict[str, object], printer_id: str = "SERIAL"):
    return {
        "ams_material_plan": {
            "source": "authoritative_ams_runtime",
            "target_printer_id": printer_id,
            "filaments": list(filaments),
        },
        "target_printer": {"printer_id": printer_id},
    }


def test_single_color_slot_two_maps_to_index_one() -> None:
    result = module.derive_authoritative_ams_start(
        job({
            "extruder": 1,
            "slot_index": 1,
            "display_slot": 2,
            "name": "AMS 2: PLA",
        }),
        printer_id="SERIAL",
        printer_slots=slots(0, 1, 2),
    )
    assert result.mapping == (1,)
    assert result.as_dict()["use_ams"] is True
    assert result.as_dict()["ams_mapping"] == [1]


def test_two_color_mapping_preserves_extruder_order() -> None:
    result = module.derive_authoritative_ams_start(
        job(
            {"extruder": 2, "slot_index": 1, "display_slot": 2, "name": "Schwarz"},
            {"extruder": 1, "slot_index": 0, "display_slot": 1, "name": "Rot"},
        ),
        printer_id="SERIAL",
        printer_slots=slots(0, 1, 2),
    )
    assert result.mapping == (0, 1)


def test_missing_authoritative_source_is_rejected() -> None:
    payload = job({"extruder": 1, "slot_index": 0})
    payload["ams_material_plan"]["source"] = "model"
    with pytest.raises(module.DirectPrintMaterialPlanError, match="autoritativen"):
        module.derive_authoritative_ams_start(
            payload,
            printer_id="SERIAL",
            printer_slots=slots(0),
        )


def test_other_printer_is_rejected() -> None:
    with pytest.raises(module.DirectPrintMaterialPlanError, match="anderen Drucker"):
        module.derive_authoritative_ams_start(
            job({"extruder": 1, "slot_index": 0}, printer_id="OTHER"),
            printer_id="SERIAL",
            printer_slots=slots(0),
        )


def test_empty_or_unavailable_slot_is_rejected() -> None:
    with pytest.raises(module.DirectPrintMaterialPlanError, match="leer oder nicht verfügbar"):
        module.derive_authoritative_ams_start(
            job({"extruder": 1, "slot_index": 2}),
            printer_id="SERIAL",
            printer_slots=slots(0, 1),
        )


def external_job(*filaments: dict[str, object], printer_id: str = "SERIAL"):
    return {
        "material_source_plan": {
            "source": "authoritative_external_spool_runtime",
            "target_printer_id": printer_id,
            "filaments": list(filaments),
        },
        "target_printer": {"printer_id": printer_id},
    }


def test_external_spool_is_explicit_and_has_no_ams_mapping() -> None:
    result = module.derive_authoritative_ams_start(
        external_job({
            "extruder": 1,
            "name": "Bambu PETG HF",
            "source": "external_spool",
        }),
        printer_id="SERIAL",
        printer_slots=[],
    )
    assert result.use_ams is False
    assert result.mapping == ()
    assert result.labels == ("Externe Spule: Bambu PETG HF",)
    assert result.as_dict()["use_ams"] is False
    assert result.as_dict()["ams_mapping"] == []


def test_external_spool_rejects_multiple_material_channels() -> None:
    with pytest.raises(module.DirectPrintMaterialPlanError, match="genau einen Materialkanal"):
        module.derive_authoritative_ams_start(
            external_job(
                {"extruder": 1, "source": "external_spool"},
                {"extruder": 2, "source": "external_spool"},
            ),
            printer_id="SERIAL",
            printer_slots=slots(0, 1),
        )


def test_external_spool_rejects_source_mismatch() -> None:
    with pytest.raises(module.DirectPrintMaterialPlanError, match="ungültig"):
        module.derive_authoritative_ams_start(
            external_job({"extruder": 1, "source": "ams"}),
            printer_id="SERIAL",
            printer_slots=[],
        )
