"""Exact selected-profile resolution for V6 slicer jobs.

This module never embeds printer-specific start G-code. Machine, process,
filament and build-plate templates always come from the profiles selected in
V6 and are rendered by the configured Bambu Studio CLI worker.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any


class ProfileResolutionError(ValueError):
    """Raised when the selected profile set cannot be resolved exactly."""


@dataclass(frozen=True, slots=True)
class ResolvedProfileSet:
    selection: dict[str, Any]
    printer: dict[str, Any]
    nozzle: dict[str, Any]
    process: dict[str, Any]
    build_plate: dict[str, Any]
    filaments: tuple[dict[str, Any], ...]


def _profile_by_id(
    catalog: dict[str, Any],
    profile_id: object,
) -> dict[str, Any] | None:
    wanted = str(profile_id or "")
    for item in catalog.get("profiles", []):
        if isinstance(item, dict) and str(item.get("id", "")) == wanted:
            return item
    return None


def resolve_selected_profiles(catalog: dict[str, Any]) -> ResolvedProfileSet:
    selection = catalog.get("selection")
    if not isinstance(selection, dict):
        raise ProfileResolutionError(
            "Der Profilkatalog enthält keine gültige Auswahl."
        )

    filament_ids = selection.get("filament_profile_ids", [])
    if not isinstance(filament_ids, list):
        raise ProfileResolutionError(
            "Die ausgewählten Filamentprofile sind ungültig."
        )

    printer = _profile_by_id(catalog, selection.get("printer_profile_id"))
    nozzle = _profile_by_id(catalog, selection.get("nozzle_profile_id"))
    process = _profile_by_id(catalog, selection.get("process_profile_id"))
    build_plate = _profile_by_id(
        catalog,
        selection.get("build_plate_profile_id"),
    )
    filaments = tuple(
        profile
        for profile_id in filament_ids
        if (profile := _profile_by_id(catalog, profile_id)) is not None
    )

    missing: list[str] = []
    if printer is None:
        missing.append("Druckerprofil")
    if nozzle is None:
        missing.append("Düsenprofil")
    if process is None:
        missing.append("Prozessprofil")
    if build_plate is None:
        missing.append("Druckplattenprofil")
    if not filaments:
        missing.append("Filamentprofil")
    if missing:
        raise ProfileResolutionError(
            "Ausgewählte Profile konnten nicht vollständig aufgelöst werden: "
            + ", ".join(missing)
        )

    resolved = ResolvedProfileSet(
        selection=deepcopy(selection),
        printer=deepcopy(printer),
        nozzle=deepcopy(nozzle),
        process=deepcopy(process),
        build_plate=deepcopy(build_plate),
        filaments=tuple(deepcopy(item) for item in filaments),
    )
    return resolved


def profile_payload(profile: dict[str, Any]) -> dict[str, Any]:
    payload = profile.get("payload", {})
    if not isinstance(payload, dict):
        raise ProfileResolutionError(
            f"Profil '{profile.get('name', '')}' enthält keine gültige Profilvorlage."
        )
    return deepcopy(payload)


def build_plate_reference(profile: dict[str, Any]) -> str:
    payload = profile_payload(profile)
    surface = str(payload.get("surface", "")).casefold()
    references = {
        "textured_pei": "Textured PEI Plate",
        "smooth_pei": "Smooth PEI Plate / High Temp Plate",
        "cool_plate_super_tack": "Cool Plate SuperTack",
        "cool_plate": "Cool Plate",
        "engineering_plate": "Engineering Plate",
    }
    reference = references.get(surface)
    if reference:
        return reference
    name = str(profile.get("name", "")).strip()
    if not name:
        raise ProfileResolutionError(
            "Das Druckplattenprofil hat keinen auflösbaren Namen."
        )
    return name


def profile_descriptor(
    profile: dict[str, Any],
    *,
    role: str,
    system_reference: str | None,
    override_file: str | None,
) -> dict[str, Any]:
    payload = profile_payload(profile)
    payload_digest = sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "role": role,
        "profile_id": str(profile.get("id", "")),
        "name": str(profile.get("name", "")),
        "source": str(profile.get("source", "")),
        "cloud_id": str(profile.get("cloud_id", "")),
        "base_id": profile.get("base_id"),
        "version": profile.get("version"),
        "system_reference": system_reference,
        "override_file": override_file,
        "payload_sha256": payload_digest,
    }


def build_profile_manifest(
    resolved: ResolvedProfileSet,
    descriptors: list[dict[str, Any]],
) -> dict[str, Any]:
    # Local import keeps the profile data model independent while ensuring that
    # every worker package receives the exact G-code/template dependency contract.
    from .gcode_template_contract import build_gcode_template_contract

    template_contract = build_gcode_template_contract(resolved)
    manifest: dict[str, Any] = {
        "schema_version": 3,
        "resolution_policy": "exact_selected_profiles_only",
        "allow_profile_fallback": False,
        "require_machine_start_gcode": True,
        "require_machine_end_gcode": True,
        "require_rendered_template_validation": True,
        "selection": deepcopy(resolved.selection),
        "profiles": deepcopy(descriptors),
        "gcode_template_contract": template_contract,
        "gcode_template_contract_sha256": template_contract[
            "contract_sha256"
        ],
    }
    digest_source = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    manifest["manifest_sha256"] = sha256(digest_source).hexdigest()
    return manifest
