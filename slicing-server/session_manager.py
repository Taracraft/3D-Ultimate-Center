"""Long-lived project session registry for API and WebSocket clients."""

from __future__ import annotations

from .project_service import ProjectService, ProjectSession


class ProjectSessionManager:
    def __init__(self, projects: ProjectService) -> None:
        self._projects = projects
        self._sessions: dict[str, ProjectSession] = {}

    def create(self, name: str) -> ProjectSession:
        session = self._projects.create(name)
        self._sessions[session.project.id] = session
        return session

    def get(self, project_id: str) -> ProjectSession:
        session = self._sessions.get(project_id)
        if session is None:
            session = self._projects.open(project_id)
            self._sessions[project_id] = session
        return session

    def discard(self, project_id: str) -> None:
        self._sessions.pop(project_id, None)

    def dirty_project_ids(self) -> tuple[str, ...]:
        return tuple(
            project_id
            for project_id, session in self._sessions.items()
            if session.dirty
        )

    def flush_all(self) -> None:
        for session in self._sessions.values():
            if session.dirty:
                session.save()