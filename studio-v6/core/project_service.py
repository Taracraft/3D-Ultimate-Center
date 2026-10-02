"""Project Core application service."""

from __future__ import annotations

from dataclasses import replace

from .common import new_id, utc_now
from .history import History
from .scene_commands import SceneCommand
from .snapshot_codec import decode_project, encode_project
from .sqlite_projects import SqliteProjectRepository
from .studio import PlateRecord, ProjectRecord


class ProjectSession:
    def __init__(
        self,
        repository: SqliteProjectRepository,
        project: ProjectRecord,
        history_limit: int = 100,
    ) -> None:
        self._repository = repository
        self._history = History.create(project, history_limit)
        self._dirty = False

    @property
    def project(self) -> ProjectRecord:
        return self._history.current

    @property
    def dirty(self) -> bool:
        return self._dirty

    def execute(self, command: SceneCommand) -> ProjectRecord:
        changed = command.apply(self.project)
        updated = replace(
            changed,
            revision=self.project.revision + 1,
            updated_at=utc_now(),
        )
        self._history.push(updated)
        self._dirty = True
        return updated

    def undo(self) -> ProjectRecord:
        before = self.project
        current = self._history.undo()
        self._dirty = self._dirty or current is not before
        return current

    def redo(self) -> ProjectRecord:
        before = self.project
        current = self._history.redo()
        self._dirty = self._dirty or current is not before
        return current

    def save(self) -> ProjectRecord:
        project = self.project
        self._repository.save(project)
        self._repository.save_revision(project, encode_project(project))
        self._dirty = False
        return project

    def restore_revision(self, revision: int | None = None) -> ProjectRecord:
        snapshot = self._repository.snapshot(self.project.id, revision)
        if snapshot is None:
            raise KeyError((self.project.id, revision))
        restored = decode_project(snapshot)
        if restored.id != self.project.id:
            raise ValueError("snapshot project id does not match active project")
        restored = replace(
            restored,
            revision=self.project.revision + 1,
            updated_at=utc_now(),
        )
        self._history.push(restored)
        self._dirty = True
        return restored


class ProjectService:
    def __init__(self, repository: SqliteProjectRepository) -> None:
        self._repository = repository

    def create(self, name: str) -> ProjectSession:
        normalized = name.strip()
        if not normalized:
            raise ValueError("project name must not be empty")
        now = utc_now()
        plate = PlateRecord(
            id=new_id("plate"),
            name="Plate 1",
            order_index=0,
        )
        project = ProjectRecord(
            id=new_id("project"),
            name=normalized,
            revision=1,
            plates=(plate,),
            created_at=now,
            updated_at=now,
        )
        self._repository.save(project)
        self._repository.save_revision(project, encode_project(project))
        return ProjectSession(self._repository, project)

    def open(self, project_id: str) -> ProjectSession:
        project = self._repository.get(project_id)
        if project is None:
            raise KeyError(project_id)
        return ProjectSession(self._repository, project)