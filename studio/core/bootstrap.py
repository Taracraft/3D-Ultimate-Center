"""Build one complete Studio application instance."""

from __future__ import annotations

from dataclasses import dataclass

from api.application import V1Application

from .asset_service import AssetService
from .database import connect, initialize
from .gallery_service import GalleryService
from .handoff import HandoffService
from .paths import StudioPaths
from .project_service import ProjectService
from .session_manager import ProjectSessionManager
from .sqlite_assets import SqliteAssetRepository
from .sqlite_gallery import SqliteGalleryRepository
from .sqlite_projects import SqliteProjectRepository
from .sqlite_queue import SqliteQueueRepository
from .sqlite_uploads import SqliteUploadRepository
from .upload_finalizer import UploadFinalizer
from .upload_service import UploadService


@dataclass(slots=True)
class StudioRuntime:
    paths: StudioPaths
    connection: object
    application: V1Application
    sessions: ProjectSessionManager

    def close(self) -> None:
        self.sessions.flush_all()
        self.connection.close()


def build_runtime(paths: StudioPaths) -> StudioRuntime:
    paths.create()
    initialize(paths.database)
    connection = connect(paths.database)

    asset_repository = SqliteAssetRepository(connection)
    upload_repository = SqliteUploadRepository(connection)
    gallery_repository = SqliteGalleryRepository(connection)
    project_repository = SqliteProjectRepository(connection)
    queue_repository = SqliteQueueRepository(connection)

    asset_service = AssetService(asset_repository, paths.assets)
    upload_service = UploadService(upload_repository, paths.runtime)
    gallery_service = GalleryService(gallery_repository)
    project_service = ProjectService(project_repository)
    sessions = ProjectSessionManager(project_service)
    handoff_service = HandoffService(
        connection,
        asset_repository,
        queue_repository,
        project_service,
    )
    finalizer = UploadFinalizer(upload_service, asset_service)

    application = V1Application(
        uploads=upload_service,
        finalizer=finalizer,
        gallery=gallery_service,
        projects=project_service,
        sessions=sessions,
        handoffs=handoff_service,
    )
    return StudioRuntime(paths, connection, application, sessions)
