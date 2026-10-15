import hashlib
import sqlite3

from core.asset_service import AssetService
from core.database import initialize
from core.sqlite_assets import SqliteAssetRepository
from core.sqlite_uploads import SqliteUploadRepository
from core.upload_finalizer import UploadFinalizer
from core.upload_service import UploadService
from core.uploads import UploadStatus


def _services(tmp_path):
    database = tmp_path / "studio.sqlite3"
    initialize(database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    asset_repository = SqliteAssetRepository(connection)
    upload_repository = SqliteUploadRepository(connection)
    asset_service = AssetService(asset_repository, tmp_path / "data" / "assets")
    upload_service = UploadService(upload_repository, tmp_path / "runtime")
    finalizer = UploadFinalizer(upload_service, asset_service)
    return connection, asset_repository, upload_service, finalizer


def test_upload_becomes_content_addressed_asset(tmp_path) -> None:
    _, assets, uploads, finalizer = _services(tmp_path)
    payload = b"solid cube\nendsolid cube\n"
    digest = hashlib.sha256(payload).hexdigest()

    session = uploads.create(
        original_name="cube.stl",
        expected_size=len(payload),
        source_ui="gallery",
        target="studio",
        chunk_size=len(payload),
        expected_digest=digest,
    )
    uploads.write_chunk(session.id, 0, payload)
    completed, asset, duplicate = finalizer.finalize(session.id)

    assert completed.status == UploadStatus.COMPLETED
    assert completed.asset_id == asset.id
    assert duplicate is False
    assert assets.find_by_digest(digest) == asset


def test_duplicate_reuses_asset_and_removes_partial_file(tmp_path) -> None:
    _, _, uploads, finalizer = _services(tmp_path)
    payload = b"solid cube\nendsolid cube\n"

    first = uploads.create(
        original_name="cube.stl",
        expected_size=len(payload),
        source_ui="control_center",
        target="gallery",
        chunk_size=len(payload),
    )
    uploads.write_chunk(first.id, 0, payload)
    _, first_asset, _ = finalizer.finalize(first.id)

    second = uploads.create(
        original_name="cube-copy.stl",
        expected_size=len(payload),
        source_ui="studio",
        target="queue",
        chunk_size=len(payload),
    )
    uploads.write_chunk(second.id, 0, payload)
    completed, second_asset, duplicate = finalizer.finalize(second.id)

    assert duplicate is True
    assert second_asset.id == first_asset.id
    assert completed.asset_id == first_asset.id
    assert not uploads.partial_path(second.id).exists()
