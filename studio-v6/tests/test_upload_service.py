import sqlite3

from core.database import initialize
from core.sqlite_uploads import SqliteUploadRepository
from core.upload_service import UploadService
from core.uploads import UploadStatus


def test_resumable_upload(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    initialize(database)

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    repository = SqliteUploadRepository(connection)
    service = UploadService(repository, tmp_path / "runtime")

    session = service.create(
        original_name="cube.stl",
        expected_size=6,
        source_ui="studio",
        target="gallery",
        chunk_size=3,
    )
    first = service.write_chunk(session.id, 0, b"abc")
    second = service.write_chunk(session.id, 3, b"def")
    verifying = service.mark_verifying(session.id)

    assert first.progress == 50.0
    assert second.progress == 100.0
    assert verifying.status == UploadStatus.VERIFYING
    assert service.partial_path(session.id).read_bytes() == b"abcdef"


def test_rejects_wrong_offset(tmp_path) -> None:
    database = tmp_path / "studio.sqlite3"
    initialize(database)

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    repository = SqliteUploadRepository(connection)
    service = UploadService(repository, tmp_path / "runtime")

    session = service.create(
        original_name="cube.stl",
        expected_size=3,
        source_ui="control_center",
        target="studio",
        chunk_size=3,
    )

    try:
        service.write_chunk(session.id, 1, b"abc")
    except ValueError as error:
        assert "expected 0" in str(error)
    else:
        raise AssertionError("wrong upload offset was accepted")