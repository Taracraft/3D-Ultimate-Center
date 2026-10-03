"""Central fail-closed compatibility preflight for Bambu Lab A1 slicing."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from typing import Any, Iterable

from .printer_model_contract import canonical_model, hardware_limits, h2s_defaults
from .a1_filament_catalog import A1_FILAMENT_CATALOG
from .filament_parameter_contract import preflight_filament_settings, check_filament_temperatures, validate_shared_bed_temperatures
from .slicer_execution_contract import digest, validate_plate_dimensions, validate_physical_a1_plate, a1_hardware_limits
from .filament_profile_mapping import attach_selected_profiles
from .slicer_nozzle_profiles import A1NozzleContract


CONTRACT_VERSION = "2"
_MANUAL_BY_ID = {
    str(item.get("id") or ""): item
    for item in A1_FILAMENT_CATALOG
    if isinstance(item, dict) and item.get("id")
}
_SUPPORTED_PLATE_TYPES = {
    "Textured PEI Plate",
    "High Temp Plate",
    "Cool Plate",
    "Engineering Plate",
    "Supertack Plate",
}


class CompatibilityContractError(ValueError):
    """Raised when a selected slice combination is not demonstrably safe."""


def _payload(profile: dict[str, Any]) -> dict[str, Any]:
    value = profile.get("payload")
    return value if isinstance(value, dict) else {}


def _selected_profile(
    catalog: dict[str, Any],
    selection_key: str,
    kind: str,
) -> dict[str, Any]:
    selection = catalog.get("selection")
    profiles = catalog.get("profiles")
    if not isinstance(selection, dict) or not isinstance(profiles, list):
        raise CompatibilityContractError("Der Profilkatalog ist unvollständig.")
    profile_id = str(selection.get(selection_key) or "")
    profile = next(
        (
            item for item in profiles
            if isinstance(item, dict)
            and item.get("kind") == kind
            and str(item.get("id") or "") == profile_id
        ),
        None,
    )
    if not isinstance(profile, dict):
        raise CompatibilityContractError(
            f"Das ausgewählte {kind}-Profil ist nicht verfügbar."
        )
    return profile


def _numbers(value: object) -> list[float]:
    values: Iterable[object]
    if isinstance(value, (list, tuple)):
        values = value
    else:
        values = (value,)
    result: list[float] = []
    for item in values:
        if item is None or item == "":
            continue
        try:
            number = float(item)
        except (TypeError, ValueError) as exc:
            raise CompatibilityContractError(
                "Ein Temperaturwert im Filamentprofil ist ungültig."
            ) from exc
        if not math.isfinite(number):
            raise CompatibilityContractError(
                "Ein Temperaturwert im Filamentprofil ist ungültig."
            )
        result.append(number)
    return result


def _temperature_values(
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> list[float]:
    result: list[float] = []
    for key in keys:
        if key in payload:
            result.extend(_numbers(payload.get(key)))
    return result


def _nozzle_material(catalog: dict[str, Any]) -> str:
    nozzle = _selected_profile(catalog, "nozzle_profile_id", "nozzle")
    return str(_payload(nozzle).get("material") or "").strip().casefold()



def printer_profile_with_validated_limits(
    catalog: dict[str, Any],
    target_profile: dict[str, Any],
) -> dict[str, Any]:
    """Attach only A1 hardware maxima from the exact validated local nozzle profile."""
    result = deepcopy(target_profile)
    payload = _payload(result)
    if canonical_model(payload.get("model")) == "H2S":
        limits = hardware_limits("H2S")
        for key in ("max_nozzle_temperature_c", "max_bed_temperature_c", "max_chamber_temperature_c"):
            if key in payload:
                value = float(payload[key])
                if not math.isfinite(value) or not 0 < value <= limits[key]:
                    raise CompatibilityContractError("Ungültige H2S-Hardwaregrenze.")
                limits[key] = value
        result["payload"] = {**payload, **{k:v for k,v in limits.items() if k.startswith("max_")}}
        return result
    try:
        nozzle_limit = float(payload["max_nozzle_temperature_c"])
        bed_limit = float(payload["max_bed_temperature_c"])
    except (KeyError, TypeError, ValueError):
        nozzle_limit = 0
        bed_limit = 0
    if (
        math.isfinite(nozzle_limit)
        and math.isfinite(bed_limit)
        and nozzle_limit > 0
        and bed_limit > 0
    ):
        return result

    target_model = str(
        payload.get("model") or target_profile.get("name") or ""
    ).strip().casefold()
    if "a1" not in target_model:
        raise CompatibilityContractError(
            "Nur Bambu-A1-Profile dürfen Hardwaregrenzen aus einer lokalen "
            "Validierungsautorität beziehen."
        )

    nozzle_profile = _selected_profile(catalog, "nozzle_profile_id", "nozzle")
    nozzle_payload = _payload(nozzle_profile)
    try:
        diameter = float(nozzle_payload["diameter_mm"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CompatibilityContractError(
            "Die gewählte Düse besitzt keinen validierten Durchmesser."
        ) from exc
    if not math.isfinite(diameter) or diameter not in {0.2, 0.4, 0.6, 0.8}:
        raise CompatibilityContractError(
            "Für die gewählte Düse existiert keine validierte A1-Hardwaregrenze."
        )

    candidates: list[dict[str, Any]] = []
    profiles = catalog.get("profiles", [])
    if isinstance(profiles, list):
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            if profile.get("kind") != "printer" or profile.get("source") != "local":
                continue
            candidate_payload = _payload(profile)
            candidate_model = str(
                candidate_payload.get("model") or profile.get("name") or ""
            ).strip().casefold()
            try:
                candidate_diameter = float(candidate_payload["nozzle_diameter_mm"])
                candidate_nozzle = float(candidate_payload["max_nozzle_temperature_c"])
                candidate_bed = float(candidate_payload["max_bed_temperature_c"])
            except (KeyError, TypeError, ValueError):
                continue
            if (
                "a1" in candidate_model
                and math.isfinite(candidate_diameter)
                and abs(candidate_diameter - diameter) < 0.000001
                and math.isfinite(candidate_nozzle)
                and math.isfinite(candidate_bed)
                and candidate_nozzle > 0
                and candidate_bed > 0
            ):
                candidates.append(profile)
    # The public catalog intentionally excludes nozzle-specific printer rows.
    # The curated A1 printer is the model-level authority for every supported nozzle.
    policy = "exact_local_a1_nozzle_authority"
    if not candidates and isinstance(profiles, list) and target_model in {"a1", "bambu lab a1"}:
        candidates = [profile for profile in profiles if isinstance(profile, dict)
                      and profile.get("id") == "printer.bambu_a1"
                      and profile.get("kind") == "printer"
                      and profile.get("source") == "builtin"
                      and _payload(profile).get("model") == "A1"
                      and _payload(profile).get("max_nozzle_temperature_c") == 300
                      and _payload(profile).get("max_bed_temperature_c") == 100]
        policy = "validated_builtin_a1_hardware"
    if len(candidates) != 1:
        raise CompatibilityContractError(
            "Für das gewählte A1-Druckerprofil fehlen eindeutige validierte "
            "Hardware-Temperaturgrenzen im Profilkatalog."
        )

    authority = candidates[0]
    authority_payload = _payload(authority)
    merged = dict(payload)
    merged["max_nozzle_temperature_c"] = float(
        authority_payload["max_nozzle_temperature_c"]
    )
    merged["max_bed_temperature_c"] = float(
        authority_payload["max_bed_temperature_c"]
    )
    merged["temperature_limits_source_profile_id"] = str(authority.get("id") or "")
    merged["temperature_limits_policy"] = policy
    result["payload"] = merged
    return result

def _printer_limits(target_profile: dict[str, Any]) -> tuple[float, float]:
    payload = _payload(target_profile)
    try:
        nozzle = float(payload["max_nozzle_temperature_c"])
        bed = float(payload["max_bed_temperature_c"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CompatibilityContractError(
            "Das A1-Druckerprofil enthält keine validierten Temperaturgrenzen."
        ) from exc
    if not math.isfinite(nozzle) or not math.isfinite(bed) or nozzle <= 0 or bed <= 0:
        raise CompatibilityContractError(
            "Die Temperaturgrenzen des A1-Druckerprofils sind ungültig."
        )
    hardware = a1_hardware_limits(payload.get("model") or target_profile.get("name"))
    if hardware:
        if nozzle > hardware["max_nozzle_temperature_c"] or bed > hardware["max_bed_temperature_c"]:
            raise CompatibilityContractError("Das Druckerprofil behauptet Temperaturgrenzen oberhalb der tatsächlichen A1-Hardware.")
    return nozzle, bed


def _profile_has_native_authority(profile: dict[str, Any]) -> bool:
    payload = _payload(profile)
    if payload.get("slicing_supported") is False:
        return False
    if str(payload.get("bambu_a1_compatibility") or "").startswith("unsupported"):
        return False
    source = str(profile.get("source") or "").strip().casefold()
    if source == "local":
        return (
            payload.get("profile_completeness") == "validated_complete"
            and payload.get("slicing_supported") is True
            and bool(str(payload.get("native_profile_name") or "").strip())
        )
    if source == "bambu_cloud":
        return any(
            bool(str(payload.get(key) or "").strip())
            for key in (
                "inherits",
                "profile_path",
                "native_profile_path",
                "native_profile_name",
                "setting_id",
                "filament_id",
            )
        )
    return False


def _explicit_plate_compatibility(
    payload: dict[str, Any],
    surface: str,
    bed_type: str,
) -> None:
    for key in (
        "compatible_build_plate_surfaces",
        "compatible_build_plates",
        "compatible_plates",
    ):
        raw = payload.get(key)
        if raw is None:
            continue
        values = raw if isinstance(raw, list) else [raw]
        normalized = {str(item).strip().casefold() for item in values if str(item).strip()}
        if surface.casefold() not in normalized and bed_type.casefold() not in normalized:
            raise CompatibilityContractError(
                "Das Filamentprofil erlaubt die ausgewählte Druckplatte nicht."
            )


def _explicit_nozzle_compatibility(
    payload: dict[str, Any],
    contract: A1NozzleContract,
) -> None:
    raw = payload.get("compatible_nozzle_diameters_mm")
    if raw is not None:
        values = raw if isinstance(raw, list) else [raw]
        allowed = _numbers(values)
        if not any(math.isclose(contract.diameter_mm, item, abs_tol=1e-6) for item in allowed):
            raise CompatibilityContractError(
                "Das Filamentprofil erlaubt den gewählten Düsendurchmesser nicht."
            )
    minimum = payload.get("minimum_nozzle_diameter_mm")
    if minimum is not None and contract.diameter_mm < _numbers(minimum)[0]:
        raise CompatibilityContractError(
            "Der gewählte Düsendurchmesser ist für dieses Filament zu klein."
        )


def _manual_profile(filament: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("filament_id", "tray_id"):
        identifier = str(filament.get(key) or "").strip()
        if identifier in _MANUAL_BY_ID:
            return _MANUAL_BY_ID[identifier]
    return None


def _validate_filament(
    filament: dict[str, Any],
    *,
    source_target: str,
    channel_index: int,
    nozzle_material: str,
    nozzle_contract: A1NozzleContract,
    max_nozzle_temperature_c: float,
    max_bed_temperature_c: float,
    build_plate_surface: str,
    bambu_bed_type: str,
) -> dict[str, Any]:
    selected = filament.get("selected_profile")
    if not isinstance(selected, dict) or not _profile_has_native_authority(selected):
        raise CompatibilityContractError(
            f"Materialkanal {channel_index} besitzt kein vollständig materialisierbares "
            "A1-Filamentprofil."
        )
    payload = _payload(selected)
    if canonical_model(payload.get("printer_model")) == "H2S":
        raise CompatibilityContractError("Ein H2S-Filamentprofil darf nicht am A1 verwendet werden.")
    manual = _manual_profile(filament)
    if manual is not None:
        targets = manual.get("targets")
        if not isinstance(targets, list) or source_target not in targets:
            target_label = "AMS" if source_target == "ams_slot" else "externe Spule"
            raise CompatibilityContractError(
                f"{manual.get('name') or manual.get('id')} ist am A1 nicht für "
                f"die Materialquelle {target_label} freigegeben."
            )

    compatibility = str(payload.get("bambu_a1_compatibility") or "").strip()
    if compatibility == "unsupported_temperature_limits":
        raise CompatibilityContractError(
            f"{selected.get('name')} überschreitet die Temperaturgrenzen des A1."
        )
    if str(payload.get("enclosure") or "").strip().casefold() == "required":
        raise CompatibilityContractError(
            f"{selected.get('name')} benötigt einen geschlossenen Bauraum; "
            "der Bambu Lab A1 ist ein Open-Frame-Drucker."
        )
    if payload.get("hardened_nozzle_required") is True and nozzle_material != "hardened_steel":
        raise CompatibilityContractError(
            f"{selected.get('name')} benötigt eine gehärtete Düse."
        )
    if source_target == "ams_slot" and payload.get("ams_lite_compatible") is False:
        raise CompatibilityContractError(
            f"{selected.get('name')} ist nicht für das AMS Lite des Bambu Lab A1 freigegeben."
        )

    _explicit_nozzle_compatibility(payload, nozzle_contract)
    _explicit_plate_compatibility(payload, build_plate_surface, bambu_bed_type)

    nozzle_values = _temperature_values(
        payload,
        (
            "nozzle_temperature_c",
            "recommended_nozzle_temperature_c",
            "first_layer_nozzle_temperature_c",
            "nozzle_temperature",
            "nozzle_temperature_initial_layer",
        ),
    )
    bed_values = _temperature_values(
        payload,
        (
            "bed_temperature_c",
            "first_layer_bed_temperature_c",
            "hot_plate_temp",
            "hot_plate_temp_initial_layer",
            "textured_plate_temp",
            "textured_plate_temp_initial_layer",
            "cool_plate_temp",
            "cool_plate_temp_initial_layer",
            "eng_plate_temp",
            "eng_plate_temp_initial_layer",
            "supertack_plate_temp",
            "supertack_plate_temp_initial_layer",
        ),
    )
    if manual is not None:
        nozzle_values.extend(_numbers(manual.get("nozzle_temp_max")))
    if not nozzle_values:
        raise CompatibilityContractError(
            f"{selected.get('name')} enthält keine prüfbare Düsentemperatur."
        )
    if max(nozzle_values) > max_nozzle_temperature_c:
        raise CompatibilityContractError(
            f"{selected.get('name')} überschreitet die maximale A1-Düsentemperatur "
            f"von {max_nozzle_temperature_c:g} °C."
        )
    if bed_values and max(bed_values) > max_bed_temperature_c:
        raise CompatibilityContractError(
            f"{selected.get('name')} überschreitet die maximale A1-Betttemperatur "
            f"von {max_bed_temperature_c:g} °C."
        )

    try:
        effective = preflight_filament_settings(payload)
        native_temperatures = check_filament_temperatures(effective, {
            "max_nozzle_temperature_c": max_nozzle_temperature_c,
            "max_bed_temperature_c": max_bed_temperature_c,
        }, bambu_bed_type)
    except ValueError as exc:
        raise CompatibilityContractError(f"{selected.get('name')}: {exc}") from exc

    return {
        "selected_profile_sha256": digest(selected),
        "effective_temperatures": native_temperatures,
        "channel": channel_index,
        "profile_id": str(selected.get("id") or ""),
        "profile_name": str(selected.get("name") or ""),
        "profile_source": str(selected.get("source") or ""),
        "manual_filament_id": str((manual or {}).get("id") or ""),
        "manual_target_confirmed": manual is not None,
        "nozzle_temperature_max_c": max(nozzle_values),
        "bed_temperature_max_c": max(bed_values) if bed_values else None,
        "enclosure": str(payload.get("enclosure") or "not_required"),
        "hardened_nozzle_required": payload.get("hardened_nozzle_required") is True,
    }


def validate_slicer_compatibility(
    catalog: dict[str, Any],
    nozzle_contract: A1NozzleContract,
    material_plan: dict[str, Any],
    build_plate_options: dict[str, Any],
    target_profile: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Attach profiles and reject any explicit or unresolved A1 incompatibility."""
    if canonical_model(_payload(target_profile).get("model")) == "H2S":
        return _validate_h2s(catalog, nozzle_contract, material_plan, build_plate_options, target_profile)
    if nozzle_contract.printer_model != "A1":
        raise CompatibilityContractError("Düse und Druckermodell passen nicht zusammen.")
    source = str(material_plan.get("source") or "")
    if source == "authoritative_ams_runtime":
        source_target = "ams_slot"
    elif source == "authoritative_external_spool_runtime":
        source_target = "external_spool"
    else:
        raise CompatibilityContractError(
            "Die Materialquelle wurde vor der Kompatibilitätsprüfung nicht aufgelöst."
        )

    bed_type = str(build_plate_options.get("bambu_bed_type") or "").strip()
    surface = str(build_plate_options.get("build_plate_surface") or "").strip()
    if bed_type not in _SUPPORTED_PLATE_TYPES or not surface:
        raise CompatibilityContractError(
            "Die ausgewählte Druckplatte besitzt keinen validierten Bambu-A1-Vertrag."
        )

    printer_payload = _payload(target_profile)
    dimensions = printer_payload.get("build_volume_mm") or [256, 256, 256]
    if not isinstance(dimensions, (list, tuple)) or len(dimensions) != 3:
        raise CompatibilityContractError("Der ausgewählte Drucker besitzt keine geprüften Bauraumabmessungen.")
    try:
        hardware = a1_hardware_limits(printer_payload.get("model") or target_profile.get("name"))
        width_limit = min(float(dimensions[0]), hardware["width_mm"]) if hardware else float(dimensions[0])
        depth_limit = min(float(dimensions[1]), hardware["depth_mm"]) if hardware else float(dimensions[1])
        validate_plate_dimensions(build_plate_options, (width_limit, depth_limit))
        if hardware:
            validate_physical_a1_plate(build_plate_options)
    except ValueError as exc:
        raise CompatibilityContractError(str(exc)) from exc

    resolved_plan = deepcopy(material_plan)
    filaments = resolved_plan.get("filaments")
    if not isinstance(filaments, list) or not filaments:
        raise CompatibilityContractError("Der Materialplan enthält keine Filamente.")
    attach_selected_profiles(catalog, filaments)

    nozzle_material = _nozzle_material(catalog)
    max_nozzle, max_bed = _printer_limits(target_profile)
    filament_results = [
        _validate_filament(
            filament,
            source_target=source_target,
            channel_index=index,
            nozzle_material=nozzle_material,
            nozzle_contract=nozzle_contract,
            max_nozzle_temperature_c=max_nozzle,
            max_bed_temperature_c=max_bed,
            build_plate_surface=surface,
            bambu_bed_type=bed_type,
        )
        for index, filament in enumerate(filaments, start=1)
        if isinstance(filament, dict)
    ]
    if len(filament_results) != len(filaments):
        raise CompatibilityContractError("Der Materialplan enthält einen ungültigen Kanal.")

    validate_shared_bed_temperatures([item["effective_temperatures"] for item in filament_results], bed_type)

    report: dict[str, Any] = {
        "status": "compatible",
        "contract_version": CONTRACT_VERSION,
        "printer_model": "Bambu Lab A1",
        "slicer_engine": "native_linux",
        "material_source": source_target,
        "nozzle": {
            "diameter_mm": nozzle_contract.diameter_mm,
            "material": nozzle_material,
        },
        "build_plate": {
            "surface": surface,
            "bambu_bed_type": bed_type,
            "width_mm": build_plate_options.get("build_plate_width_mm", dimensions[0]),
            "depth_mm": build_plate_options.get("build_plate_depth_mm", dimensions[1]),
        },
        "limits": {
            "max_nozzle_temperature_c": max_nozzle,
            "max_bed_temperature_c": max_bed,
        },
        "filaments": filament_results,
    }
    canonical = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    report["contract_sha256"] = hashlib.sha256(canonical).hexdigest()
    return resolved_plan, report


