"""Structured Studio plan helpers for Printer Control Center v5.

Alpha18 introduces a shared planning structure for persistent Studio jobs.
Alpha19 makes the Studio job UI consume studio_plan as primary status data.
Alpha20 adds diagnostics test-window support.
The plan is intentionally validation/planning data only.
Real slicing and direct printing remain disabled.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

PLAN_VERSION = "5.0.0-beta38"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _pick(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value is not None and value != "":
            return value
    return None


def compact_profile(profile: Any) -> dict[str, Any] | None:
    if not isinstance(profile, dict):
        return None

    allowed = {
        "id",
        "name",
        "family",
        "material",
        "vendor",
        "build_plate_mm",
        "default_nozzle_mm",
        "nozzle_temp_c",
        "bed_temp_c",
        "max_volumetric_speed_mm3_s",
        "layer_height_mm",
        "wall_loops",
        "top_shell_layers",
        "bottom_shell_layers",
        "sparse_infill_density_percent",
        "sparse_infill_pattern",
        "support_enabled",
    }

    return {key: deepcopy(value) for key, value in profile.items() if key in allowed}


def normalize_profile_context(profile_context: Any | None) -> dict[str, Any]:
    context = _safe_dict(profile_context)
    selection = _safe_dict(context.get("selection"))

    printer_profile = compact_profile(context.get("printer_profile") or context.get("printer"))
    filament_profile = compact_profile(context.get("filament_profile") or context.get("filament"))
    process_profile = compact_profile(context.get("process_profile") or context.get("process"))

    normalized = {
        "version": PLAN_VERSION,
        "source": context.get("source") or "studio_plan",
        "selection": {
            "printer_profile_id": selection.get("printer_profile_id"),
            "filament_profile_id": selection.get("filament_profile_id"),
            "process_profile_id": selection.get("process_profile_id"),
        },
        "printer_profile": printer_profile,
        "filament_profile": filament_profile,
        "process_profile": process_profile,
        "valid": True,
        "warnings": [],
    }

    if not normalized["selection"]["printer_profile_id"]:
        normalized["valid"] = False
        normalized["warnings"].append("Missing printer profile selection.")

    if not normalized["selection"]["filament_profile_id"]:
        normalized["valid"] = False
        normalized["warnings"].append("Missing filament profile selection.")

    if not normalized["selection"]["process_profile_id"]:
        normalized["valid"] = False
        normalized["warnings"].append("Missing process profile selection.")

    if printer_profile is None:
        normalized["valid"] = False
        normalized["warnings"].append("Missing printer profile details.")

    if filament_profile is None:
        normalized["valid"] = False
        normalized["warnings"].append("Missing filament profile details.")

    if process_profile is None:
        normalized["valid"] = False
        normalized["warnings"].append("Missing process profile details.")

    return normalized


def normalize_dry_run_context(dry_run: Any | None) -> dict[str, Any]:
    source = _safe_dict(dry_run)

    warnings = []
    for item in source.get("warnings") or []:
        if item and item not in warnings:
            warnings.append(item)

    return {
        "version": PLAN_VERSION,
        "ok": bool(source.get("ok")),
        "job_present": bool(source.get("job_present", True)),
        "profile_context_valid": source.get("profile_context_valid") is not False,
        "status": source.get("status") or ("dry_run_ready" if source.get("ok") else "dry_run_incomplete"),
        "warnings": warnings,
        "updated_at": source.get("updated_at") or _utcnow(),
        "real_slicing_enabled": False,
        "direct_print_enabled": False,
    }


def normalize_studio_plan(
    job: dict[str, Any] | None,
    profile_context: dict[str, Any] | None = None,
    dry_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_job = _safe_dict(job)
    existing_plan = _safe_dict(source_job.get("studio_plan"))

    resolved_profile_context = (
        profile_context
        or source_job.get("profile_context")
        or existing_plan.get("profile_context")
        or {}
    )

    resolved_dry_run = (
        dry_run
        or source_job.get("dry_run")
        or existing_plan.get("dry_run")
        or {}
    )

    normalized_profile_context = normalize_profile_context(resolved_profile_context)
    normalized_dry_run = normalize_dry_run_context(resolved_dry_run)

    job_name = _pick(source_job, "name", "title", "file_name", "filename", "model_name") or "Studio job"
    job_id = _pick(source_job, "id", "job_id", "uid")
    now = _utcnow()

    warnings: list[str] = []
    for warning in normalized_profile_context.get("warnings") or []:
        if warning and warning not in warnings:
            warnings.append(warning)

    for warning in normalized_dry_run.get("warnings") or []:
        if warning and warning not in warnings:
            warnings.append(warning)

    return {
        "version": PLAN_VERSION,
        "schema": 1,
        "source": "studio_job_alpha18",
        "updated_at": now,
        "job": {
            "id": job_id,
            "name": job_name,
            "file_name": _pick(source_job, "file_name", "filename"),
            "file_path": _pick(source_job, "file_path", "path"),
            "source": _pick(source_job, "source", "origin"),
            "created_at": _pick(source_job, "created_at", "created"),
            "updated_at": _pick(source_job, "updated_at", "updated") or now,
        },
        "profile_context": normalized_profile_context,
        "dry_run": normalized_dry_run,
        "slicer": {
            "stage": "planning_only",
            "real_slicing_enabled": False,
            "direct_print_enabled": False,
            "worker_enabled": False,
        },
        "warnings": warnings,
        "valid": normalized_profile_context["valid"],
    }


def apply_studio_plan(
    job: dict[str, Any] | None,
    profile_context: dict[str, Any] | None = None,
    dry_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = deepcopy(_safe_dict(job))
    updated["studio_plan"] = normalize_studio_plan(updated, profile_context, dry_run)
    updated["profile_context"] = updated["studio_plan"]["profile_context"]
    updated["dry_run"] = updated["studio_plan"]["dry_run"]
    updated["real_slicing_enabled"] = False
    updated["direct_print_enabled"] = False
    return updated


def normalize_studio_job_patch(patch: dict[str, Any] | None) -> dict[str, Any]:
    updated = deepcopy(_safe_dict(patch))

    profile_context = (
        updated.get("profile_context")
        or _safe_dict(updated.get("studio_plan")).get("profile_context")
        or {}
    )

    dry_run = (
        updated.get("dry_run")
        or _safe_dict(updated.get("studio_plan")).get("dry_run")
        or {}
    )

    updated["studio_plan"] = normalize_studio_plan(updated, profile_context, dry_run)
    updated["profile_context"] = updated["studio_plan"]["profile_context"]
    updated["dry_run"] = updated["studio_plan"]["dry_run"]
    updated["real_slicing_enabled"] = False
    updated["direct_print_enabled"] = False
    return updated