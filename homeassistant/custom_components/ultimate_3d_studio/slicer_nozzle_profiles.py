"""Validated Bambu Lab A1 nozzle and native process contracts.

The values mirror the fully resolved profiles installed on the native
Home-Assistant slicing VM. The native worker verifies the referenced files
again before every slice and never accepts an arbitrary profile path.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any
try:
    from .printer_model_contract import canonical_model, h2s_defaults
except ImportError:
    import importlib.util as _model_import
    from pathlib import Path as _ModelPath
    _spec = _model_import.spec_from_file_location("studio_printer_model_authority", _ModelPath(__file__).with_name("printer_model_contract.py"))
    _authority = _model_import.module_from_spec(_spec)
    _spec.loader.exec_module(_authority)
    canonical_model = _authority.canonical_model
    h2s_defaults = _authority.h2s_defaults


class NozzleProfileError(ValueError):
    """Raised when a selected nozzle/process combination is not validated."""


@dataclass(frozen=True, slots=True)
class A1NozzleContract:
    diameter_mm: float
    machine_profile: str
    process_profile: str
    min_layer_height_mm: float
    max_layer_height_mm: float
    default_layer_height_mm: float
    default_outer_wall_speed_mm_s: float
    default_inner_wall_speed_mm_s: float
    max_wall_speed_mm_s: float = 500.0
    printer_model: str = "A1"
    max_build_height_mm: float = 256.0


A1_NOZZLE_CONTRACTS: tuple[A1NozzleContract, ...] = (
    A1NozzleContract(
        .2,
        "BBL/machine/Bambu Lab A1 0.2 nozzle.json",
        "BBL/process/0.10mm Standard @BBL A1 0.2 nozzle.json",
        .04,
        .14,
        .1,
        120,
        150,
    ),
    A1NozzleContract(
        .4,
        "BBL/machine/Bambu Lab A1 0.4 nozzle.json",
        "BBL/process/0.20mm Standard @BBL A1.json",
        .08,
        .28,
        .2,
        200,
        300,
    ),
    A1NozzleContract(
        .6,
        "BBL/machine/Bambu Lab A1 0.6 nozzle.json",
        "BBL/process/0.30mm Strength @BBL A1 0.6 nozzle.json",
        .12,
        .42,
        .3,
        120,
        150,
    ),
    A1NozzleContract(
        .8,
        "BBL/machine/Bambu Lab A1 0.8 nozzle.json",
        "BBL/process/0.40mm Standard @BBL A1 0.8 nozzle.json",
        .16,
        .56,
        .4,
        120,
        150,
    ),
)

MAX_LAYER_HEIGHT_RANGE_COUNT = 32
MAX_LAYER_HEIGHT_RANGE_Z_MM = 256.0


def _number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise NozzleProfileError(f"{label} ist ungültig.")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise NozzleProfileError(f"{label} ist ungültig.") from exc
    if not math.isfinite(parsed):
        raise NozzleProfileError(f"{label} ist ungültig.")
    return parsed


def a1_nozzle_contract(diameter_mm: object) -> A1NozzleContract:
    diameter = _number(diameter_mm, "Der Düsendurchmesser")
    for contract in A1_NOZZLE_CONTRACTS:
        if math.isclose(contract.diameter_mm, diameter, abs_tol=1e-6):
            return contract
    raise NozzleProfileError(
        "Für den gewählten Düsendurchmesser ist kein validiertes "
        "Bambu-Lab-A1-Profil installiert."
    )


def _selected_profile(
    catalog: dict[str, Any],
    selection_key: str,
    expected_kind: str,
) -> dict[str, Any]:
    selection = catalog.get("selection")
    if not isinstance(selection, dict):
        raise NozzleProfileError("Der Profilkatalog enthält keine gültige Auswahl.")
    profile_id = str(selection.get(selection_key) or "")
    profiles = catalog.get("profiles")
    if not isinstance(profiles, list):
        raise NozzleProfileError("Der Profilkatalog ist ungültig.")
    profile = next(
        (
            item
            for item in profiles
            if isinstance(item, dict)
            and str(item.get("id") or "") == profile_id
            and str(item.get("kind") or "") == expected_kind
        ),
        None,
    )
    if profile is None:
        raise NozzleProfileError(
            f"Das ausgewählte {expected_kind}-Profil ist nicht verfügbar."
        )
    return profile


def resolve_a1_nozzle_contract(
    catalog: dict[str, Any],
    target_printer: dict[str, Any] | None,
) -> A1NozzleContract:
    target = target_printer or {}
    target_model = str(target.get("model") or target.get("name") or "")
    normalized_model = "".join(ch for ch in target_model.casefold() if ch.isalnum())
    if "a1mini" in normalized_model or "a1m" in normalized_model or "a1" not in normalized_model:
        raise NozzleProfileError(
            "Die Düsenprofile 0,2–0,8 mm sind ausschließlich für den "
            "validierten Bambu Lab A1 vorgesehen."
        )

    nozzle = _selected_profile(catalog, "nozzle_profile_id", "nozzle")
    payload = nozzle.get("payload")
    if not isinstance(payload, dict):
        raise NozzleProfileError("Das gewählte Düsenprofil ist ungültig.")
    printer_name = str(payload.get("printer") or "").strip().casefold()
    if printer_name and "bambu lab a1" not in printer_name:
        raise NozzleProfileError("Das gewählte Düsenprofil passt nicht zum Bambu Lab A1.")
    contract = a1_nozzle_contract(payload.get("diameter_mm"))

    printer = _selected_profile(catalog, "printer_profile_id", "printer")
    printer_payload = printer.get("payload")
    if isinstance(printer_payload, dict) and printer_payload.get("nozzle_diameter_mm") is not None:
        profile_diameter = _number(
            printer_payload.get("nozzle_diameter_mm"),
            "Der Düsendurchmesser des Druckerprofils",
        )
        if not math.isclose(profile_diameter, contract.diameter_mm, abs_tol=1e-6):
            raise NozzleProfileError(
                "Druckerprofil und Düsenprofil haben unterschiedliche "
                "Düsendurchmesser."
            )
    return contract


def validate_process_overrides(
    overrides: dict[str, Any] | None,
    contract: A1NozzleContract,
) -> dict[str, Any]:
    result = dict(overrides or {})
    support_mode = str(result.get("support_mode") or "off").strip().casefold()
    if support_mode not in {"off", "normal", "tree"}:
        raise NozzleProfileError("Der Support-Modus ist ungültig.")
    result["support_mode"] = support_mode
    support_style = str(result.get("support_style") or "standard").strip().casefold()
    if support_style not in {"standard", "tree_slim", "tree_strong", "tree_hybrid", "tree_organic"}:
        raise NozzleProfileError("Der Support-Stil ist ungültig.")
    result["support_style"] = support_style
    plate_only = result.get("support_build_plate_only", True)
    if isinstance(plate_only, str):
        normalized_plate_only = plate_only.strip().casefold()
        if normalized_plate_only not in {"true", "false"}:
            raise NozzleProfileError("Die Option 'Support nur vom Druckbett' ist ungültig.")
        result["support_build_plate_only"] = normalized_plate_only == "true"
    else:
        result["support_build_plate_only"] = plate_only is not False
    support_angle = result.get("support_threshold_angle")
    if support_angle is not None:
        angle_value = _number(support_angle, "Der Support-Schwellenwinkel")
        if not 0 <= angle_value <= 89:
            raise NozzleProfileError("Der Support-Schwellenwinkel muss zwischen 0 und 89 Grad liegen.")
        result["support_threshold_angle"] = int(round(angle_value))

    layer = result.get("layer_height_mm")
    if layer is not None:
        layer_value = _number(layer, "Die Schichthöhe")
        if not (
            contract.min_layer_height_mm
            <= layer_value
            <= contract.max_layer_height_mm
        ):
            raise NozzleProfileError(
                f"Die Schichthöhe für die {contract.diameter_mm:g}-mm-Düse "
                f"muss zwischen {contract.min_layer_height_mm:g} und "
                f"{contract.max_layer_height_mm:g} mm liegen."
            )
        result["layer_height_mm"] = layer_value

    for key, label in (
        ("outer_wall_speed_mm_s", "Die Außenwandgeschwindigkeit"),
        ("inner_wall_speed_mm_s", "Die Innenwandgeschwindigkeit"),
    ):
        value = result.get(key)
        if value is None:
            continue
        speed = _number(value, label)
        if not 1 <= speed <= contract.max_wall_speed_mm_s:
            raise NozzleProfileError(
                f"{label} muss zwischen 1 und "
                f"{contract.max_wall_speed_mm_s:g} mm/s liegen."
            )
        result[key] = speed

    ranges = result.get("layer_height_ranges")
    if ranges is not None:
        if not isinstance(ranges, list):
            raise NozzleProfileError("Variable Schichthöhen müssen eine Liste sein.")
        if len(ranges) > MAX_LAYER_HEIGHT_RANGE_COUNT:
            raise NozzleProfileError(
                f"Es sind höchstens {MAX_LAYER_HEIGHT_RANGE_COUNT} variable "
                "Schichthöhenbereiche erlaubt."
            )
        normalized: list[dict[str, float]] = []
        previous_max = 0.0
        for index, item in enumerate(ranges, start=1):
            if not isinstance(item, dict):
                raise NozzleProfileError(
                    f"Variabler Schichthöhenbereich {index} ist ungültig."
                )
            min_z = _number(
                item.get("min_z_mm", item.get("min_z")),
                f"Start-Z von Schichthöhenbereich {index}",
            )
            max_z = _number(
                item.get("max_z_mm", item.get("max_z")),
                f"End-Z von Schichthöhenbereich {index}",
            )
            height = _number(
                item.get("layer_height_mm", item.get("layer_height")),
                f"Schichthöhe von Bereich {index}",
            )
            if min_z < 0 or max_z <= min_z or max_z > contract.max_build_height_mm:
                raise NozzleProfileError(
                    f"Z-Bereich {index} muss innerhalb 0 bis "
                    f"{contract.max_build_height_mm:g} mm liegen und aufsteigend sein."
                )
            if min_z < previous_max:
                raise NozzleProfileError(
                    "Variable Schichthöhenbereiche dürfen sich nicht überlappen."
                )
            if not (
                contract.min_layer_height_mm
                <= height
                <= contract.max_layer_height_mm
            ):
                raise NozzleProfileError(
                    f"Die variable Schichthöhe in Bereich {index} muss für die "
                    f"{contract.diameter_mm:g}-mm-Düse zwischen "
                    f"{contract.min_layer_height_mm:g} und "
                    f"{contract.max_layer_height_mm:g} mm liegen."
                )
            normalized.append({
                "min_z_mm": min_z,
                "max_z_mm": max_z,
                "layer_height_mm": height,
            })
            previous_max = max_z
        result["layer_height_ranges"] = normalized
    return result


def contract_payload(contract: A1NozzleContract) -> dict[str, Any]:
    return {
        "nozzle_diameter_mm": contract.diameter_mm,
        "native_machine_profile": contract.machine_profile,
        "native_process_profile": contract.process_profile,
        "min_layer_height_mm": contract.min_layer_height_mm,
        "max_layer_height_mm": contract.max_layer_height_mm,
        "default_layer_height_mm": contract.default_layer_height_mm,
        "default_outer_wall_speed_mm_s": contract.default_outer_wall_speed_mm_s,
        "default_inner_wall_speed_mm_s": contract.default_inner_wall_speed_mm_s,
        "max_wall_speed_mm_s": contract.max_wall_speed_mm_s,
    }


H2S_NOZZLE_CONTRACTS = tuple(A1NozzleContract(
    float(diameter), machine["native_path"], h2s_defaults()["processes"][diameter]["native_path"],
    machine["min_layer"], machine["max_layer"], h2s_defaults()["processes"][diameter]["layer_height"],
    h2s_defaults()["processes"][diameter]["outer_wall_speed"],
    h2s_defaults()["processes"][diameter]["inner_wall_speed"], 500., "H2S", 340.)
    for diameter, machine in h2s_defaults()["machines"].items())


def resolve_nozzle_contract(catalog: dict, target_printer: dict | None) -> A1NozzleContract:
    target = target_printer or {}
    model = canonical_model(target.get("model") or target.get("name"))
    if model == "A1":
        return resolve_a1_nozzle_contract(catalog, target_printer)
    if model != "H2S":
        raise NozzleProfileError("Für diesen Drucker fehlt ein geprüfter Düsenvertrag.")
    nozzle = _selected_profile(catalog, "nozzle_profile_id", "nozzle")
    payload = nozzle.get("payload") or {}
    if canonical_model(payload.get("printer") or payload.get("printer_model")) != "H2S":
        raise NozzleProfileError("Das ausgewählte Düsenprofil passt nicht zum H2S.")
    diameter = _number(payload.get("diameter_mm"), "Düsendurchmesser")
    contract = next((c for c in H2S_NOZZLE_CONTRACTS if abs(c.diameter_mm - diameter) < 1e-6), None)
    if contract is None or payload.get("material") != "hardened_steel":
        raise NozzleProfileError("Für diese H2S-Düse fehlt ein geprüfter Hardwarevertrag.")
    printer = _selected_profile(catalog, "printer_profile_id", "printer")
    if canonical_model((printer.get("payload") or {}).get("model")) != "H2S":
        raise NozzleProfileError("Druckerprofil und H2S-Düse passen nicht zusammen.")
    return contract
