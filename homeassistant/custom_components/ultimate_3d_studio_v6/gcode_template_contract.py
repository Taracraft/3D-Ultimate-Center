"""Exact dependency and G-code-template contract for V6 slicing.

The contract never renders or rewrites G-code. It records the exact selected
profile payloads, validates explicit compatibility constraints and fingerprints
all native Bambu G-code template fields before the archive reaches the worker.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Iterable

from .profile_resolution import (
    ProfileResolutionError,
    ResolvedProfileSet,
    profile_payload,
)


_MACHINE_START_KEYS = (
    "machine_start_gcode",
    "start_gcode",
)
_MACHINE_END_KEYS = (
    "machine_end_gcode",
    "end_gcode",
)
_TEMPLATE_KEYS: dict[str, tuple[str, ...]] = {
    "machine": (
        "machine_start_gcode",
        "machine_end_gcode",
        "before_layer_change_gcode",
        "layer_change_gcode",
        "change_filament_gcode",
        "machine_pause_gcode",
        "template_custom_gcode",
        "start_gcode",
        "end_gcode",
    ),
    "process": (
        "before_layer_change_gcode",
        "layer_change_gcode",
        "change_filament_gcode",
        "template_custom_gcode",
    ),
    "build_plate": (
        "start_gcode",
        "end_gcode",
        "plate_start_gcode",
        "plate_end_gcode",
    ),
    "filament": (
        "filament_start_gcode",
        "filament_end_gcode",
        "start_gcode",
        "end_gcode",
    ),
}


class GCodeTemplateContractError(ProfileResolutionError):
    """Raised when the selected profile combination is not deterministic."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_canonical(value)).hexdigest()


