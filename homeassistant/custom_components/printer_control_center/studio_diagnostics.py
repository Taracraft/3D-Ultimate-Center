"""Studio diagnostics helpers for Printer Control Center v5.

Alpha20 is a test-window release. It adds health reporting for the Studio plan,
profile bank, Dry-Run worker and frontend job UI state.
Real slicing and direct printing remain disabled.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DIAGNOSTICS_VERSION = "5.0.0-beta38"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _ok(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "detail": detail,
    }


def build_studio_health_report(
    profile_bank: dict[str, Any] | None = None,
    jobs: list[Any] | None = None,
    dry_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a non-invasive Studio health report."""
    bank = _safe_dict(profile_bank)
    job_list = _safe_list(jobs)
    dry = _safe_dict(dry_run)

    selection = _safe_dict(bank.get("selection"))
    printer_profiles = _safe_dict(bank.get("printer_profiles"))
    filaments = _safe_dict(bank.get("filaments"))
    process_profiles = _safe_dict(bank.get("process_profiles"))

    dry_run_context = _safe_dict(dry.get("profile_context"))
    dry_run_plan = _safe_dict(dry.get("studio_plan"))
    dry_run_slicer = _safe_dict(dry_run_plan.get("slicer"))

    active_job = {}
    for entry in job_list:
        candidate = _safe_dict(entry.get("job") if isinstance(entry, dict) else {})
        if not candidate and isinstance(entry, dict):
            candidate = entry
        if candidate:
            active_job = candidate
            break

    active_plan = _safe_dict(active_job.get("plan"))
    active_model = _safe_dict(active_job.get("model") or active_plan.get("model"))
    active_transform = _safe_dict(active_job.get("transform") or active_plan.get("transform"))
    active_path = active_job.get("file_path") or active_job.get("path") or active_model.get("path")
    active_source = active_job.get("source") or active_job.get("origin") or active_model.get("source")

    checks = [
        _ok(
            "profile_bank_present",
            bool(bank),
            "Profile bank object is available." if bank else "Profile bank object is missing.",
        ),
        _ok(
            "profile_bank_selection_present",
            bool(selection.get("printer_profile_id") and selection.get("filament_profile_id") and selection.get("process_profile_id")),
            "Printer, filament and process selections are present.",
        ),
        _ok(
            "profile_bank_has_printers",
            bool(printer_profiles),
            f"Printer profiles: {len(printer_profiles)}",
        ),
        _ok(
            "profile_bank_has_filaments",
            bool(filaments),
            f"Filament profiles: {len(filaments)}",
        ),
        _ok(
            "profile_bank_has_process_profiles",
            bool(process_profiles),
            f"Process profiles: {len(process_profiles)}",
        ),
        _ok(
            "dry_run_context_present",
            bool(dry_run_context),
            "Dry-Run profile context is available." if dry_run_context else "Dry-Run profile context not available yet.",
        ),
        _ok(
            "studio_plan_present",
            bool(dry_run_plan),
            "Dry-Run returned a studio_plan." if dry_run_plan else "No studio_plan returned yet.",
        ),
        _ok(
            "job_ui_payload_present",
            isinstance(job_list, list),
            f"Frontend supplied {len(job_list)} job entries for diagnostics.",
        ),
        _ok(
            "active_studio_job_present",
            bool(active_job),
            "Active persistent Studio job is available." if active_job else "No active persistent Studio job supplied yet.",
        ),
        _ok(
            "gallery_handoff_ready",
            bool(active_path and active_source),
            f"Gallery handoff source={active_source}, path={active_path}" if active_path and active_source else "No gallery/file-manager handoff path detected yet.",
        ),
        _ok(
            "transform_state_present",
            bool(active_transform),
            "Transform state is attached to the active job." if active_transform else "No transform state found on active job.",
        ),
        _ok(
            "persistent_job_store_ready",
            isinstance(job_list, list),
            f"Studio job payload contains {len(job_list)} entries.",
        ),
        _ok(
            "real_slicing_disabled",
            dry_run_slicer.get("real_slicing_enabled") is not True and dry.get("real_slicing_enabled") is not True,
            "Real slicing is disabled.",
        ),
        _ok(
            "direct_print_disabled",
            dry_run_slicer.get("direct_print_enabled") is not True and dry.get("direct_print_enabled") is not True,
            "Direct print is disabled.",
        ),
    ]

    ok_count = sum(1 for item in checks if item["ok"])
    warn_count = len(checks) - ok_count

    return {
        "version": DIAGNOSTICS_VERSION,
        "updated_at": _utcnow(),
        "status": "ok" if warn_count == 0 else "warnings",
        "summary": {
            "ok": ok_count,
            "warnings": warn_count,
            "checks": len(checks),
        },
        "checks": checks,
        "safety": {
            "real_slicing_enabled": False,
            "direct_print_enabled": False,
            "stage": "diagnostics_only",
        },
    }