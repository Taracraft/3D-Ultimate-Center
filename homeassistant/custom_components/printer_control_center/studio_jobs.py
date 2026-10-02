"""Persistent v5 Studio slice-job store for Printer Control Center.

This module is intentionally standalone and does not depend on external Bambu
Lab Home Assistant integrations.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

STORE_DIRECTORY = "printer_control_center"
STORE_FILENAME = "studio_jobs.json"
MAX_JOBS = 100


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _store_path(hass: Any) -> Path:
    return Path(hass.config.path(STORE_DIRECTORY, STORE_FILENAME))


def _load_jobs_sync(path: Path) -> list[dict[str, Any]]:
    try:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [job for job in data if isinstance(job, dict)]
        if isinstance(data, dict) and isinstance(data.get("jobs"), list):
            return [job for job in data["jobs"] if isinstance(job, dict)]
    except Exception:
        return []
    return []


def _save_jobs_sync(path: Path, jobs: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "printer-control-center.v5.slice-jobs",
        "version": "5.0.0-beta38",
        "updatedAt": _utcnow(),
        "jobs": jobs[:MAX_JOBS],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def async_load_studio_jobs(hass: Any) -> list[dict[str, Any]]:
    path = _store_path(hass)
    return await hass.async_add_executor_job(_load_jobs_sync, path)


async def async_save_studio_jobs(hass: Any, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean_jobs = [job for job in jobs if isinstance(job, dict)][:MAX_JOBS]
    path = _store_path(hass)
    await hass.async_add_executor_job(_save_jobs_sync, path, clean_jobs)
    return clean_jobs


def build_studio_job(plan: dict[str, Any] | None = None, serial: str | None = None) -> dict[str, Any]:
    """Build a persistent Studio job from a gallery/file-manager handoff plan.

    Alpha22 promotes the previous isolated preview into a real, persistent
    Studio job. The job stays planning-only: real slicing and direct printing
    remain explicitly disabled.
    """
    plan_data = deepcopy(plan or {})
    model = _safe_dict(plan_data.get("model"))

    source = str(plan_data.get("source") or model.get("source") or plan_data.get("origin") or "")
    file_path = str(model.get("path") or plan_data.get("file_path") or plan_data.get("path") or "")
    file_name = str(
        model.get("name")
        or plan_data.get("file_name")
        or plan_data.get("filename")
        or plan_data.get("modelName")
        or (Path(file_path).name if file_path else "")
        or "3MF model"
    )
    model_name = str(model.get("name") or plan_data.get("modelName") or file_name or "3MF model")

    transform = _safe_dict(plan_data.get("transform"))
    if not transform:
        transform = {
            "x": 0,
            "y": 0,
            "z": 0,
            "rx": 0,
            "ry": 0,
            "rz": 0,
            "scale": 100,
            "sx": 100,
            "sy": 100,
            "sz": 100,
        }

    profile_context = _safe_dict(plan_data.get("profile_context"))
    created = _utcnow()

    return {
        "id": f"job-{uuid4().hex[:12]}",
        "schema": "printer-control-center.v5.slice-job",
        "version": "5.0.0-beta38",
        "createdAt": created,
        "updatedAt": created,
        "serial": str(serial or plan_data.get("serial") or model.get("serial") or ""),
        "name": model_name,
        "modelName": model_name,
        "file_name": file_name,
        "filename": file_name,
        "file_path": file_path,
        "path": file_path,
        "source": source,
        "origin": source,
        "modelKey": str(plan_data.get("modelKey") or file_path or file_name),
        "model": model or {
            "name": model_name,
            "path": file_path,
            "source": source,
        },
        "transform": transform,
        "profile_context": profile_context,
        "plan": plan_data,
        "status": "prepared",
        "progress": 0,
        "stage": "waiting",
        "message": "Studio-Job aus Galerie/Dateimanager vorbereitet. Echter Slicer-Lauf ist noch deaktiviert.",
        "output": None,
        "directPrint": False,
        "real_slicing_enabled": False,
        "direct_print_enabled": False,
        "workerStatus": "not_started",
        "workerCommand": None,
        "workerMessage": "Slicer-Worker ist vorbereitet, aber noch nicht aktiviert.",
    }


async def async_create_studio_job(
    hass: Any,
    plan: dict[str, Any] | None = None,
    serial: str | None = None,
) -> dict[str, Any]:
    jobs = await async_load_studio_jobs(hass)
    job = build_studio_job(plan, serial)
    jobs = [job, *jobs]
    await async_save_studio_jobs(hass, jobs)
    return job


async def async_update_studio_job(
    hass: Any,
    job_id: str,
    patch: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    jobs = await async_load_studio_jobs(hass)
    patch_data = dict(patch or {})
    updated_job: dict[str, Any] | None = None

    for job in jobs:
        if str(job.get("id")) == str(job_id):
            job.update(patch_data)
            job["updatedAt"] = _utcnow()
            updated_job = job
            break

    if updated_job is not None:
        await async_save_studio_jobs(hass, jobs)

    return updated_job


async def async_clear_studio_jobs(hass: Any) -> list[dict[str, Any]]:
    await async_save_studio_jobs(hass, [])
    return []