def _sequence(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            result.extend(_sequence(item))
        return tuple(result)
    return (str(value).strip(),) if str(value).strip() else ()


def _template_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(str(item) for item in value)
    return ""


def _template_fingerprints(
    payload: dict[str, Any],
    role: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key in _TEMPLATE_KEYS.get(role, ()):
        if key not in payload:
            continue
        text = _template_text(payload.get(key))
        if not text.strip():
            continue
        result[key] = {
            "sha256": sha256(text.encode("utf-8")).hexdigest(),
            "bytes": len(text.encode("utf-8")),
            "lines": len(text.splitlines()),
        }
    return result


def _identity(profile: dict[str, Any]) -> set[str]:
    payload = profile_payload(profile)
    values: set[str] = set()
    for value in (
        profile.get("id"),
        profile.get("name"),
        payload.get("model"),
        payload.get("printer_model"),
        payload.get("machine_model"),
        payload.get("vendor"),
    ):
        for item in _sequence(value):
            values.add(item.casefold())
    return values


def _explicit_constraint(
    payload: dict[str, Any],
    keys: Iterable[str],
) -> tuple[str, ...]:
    for key in keys:
        if key not in payload:
            continue
        values = _sequence(payload.get(key))
        if values:
            return values
    return ()


def _ensure_printer_compatibility(
    profile: dict[str, Any],
    printer_identity: set[str],
    role: str,
) -> None:
    payload = profile_payload(profile)
    allowed = _explicit_constraint(
        payload,
        (
            "compatible_printers",
            "compatible_printer_ids",
            "compatible_printer_models",
            "compatible_machines",
            "compatible_machine_models",
        ),
    )
    if not allowed:
        return
    normalized = {item.casefold() for item in allowed}
    if normalized.isdisjoint(printer_identity):
        raise GCodeTemplateContractError(
            f"Das ausgewählte {role}-Profil '{profile.get('name', '')}' ist "
            "nicht für das gewählte Druckerprofil freigegeben."
        )


def _decimal(value: Any) -> float | None:
    try:
        parsed = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _ensure_nozzle_compatibility(
    profile: dict[str, Any],
    selected_diameter: float,
    role: str,
) -> None:
    payload = profile_payload(profile)
    values = _explicit_constraint(
        payload,
        (
            "compatible_nozzle_diameters",
            "compatible_nozzle_diameter_mm",
            "supported_nozzle_diameters",
        ),
    )
    if not values:
        return
    diameters = {
        parsed
        for value in values
        if (parsed := _decimal(value)) is not None
    }
    if diameters and not any(
        abs(selected_diameter - diameter) < 0.0001
        for diameter in diameters
    ):
        raise GCodeTemplateContractError(
            f"Das ausgewählte {role}-Profil '{profile.get('name', '')}' unterstützt "
            f"die Düse {selected_diameter:g} mm nicht."
        )


def _ensure_plate_compatibility(
    profile: dict[str, Any],
    plate_values: set[str],
    role: str,
) -> None:
    payload = profile_payload(profile)
    allowed = _explicit_constraint(
        payload,
        (
            "compatible_build_plates",
            "compatible_plate_types",
            "supported_build_plates",
        ),
    )
    if not allowed:
        return
    normalized = {item.casefold() for item in allowed}
    if normalized.isdisjoint(plate_values):
        raise GCodeTemplateContractError(
            f"Das ausgewählte {role}-Profil '{profile.get('name', '')}' ist "
            "nicht für die gewählte Druckplatte freigegeben."
        )


def _machine_template_mode(profile: dict[str, Any]) -> str:
    if str(profile.get("source", "")) == "builtin":
        return "bambu_system_reference"
    payload = profile_payload(profile)
    start = any(_template_text(payload.get(key)).strip() for key in _MACHINE_START_KEYS)
    end = any(_template_text(payload.get(key)).strip() for key in _MACHINE_END_KEYS)
    if start and end:
        return "exact_profile_templates"
    inheritance = _explicit_constraint(
        payload,
        ("inherits", "inherit", "base_profile", "base_machine_profile"),
    )
    if inheritance or profile.get("base_id"):
        return "exact_profile_inheritance"
    raise GCodeTemplateContractError(
        f"Das Maschinenprofil '{profile.get('name', '')}' enthält weder "
        "vollständigen Start-/End-GCode noch eine eindeutige Bambu-Vererbung."
    )


def build_gcode_template_contract(
    resolved: ResolvedProfileSet,
) -> dict[str, Any]:
    """Build and validate the immutable selected-profile dependency contract."""
    printer_payload = profile_payload(resolved.printer)
    nozzle_payload = profile_payload(resolved.nozzle)
    process_payload = profile_payload(resolved.process)
    plate_payload = profile_payload(resolved.build_plate)
    filament_payloads = [profile_payload(item) for item in resolved.filaments]

    diameter = _decimal(nozzle_payload.get("diameter_mm"))
    if diameter is None:
        raise GCodeTemplateContractError(
            "Das ausgewählte Düsenprofil enthält keinen gültigen Durchmesser."
        )

    printer_identity = _identity(resolved.printer)
    plate_values = {
        value.casefold()
        for value in _sequence(resolved.build_plate.get("id"))
        + _sequence(resolved.build_plate.get("name"))
        + _sequence(plate_payload.get("surface"))
        + _sequence(plate_payload.get("bed_type"))
    }

    _ensure_printer_compatibility(resolved.process, printer_identity, "Prozess")
    _ensure_printer_compatibility(resolved.build_plate, printer_identity, "Druckplatten")
    _ensure_nozzle_compatibility(resolved.process, diameter, "Prozess")
    _ensure_nozzle_compatibility(resolved.build_plate, diameter, "Druckplatten")

    for filament in resolved.filaments:
        _ensure_printer_compatibility(filament, printer_identity, "Filament")
        _ensure_nozzle_compatibility(filament, diameter, "Filament")
        _ensure_plate_compatibility(filament, plate_values, "Filament")

    profiles = {
        "machine": {
            "profile_id": str(resolved.printer.get("id", "")),
            "payload_sha256": _digest(printer_payload),
            "template_mode": _machine_template_mode(resolved.printer),
            "templates": _template_fingerprints(printer_payload, "machine"),
        },
        "nozzle": {
            "profile_id": str(resolved.nozzle.get("id", "")),
            "payload_sha256": _digest(nozzle_payload),
            "diameter_mm": diameter,
            "material": str(nozzle_payload.get("material", "")),
        },
        "process": {
            "profile_id": str(resolved.process.get("id", "")),
            "payload_sha256": _digest(process_payload),
            "templates": _template_fingerprints(process_payload, "process"),
        },
        "build_plate": {
            "profile_id": str(resolved.build_plate.get("id", "")),
            "payload_sha256": _digest(plate_payload),
            "surface": str(
                plate_payload.get("surface")
                or plate_payload.get("bed_type")
                or resolved.build_plate.get("name", "")
            ),
            "templates": _template_fingerprints(plate_payload, "build_plate"),
        },
        "filaments": [
            {
                "profile_id": str(profile.get("id", "")),
                "payload_sha256": _digest(payload),
                "material": str(payload.get("material", "")),
                "vendor": str(payload.get("vendor", "")),
                "templates": _template_fingerprints(payload, "filament"),
            }
            for profile, payload in zip(resolved.filaments, filament_payloads)
        ],
    }

    contract: dict[str, Any] = {
        "schema_version": 1,
        "policy": "exact_selected_profile_templates",
        "gcode_rendering": "bambu_studio_cli_only",
        "template_rewrite_allowed": False,
        "profile_fallback_allowed": False,
        "dependencies": {
            "printer_profile_id": str(resolved.printer.get("id", "")),
            "nozzle_profile_id": str(resolved.nozzle.get("id", "")),
            "process_profile_id": str(resolved.process.get("id", "")),
            "build_plate_profile_id": str(resolved.build_plate.get("id", "")),
            "filament_profile_ids": [
                str(item.get("id", ""))
                for item in resolved.filaments
            ],
        },
        "profiles": profiles,
    }
    contract["contract_sha256"] = _digest(contract)
    return contract