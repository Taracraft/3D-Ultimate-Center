"""Persistent project and revision repository for 3D Ultimate Studio."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORE_VERSION = 1
STORE_KEY = "ultimate_3d_studio_v6.studio_projects"
DATA_PROJECTS = "studio_projects"
MAX_PROJECTS = 40
MAX_REVISIONS = 30
MAX_SNAPSHOT_BYTES = 12 * 1024 * 1024


class ProjectConflictError(RuntimeError):
    """Raised when the caller writes an obsolete project revision."""


class ProjectValidationError(ValueError):
    """Raised when a project payload is unsafe or invalid."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _name(value: Any) -> str:
    result = str(value or "").strip()
    if not result:
        raise ProjectValidationError("A project name is required")
    return result[:160]


def _snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProjectValidationError("snapshot must be a JSON object")
    if int(value.get("version", 0)) != 1:
        raise ProjectValidationError("snapshot version 1 is required")
    plates = value.get("plates")
    if not isinstance(plates, list) or not plates:
        raise ProjectValidationError("snapshot must contain at least one plate")
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProjectValidationError("snapshot must contain finite JSON values only") from exc
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise ProjectValidationError(
            f"snapshot exceeds the {MAX_SNAPSHOT_BYTES // 1024 // 1024} MiB project limit"
        )
    return deepcopy(value)


class StudioProjectRepository:
    """Bounded HA Store repository with optimistic revision protection."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
        self._projects: dict[str, dict[str, Any]] = {}
        self._loaded = False

    async def async_load(self) -> None:
        if self._loaded:
            return
        stored = await self._store.async_load() or {}
        projects = stored.get("projects", {})
        if isinstance(projects, dict):
            self._projects = {
                str(key): item for key, item in projects.items()
                if isinstance(item, dict)
            }
        self._loaded = True

    async def _save(self) -> None:
        await self._store.async_save({"projects": self._projects})

    @staticmethod
    def _summary(project: dict[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(project.get(key))
            for key in ("id", "name", "revision", "created_at", "updated_at")
        }

    async def async_list(self) -> list[dict[str, Any]]:
        await self.async_load()
        items = [self._summary(item) for item in self._projects.values()]
        items.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return items

    async def async_create(self, name: Any, snapshot: Any) -> dict[str, Any]:
        await self.async_load()
        if len(self._projects) >= MAX_PROJECTS:
            raise ProjectValidationError(f"at most {MAX_PROJECTS} projects are supported")
        now = _now()
        project_id = uuid4().hex
        clean_snapshot = _snapshot(snapshot)
        project = {
            "id": project_id,
            "name": _name(name),
            "revision": 1,
            "created_at": now,
            "updated_at": now,
            "snapshot": clean_snapshot,
            "revisions": [{
                "revision": 1,
                "created_at": now,
                "snapshot": deepcopy(clean_snapshot),
            }],
        }
        self._projects[project_id] = project
        await self._save()
        return deepcopy(project)

    async def async_get(self, project_id: str) -> dict[str, Any] | None:
        await self.async_load()
        project = self._projects.get(str(project_id))
        return deepcopy(project) if project is not None else None

    async def async_save_project(
        self,
        project_id: str,
        *,
        name: Any,
        snapshot: Any,
        expected_revision: int,
    ) -> dict[str, Any] | None:
        await self.async_load()
        project = self._projects.get(str(project_id))
        if project is None:
            return None
        current = int(project.get("revision", 0))
        if int(expected_revision) != current:
            raise ProjectConflictError(
                f"project revision conflict: expected {expected_revision}, current {current}"
            )
        revision = current + 1
        now = _now()
        clean_snapshot = _snapshot(snapshot)
        revisions = list(project.get("revisions", []))
        revisions.append({
            "revision": revision,
            "created_at": now,
            "snapshot": deepcopy(clean_snapshot),
        })
        project.update({
            "name": _name(name),
            "revision": revision,
            "updated_at": now,
            "snapshot": clean_snapshot,
            "revisions": revisions[-MAX_REVISIONS:],
        })
        await self._save()
        return deepcopy(project)

    async def async_revisions(self, project_id: str) -> list[dict[str, Any]] | None:
        project = await self.async_get(project_id)
        if project is None:
            return None
        return [
            {
                "revision": int(item.get("revision", 0)),
                "created_at": item.get("created_at"),
            }
            for item in reversed(project.get("revisions", []))
            if isinstance(item, dict)
        ]

    async def async_restore(
        self,
        project_id: str,
        *,
        source_revision: int,
        expected_revision: int,
    ) -> dict[str, Any] | None:
        await self.async_load()
        project = self._projects.get(str(project_id))
        if project is None:
            return None
        current = int(project.get("revision", 0))
        if int(expected_revision) != current:
            raise ProjectConflictError(
                f"project revision conflict: expected {expected_revision}, current {current}"
            )
        source = next(
            (
                item for item in project.get("revisions", [])
                if isinstance(item, dict) and int(item.get("revision", 0)) == int(source_revision)
            ),
            None,
        )
        if source is None:
            raise ProjectValidationError("requested source revision does not exist")
        return await self.async_save_project(
            project_id,
            name=project.get("name"),
            snapshot=source.get("snapshot"),
            expected_revision=current,
        )

    async def async_delete(self, project_id: str, *, expected_revision: int) -> bool:
        await self.async_load()
        project = self._projects.get(str(project_id))
        if project is None:
            return False
        current = int(project.get("revision", 0))
        if int(expected_revision) != current:
            raise ProjectConflictError(
                f"project revision conflict: expected {expected_revision}, current {current}"
            )
        del self._projects[str(project_id)]
        await self._save()
        return True


def get_studio_project_repository(hass: HomeAssistant) -> StudioProjectRepository:
    data = hass.data.setdefault(DOMAIN, {})
    runtime = data.get(DATA_PROJECTS)
    if not isinstance(runtime, StudioProjectRepository):
        runtime = StudioProjectRepository(hass)
        data[DATA_PROJECTS] = runtime
    return runtime
