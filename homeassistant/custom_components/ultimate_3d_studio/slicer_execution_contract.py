"""Bind selected profiles to the worker request and enforce printer geometry."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import re
from typing import Any
try:
    from .printer_model_contract import canonical_model, hardware_limits, h2s_defaults
except ImportError:
    import importlib.util as _model_import
    from pathlib import Path as _ModelPath
    _spec = _model_import.spec_from_file_location("studio_printer_model_authority", _ModelPath(__file__).with_name("printer_model_contract.py"))
    _authority = _model_import.module_from_spec(_spec)
    _spec.loader.exec_module(_authority)
    canonical_model = _authority.canonical_model
    hardware_limits = _authority.hardware_limits
    h2s_defaults = _authority.h2s_defaults


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _body(target: dict[str, Any], overrides: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": 1,
        "target_printer": deepcopy(target),
        "process_overrides": {k: deepcopy(v) for k, v in overrides.items() if k != "execution_contract"},
        "material_plan": deepcopy(plan),
    }


def bind_execution_contract(target: dict[str, Any], overrides: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    body = _body(target, overrides, plan)
    return {"schema": 1, "sha256": digest(body)}


def validate_execution_contract(job: dict[str, Any]) -> bool:
    overrides = job.get("process_overrides") or {}
    contract = overrides.get("execution_contract")
    required = overrides.get("require_execution_contract") is True
    if contract is None:
        if required:
            raise ValueError("Der durchgängige Profil-/G-Code-Vertrag fehlt.")
        return False
    if not isinstance(contract, dict) or contract.get("schema") != 1:
        raise ValueError("Der Profil-/G-Code-Vertrag ist ungültig.")
    target = job.get("target_printer") or {}
    body = _body(target, overrides, job.get("material_plan") or {})
    if digest(body) != contract.get("sha256"):
        raise ValueError("Drucker-, Prozess- oder Filamentwerte wurden nach der Vertragsprüfung verändert.")
    report = target.get("compatibility_contract")
    if required and not isinstance(report, dict):
        raise ValueError("Der geprüfte Kompatibilitätsbericht fehlt im nativen Auftrag.")
    if isinstance(report, dict):
        report_body = {k: v for k, v in report.items() if k != "contract_sha256"}
        if digest(report_body) != report.get("contract_sha256") or report.get("status") != "compatible":
            raise ValueError("Der Kompatibilitätsbericht ist nicht integer.")
        filaments = (job.get("material_plan") or {}).get("filaments") or []
        proofs = report.get("filaments") or []
        if len(filaments) != len(proofs):
            raise ValueError("Die geprüften Materialkanäle stimmen nicht mit dem Auftrag überein.")
        for filament, proof in zip(filaments, proofs, strict=True):
            if proof.get("selected_profile_sha256") != digest(filament.get("selected_profile")):
                raise ValueError("Ein Filamentprofil weicht vom geprüften Kompatibilitätsbericht ab.")
    for key in ("native_machine_profile", "native_process_profile", "nozzle_diameter_mm"):
        if job.get(key) is not None and job[key] != target.get(key):
            raise ValueError(f"Der native Auftrag weicht beim Feld {key} vom geprüften Druckervertrag ab.")
    return True


def a1_hardware_limits(model: object) -> dict[str, float] | None:
    canonical = re.sub(r"[^a-z0-9]+", " ", str(model or "").casefold()).strip()
    if canonical not in {"a1", "bambu lab a1", "bambu a1"}:
        return None
    return {"max_nozzle_temperature_c": 300.0, "max_bed_temperature_c": 100.0,
            "width_mm": 256.0, "depth_mm": 256.0, "height_mm": 256.0}


def validate_plate_dimensions(options: dict[str, Any], dimensions: tuple[float, float]) -> tuple[float, float]:
    values = []
    for key, maximum in zip(("build_plate_width_mm", "build_plate_depth_mm"), dimensions, strict=True):
        raw = options.get(key, maximum)
        if isinstance(raw, bool):
            raise ValueError("Die Druckplattenabmessungen sind ungültig.")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Die Druckplattenabmessungen sind ungültig.") from exc
        if not math.isfinite(value) or value <= 0 or not math.isfinite(maximum) or maximum <= 0:
            raise ValueError("Die Druckplattenabmessungen müssen endlich und größer als null sein.")
        if value > maximum + 1e-6:
            raise ValueError("Die gewählte Druckplatte ist größer als die physische Druckfläche des gewählten Druckers.")
        values.append(value)
    return values[0], values[1]


def validate_physical_a1_plate(options: dict[str, Any]) -> tuple[float, float]:
    size = validate_plate_dimensions(options, (256.0, 256.0))
    if any(abs(value - 256.0) > 1e-6 for value in size):
        raise ValueError("Die gewählte physische Druckplatte passt nicht zum A1-Maschinenvertrag (256 × 256 mm); kleinere Platten benötigen einen eigenen geprüften Maschinenablauf.")
    return size


def job_hardware_limits(job: dict[str, Any]) -> dict[str, float] | None:
    target = job.get("target_printer") or {}
    model = canonical_model(target.get("model") or target.get("name"))
    limits = hardware_limits(model)
    if limits is None and (job.get("process_overrides") or {}).get("require_execution_contract") is True:
        raise ValueError("Für diesen Drucker fehlt ein geprüfter nativer Hardware-/G-Code-Vertrag.")
    if limits:
        options = job.get("process_overrides") or {}
        if model == "A1":
            validate_physical_a1_plate(options)
        else:
            size = validate_plate_dimensions(options, (340., 320.))
            if size != (340., 320.):
                raise ValueError("Physische H2S-Platten benötigen den geprüften 340 × 320 mm Maschinenvertrag.")
            diameter = str(float(target.get("nozzle_diameter_mm")))
            machine = h2s_defaults()["machines"].get(diameter)
            process = h2s_defaults()["processes"].get(diameter)
            if not machine or target.get("native_machine_profile") != machine["native_path"] or target.get("native_process_profile") != process["native_path"]:
                raise ValueError("H2S-Maschine, Prozess und Düse passen nicht zusammen.")
            if options.get("require_execution_contract") is True:
                contract = target.get("machine_gcode_contract") or {}
                if contract.get("printer_model") != "H2S":
                    raise ValueError("Der H2S-Auftrag benötigt seine vier Maschinen-/Soundabschnitte.")
        selected_limits = (target.get("compatibility_contract") or {}).get("limits") or {}
        for key in ("max_nozzle_temperature_c", "max_bed_temperature_c", "max_chamber_temperature_c"):
            if key not in limits:
                continue
            if key in selected_limits:
                value = float(selected_limits[key])
                if not math.isfinite(value) or value <= 0 or value > limits[key]:
                    raise ValueError("Der Kompatibilitätsbericht behauptet ungültige Hardwaregrenzen.")
                limits[key] = value
    return limits