def _validate_h2s(catalog, nozzle_contract, material_plan, options, target_profile):
    if nozzle_contract.printer_model != "H2S":
        raise CompatibilityContractError("Die ausgewählte Düse gehört nicht zum H2S.")
    payload = _payload(target_profile)
    if _numbers(payload.get("build_volume_mm")) != [340., 320., 340.]:
        raise CompatibilityContractError("Der H2S benötigt den geprüften Bauraum 340 × 320 × 340 mm.")
    if validate_plate_dimensions(options, (340., 320.)) != (340., 320.):
        raise CompatibilityContractError("Abweichende physische H2S-Plattengrößen sind noch nicht validiert.")
    bed = str(options.get("bambu_bed_type") or "")
    surface = str(options.get("build_plate_surface") or "")
    if bed not in {"Textured PEI Plate", "High Temp Plate"} or not surface:
        raise CompatibilityContractError("Für diese H2S-Druckplatte fehlt der native Vertrag.")
    source = {"authoritative_ams_runtime":"ams_slot", "authoritative_external_spool_runtime":"external_spool"}.get(material_plan.get("source"))
    if not source:
        raise CompatibilityContractError("Die Materialquelle wurde nicht autoritativ aufgelöst.")
    limits = hardware_limits("H2S")
    for key in ("max_nozzle_temperature_c", "max_bed_temperature_c", "max_chamber_temperature_c"):
        value = float(payload.get(key, limits[key]))
        if not math.isfinite(value) or not 0 < value <= limits[key]:
            raise CompatibilityContractError("Das Profil behauptet ungültige H2S-Hardwaregrenzen.")
        limits[key] = value
    plan = deepcopy(material_plan)
    filaments = plan.get("filaments")
    if not isinstance(filaments, list) or not filaments or not all(isinstance(f, dict) for f in filaments):
        raise CompatibilityContractError("Der Materialplan enthält ungültige Kanäle.")
    attach_selected_profiles(catalog, filaments)
    material = _nozzle_material(catalog)
    results = []
    for index, filament in enumerate(filaments, 1):
        selected = filament.get("selected_profile")
        if not isinstance(selected, dict) or not _profile_has_native_authority(selected):
            raise CompatibilityContractError("Für H2S fehlt ein vollständig materialisierbares Filamentprofil.")
        settings = _payload(selected)
        if canonical_model(settings.get("printer_model")) != "H2S":
            raise CompatibilityContractError("Das Filamentprofil gehört nicht zum H2S.")
        native_name = str(settings.get("native_profile_name") or settings.get("inherits") or "")
        authority = h2s_defaults()["filaments"].get(native_name)
        printer_name = f"Bambu Lab H2S {nozzle_contract.diameter_mm:g} nozzle"
        if not authority or printer_name not in authority["compatible_printers"]:
            raise CompatibilityContractError("Die native H2S-Filamentbasis passt nicht zur Düse.")
        if source == "ams_slot" and (settings.get("ams_compatible") is not True or authority.get("ams_supported") is not True):
            raise CompatibilityContractError("Dieses H2S-Filamentprofil ist nicht für AMS freigegeben.")
        if settings.get("hardened_nozzle_required") is True and material != "hardened_steel":
            raise CompatibilityContractError("Dieses Filament benötigt eine gehärtete Düse.")
        _explicit_nozzle_compatibility(settings, nozzle_contract)
        _explicit_plate_compatibility(settings, surface, bed)
        temperatures = check_filament_temperatures(preflight_filament_settings(settings), limits, bed)
        results.append({"channel":index, "profile_id":selected.get("id"), "profile_name":selected.get("name"),
            "profile_source":selected.get("source"), "selected_profile_sha256":digest(selected),
            "effective_temperatures":temperatures, "native_profile_name":native_name})
    validate_shared_bed_temperatures([r["effective_temperatures"] for r in results], bed)
    chambers = {tuple(_numbers(r["effective_temperatures"].get("chamber_temperatures"))) for r in results}
    if len(chambers) > 1:
        raise CompatibilityContractError("Materialkanäle benötigen unterschiedliche gemeinsame Kammertemperaturen.")
    report = {"status":"compatible", "contract_version":CONTRACT_VERSION, "printer_model":"Bambu Lab H2S",
        "slicer_engine":"native_linux", "material_source":source,
        "nozzle":{"diameter_mm":nozzle_contract.diameter_mm, "material":material},
        "build_plate":{"surface":surface, "bambu_bed_type":bed, "width_mm":340, "depth_mm":320},
        "limits":{k:v for k,v in limits.items() if k.startswith("max_")}, "filaments":results}
    report["contract_sha256"] = digest(report)
    return plan, report
