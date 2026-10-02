"""Framework-neutral V1 application facade."""

from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from core.command_factory import scene_command_from_payload
from core.gallery_service import GalleryService
from core.handoff import HandoffService
from core.project_service import ProjectService
from core.session_manager import ProjectSessionManager
from core.upload_finalizer import UploadFinalizer
from core.upload_service import UploadService

from .contracts import ApiError, ApiResponse


class V1Application:
    def __init__(
        self,
        uploads: UploadService,
        finalizer: UploadFinalizer,
        gallery: GalleryService,
        projects: ProjectService,
        sessions: ProjectSessionManager,
        handoffs: HandoffService,
    ) -> None:
        self._uploads = uploads
        self._finalizer = finalizer
        self._gallery = gallery
        self._projects = projects
        self._sessions = sessions
        self._handoffs = handoffs

    def create_upload(self, payload: dict) -> ApiResponse:
        return self._guard(
            lambda: asdict(
                self._uploads.create(
                    original_name=str(payload["original_name"]),
                    expected_size=int(payload["expected_size"]),
                    source_ui=str(payload["source_ui"]),
                    target=str(payload["target"]),
                    chunk_size=int(payload.get("chunk_size", 4 * 1024 * 1024)),
                    expected_digest=payload.get("expected_digest"),
                )
            )
        )

    def write_upload_chunk(self, upload_id: str, offset: int, chunk: bytes) -> ApiResponse:
        return self._guard(
            lambda: asdict(self._uploads.write_chunk(upload_id, offset, chunk))
        )

    def finalize_upload(self, upload_id: str) -> ApiResponse:
        def action() -> dict:
            session, asset, duplicate = self._finalizer.finalize(upload_id)
            return {
                "upload": asdict(session),
                "asset": asdict(asset),
                "duplicate": duplicate,
            }

        return self._guard(action)

    def search_gallery(self, query: str = "", limit: int = 100) -> ApiResponse:
        return self._guard(
            lambda: [asdict(item) for item in self._gallery.search(query, limit)]
        )

    def create_project(self, payload: dict) -> ApiResponse:
        return self._guard(
            lambda: asdict(self._sessions.create(str(payload["name"])).project)
        )

    def get_project(self, project_id: str) -> ApiResponse:
        return self._guard(lambda: asdict(self._sessions.get(project_id).project))

    def execute_scene_command(self, project_id: str, payload: dict) -> ApiResponse:
        def action() -> dict:
            session = self._sessions.get(project_id)
            project = session.execute(scene_command_from_payload(payload))
            return asdict(project)

        return self._guard(action)

    def undo_project(self, project_id: str) -> ApiResponse:
        return self._guard(
            lambda: asdict(self._sessions.get(project_id).undo())
        )

    def redo_project(self, project_id: str) -> ApiResponse:
        return self._guard(
            lambda: asdict(self._sessions.get(project_id).redo())
        )

    def save_project(self, project_id: str) -> ApiResponse:
        return self._guard(
            lambda: asdict(self._sessions.get(project_id).save())
        )

    def restore_project_revision(
        self,
        project_id: str,
        revision: int | None = None,
    ) -> ApiResponse:
        return self._guard(
            lambda: asdict(
                self._sessions.get(project_id).restore_revision(revision)
            )
        )

    def gallery_to_studio(
        self,
        asset_id: str,
        project_id: str | None = None,
        plate_id: str | None = None,
    ) -> ApiResponse:
        def action() -> dict:
            session, handoff = self._handoffs.gallery_asset_to_project(
                asset_id,
                project_id,
                plate_id,
            )
            self._sessions.discard(session.project.id)
            return {
                "project": asdict(session.project),
                "handoff": asdict(handoff),
            }

        return self._guard(action)

    def queue_to_studio(
        self,
        queue_item_id: str,
        project_id: str | None = None,
    ) -> ApiResponse:
        def action() -> dict:
            session, handoff = self._handoffs.queue_item_to_project(
                queue_item_id,
                project_id,
            )
            self._sessions.discard(session.project.id)
            return {
                "project": asdict(session.project),
                "handoff": asdict(handoff),
            }

        return self._guard(action)

    def _guard(self, action) -> ApiResponse:
        request_id = uuid4().hex
        try:
            return ApiResponse(data=action(), request_id=request_id)
        except KeyError as error:
            return ApiResponse(
                error=ApiError("not_found", str(error)),
                request_id=request_id,
            )
        except ValueError as error:
            return ApiResponse(
                error=ApiError("validation_failed", str(error)),
                request_id=request_id,
            )
        except Exception as error:
            return ApiResponse(
                error=ApiError("internal_error", str(error)),
                request_id=request_id,
            )