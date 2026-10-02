"""Studio worker dry-run helpers for Printer Control Center v5.

Alpha16 adds profile-context validation for dry-run jobs.
Alpha17 adds dry-run result visualization support in the Studio UI.
Alpha18 adds shared persistent Studio plan data for jobs.
Alpha19 keeps Dry-Run plan output compatible with the job UI.
Alpha20 adds Studio health diagnostics for the test window.
This module still does not perform real slicing and never starts direct printing.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .studio_plan import normalize_studio_plan

WORKER_VERSION = "5.0.0-beta38"


def _utcnow() -> str:
    """Return an ISO timestamp with UTC timezone."""
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> dict[str, Any]:
    """Return value when it is a dict, otherwise an empty dict."""
    return value if isinstance(value, dict) else {}


def _compact_profile(profile: Any) -> dict[str, Any] | None:
    """Return a compact profile representation suitable for job storage."""
    if not isinstance(profile, dict):
        return None

    allowed_keys = {
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

    return {key: deepcopy(value) for key, value in profile.items() if key in allowed_keys}


def normalize_profile_context(profile_context: Any | None) -> dict[str, Any]:
    """Normalize the Studio profile context supplied by the frontend."""
    context = _safe_dict(profile_context)

    selection = _safe_dict(context.get("selection"))
    printer_profile = _compact_profile(context.get("printer_profile"))
    filament_profile = _compact_profile(context.get("filament_profile"))
    process_profile = _compact_profile(context.get("process_profile"))

    normalized = {
        "version": WORKER_VERSION,
        "source": context.get("source") or "studio_ui",
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


def build_dry_run_result(
    job: dict[str, Any] | None,
    profile_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a dry-run patch for a Studio job.

    The result is intentionally a planning/validation object only.
    It must not invoke a slicer and must not start a print job.
    """
    target_job = _safe_dict(job)
    normalized_profile_context = normalize_profile_context(profile_context)
    now = _utcnow()

    job_name = (
        target_job.get("name")
        or target_job.get("title")
        or target_job.get("file_name")
        or target_job.get("filename")
        or "Studio job"
    )

    dry_run_ok = bool(target_job) and normalized_profile_context["valid"]

    warnings: list[str] = []
    if not target_job:
        warnings.append("No Studio job was supplied to the dry-run worker.")

    warnings.extend(normalized_profile_context["warnings"])

    result = {
        "version": WORKER_VERSION,
        "updated_at": now,
        "status": "dry_run_ready" if dry_run_ok else "dry_run_incomplete",
        "profile_context": normalized_profile_context,
        "worker": {
            "version": WORKER_VERSION,
            "state": "dry_run_ready" if dry_run_ok else "dry_run_incomplete",
            "dry_run": True,
            "real_slicing_enabled": False,
            "direct_print_enabled": False,
            "message": (
                "Dry-run profile context validation completed."
                if dry_run_ok
                else "Dry-run profile context validation completed with warnings."
            ),
            "warnings": warnings,
            "job_name": job_name,
            "updated_at": now,
        },
        "dry_run": {
            "ok": dry_run_ok,
            "job_present": bool(target_job),
            "profile_context_valid": normalized_profile_context["valid"],
            "real_slicing_enabled": False,
            "direct_print_enabled": False,
            "warnings": warnings,
            "updated_at": now,
        },
    }

    result["studio_plan"] = normalize_studio_plan(
        target_job,
        normalized_profile_context,
        result.get("dry_run"),
    )

    return result