"""Persistent geometry and slice plans for Ultimate 3D Studio V6."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORE_VERSION = 1
STORE_KEY = "ultimate_3d_studio_v6.slicer_plans"
DATA_SLICER_RUNTIME = "slicer_plan_runtime"
_MAX_PLANS = 200
_ALLOWED_SUFFIXES = {".stl", ".3mf"}


class SlicerRuntimeError(ValueError):
    """Raised for invalid geometry or persistent slice-plan data."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_filename(value: object) -> str:
    raw = Path(str(value or "scene.stl")).name.strip()
    cleaned = "".join(
        character if character.isalnum() or character in "-_. " else "_"
        for character in raw
    ).strip(" .")
    name = (cleaned or "scene.stl")[:180]
    if Path(name).suffix.casefold() not in _ALLOWED_SUFFIXES:
        raise SlicerRuntimeError("only STL or 3MF geometry is supported")
    return name


class V6SlicerPlanRuntime:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
        self._plans: list[dict[str, Any]] = []
        self._loaded = False
        self._geometry_root = Path(
            hass.config.path(".storage", "ultimate_3d_studio_v6_slicer_geometry")
        )

    async def async_load(self) -> None:
        if self._loaded:
            return
        stored = await self._store.async_load() or {}
        plans = stored.get("plans", [])
        self._plans = [deepcopy(item) for item in plans if isinstance(item, dict)][:_MAX_PLANS]
        self._loaded = True

    async def _async_save(self) -> None:
        await self._store.async_save({"plans": self._plans[:_MAX_PLANS]})

    async def async_store_geometry(self, filename: str, payload: bytes) -> dict[str, Any]:
        name = _safe_filename(filename)
        if not payload:
            raise SlicerRuntimeError("geometry is empty")
        geometry_id = f"geometry-{uuid4().hex}"
        suffix = Path(name).suffix.casefold()
        path = self._geometry_root / f"{geometry_id}{suffix}"

        def write() -> None:
            self._geometry_root.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".new")
            temporary.write_bytes(payload)
            os.replace(temporary, path)

        await self.hass.async_add_executor_job(write)
        return {
            "geometry_id": geometry_id,
            "filename": name,
            "size_bytes": len(payload),
            "sha256": sha256(payload).hexdigest(),
            "path": str(path),
        }

    def _geometry_record(self, geometry_id: str) -> tuple[Path, int] | None:
        if not geometry_id.startswith("geometry-") or len(geometry_id) != 41:
            return None
        for suffix in _ALLOWED_SUFFIXES:
            path = self._geometry_root / f"{geometry_id}{suffix}"
            if path.is_file():
                return path, path.stat().st_size
        return None

    async def async_list_plans(self) -> list[dict[str, Any]]:
        await self.async_load()
        return deepcopy(self._plans)

    async def async_get_plan(self, plan_id: str) -> dict[str, Any] | None:
        await self.async_load()
        plan = next((item for item in self._plans if item.get("id") == plan_id), None)
        return deepcopy(plan) if plan is not None else None

    async def async_create_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self.async_load()
        geometry_id = str(payload.get("geometry_id", "")).strip()
        geometry_record = await self.hass.async_add_executor_job(
            self._geometry_record,
            geometry_id,
        )
        if geometry_record is None:
            raise SlicerRuntimeError("stored geometry was not found")
        geometry_path, geometry_size = geometry_record
        selection = payload.get("profile_selection")
        analysis = payload.get("analysis")
        preview = payload.get("preview")
        if not isinstance(selection, dict):
            raise SlicerRuntimeError("profile_selection must be an object")
        if not isinstance(analysis, dict):
            raise SlicerRuntimeError("analysis must be an object")
        if not isinstance(preview, dict):
            raise SlicerRuntimeError("preview must be an object")
        try:
            layer_height = float(payload.get("layer_height_mm"))
        except (TypeError, ValueError) as exc:
            raise SlicerRuntimeError("invalid layer height") from exc
        if layer_height <= 0:
            raise SlicerRuntimeError("invalid layer height")
        name = str(payload.get("name", "Slice-Plan")).strip()[:240] or "Slice-Plan"
        now = _now()
        plan = {
            "id": f"slice-plan-{uuid4().hex}",
            "status": "geometry_analyzed",
            "name": name,
            "project_id": payload.get("project_id"),
            "plate_id": payload.get("plate_id"),
            "geometry_id": geometry_id,
            "geometry_filename": str(payload.get("geometry_filename") or geometry_path.name),
            "geometry_size_bytes": geometry_size,
            "profile_selection": deepcopy(selection),
            "layer_height_mm": layer_height,
            "analysis": deepcopy(analysis),
            "preview": deepcopy(preview),
            "gcode_provider": "bambu_studio_cli_worker",
            "print_command_created": False,
            "created_at": now,
            "updated_at": now,
        }
        self._plans.insert(0, plan)
        self._plans = self._plans[:_MAX_PLANS]
        await self._async_save()
        return deepcopy(plan)

    async def async_delete_plan(self, plan_id: str) -> bool:
        await self.async_load()
        before = len(self._plans)
        self._plans = [item for item in self._plans if item.get("id") != plan_id]
        if len(self._plans) == before:
            return False
        await self._async_save()
        return True

    # Compatibility API used by the previous V6 geometry-plan implementation.
    async def async_list(self) -> list[dict[str, Any]]:
        return await self.async_list_plans()

    async def async_get(self, plan_id: str) -> dict[str, Any] | None:
        return await self.async_get_plan(plan_id)

    async def async_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "geometry_id" in payload:
            return await self.async_create_plan(payload)
        await self.async_load()
        filename = str(payload.get("filename", "")).strip()
        geometry = payload.get("geometry")
        profiles = payload.get("profiles")
        try:
            layer_height = float(payload.get("layer_height_mm"))
            count = int(payload.get("layer_count"))
        except (TypeError, ValueError) as exc:
            raise SlicerRuntimeError("invalid layer information") from exc
        if not filename or not isinstance(geometry, dict) or not isinstance(profiles, dict):
            raise SlicerRuntimeError("invalid legacy slice plan")
        if layer_height <= 0 or count <= 0:
            raise SlicerRuntimeError("invalid layer information")
        now = _now()
        plan = {
            "id": f"slice-plan-{uuid4().hex}",
            "filename": filename[:260],
            "status": "geometry_analyzed",
            "geometry": deepcopy(geometry),
            "profiles": deepcopy(profiles),
            "layer_height_mm": layer_height,
            "layer_count": count,
            "selected_layer": max(0, min(int(payload.get("selected_layer", 0)), count - 1)),
            "gcode_provider": "not_configured",
            "print_command_created": False,
            "created_at": now,
            "updated_at": now,
        }
        self._plans.insert(0, plan)
        self._plans = self._plans[:_MAX_PLANS]
        await self._async_save()
        return deepcopy(plan)


def get_slicer_runtime(hass: HomeAssistant) -> V6SlicerPlanRuntime:
    data = hass.data.setdefault(DOMAIN, {})
    runtime = data.get(DATA_SLICER_RUNTIME)
    if not isinstance(runtime, V6SlicerPlanRuntime):
        runtime = V6SlicerPlanRuntime(hass)
        data[DATA_SLICER_RUNTIME] = runtime
    return runtime


def get_slicer_plan_runtime(hass: HomeAssistant) -> V6SlicerPlanRuntime:
    return get_slicer_runtime(hass)