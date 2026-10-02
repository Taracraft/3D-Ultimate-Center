import sqlite3

from core.asset_service import AssetService
from core.database import initialize
from core.event_bus import EventBus
from core.gallery_service import GalleryService
from core.handoff import HandoffService
from core.makerworld import MakerWorldDestination
from core.makerworld_import_service import MakerWorldImportRequest, MakerWorldImportService
from core.makerworld_repository import MakerWorldRepository
from core.profiles import ProfileSelection
from core.project_service import ProjectService
from core.slice_service import SliceService
from core.sqlite_assets import SqliteAssetRepository
from core.sqlite_gallery import SqliteGalleryRepository
from core.sqlite_projects import SqliteProjectRepository
from core.sqlite_queue import SqliteQueueRepository
from core.sqlite_slicing import SqliteSliceArtifactRepository, SqliteSliceJobRepository

from tests.fakes import FakeMakerWorldProvider, FakeSlicerProvider


async def test_makerworld_to_gallery_to_studio_to_slicer(tmp_path) -> None:
    source = tmp_path / "makerworld-test.stl"
    source.write_text(
        """solid test
facet normal 0 0 1
 outer loop
  vertex 0 0 0
  vertex 10 0 0
  vertex 0 10 0
 endloop
endfacet
endsolid test
""",
        encoding="utf-8",
    )

    database = tmp_path / "studio.sqlite3"
    initialize(database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    assets_repository = SqliteAssetRepository(connection)
    assets = AssetService(assets_repository, tmp_path / "assets")
    gallery = GalleryService(SqliteGalleryRepository(connection))
    projects = ProjectService(SqliteProjectRepository(connection))
    queue = SqliteQueueRepository(connection)
    handoffs = HandoffService(connection, assets_repository, queue, projects)

    slicing = SliceService(
        SqliteSliceJobRepository(connection),
        SqliteSliceArtifactRepository(connection),
        EventBus(),
    )
    slicing.register_provider("fake_slicer", FakeSlicerProvider())

    makerworld_repository = MakerWorldRepository(connection)
    service = MakerWorldImportService(
        provider=FakeMakerWorldProvider(source),
        repository=makerworld_repository,
        assets=assets,
        gallery=gallery,
        handoffs=handoffs,
        slicing=slicing,
    )

    imported = await service.import_model(
        MakerWorldImportRequest(
            model_id_or_url="mw_test_model",
            destination=MakerWorldDestination.GALLERY,
            profile_id="mw_profile_04",
            license_acknowledged=True,
        )
    )

    asset_id = imported["asset"]["id"]
    gallery_item = gallery.search("MakerWorld Test Model")[0]
    provenance = makerworld_repository.get_asset_info(asset_id)

    assert gallery_item.asset_id == asset_id
    assert provenance is not None
    assert provenance["model"]["creator"]["name"] == "Test Creator"
    assert provenance["selected_profile_id"] == "mw_profile_04"
    assert provenance["selected_profile"]["nozzle_diameter"] == 0.4

    session, handoff = handoffs.gallery_asset_to_project(asset_id)
    project = session.project
    plate = project.plates[0]

    assert handoff.source_kind == "gallery_asset"
    assert plate.objects[0].asset_id == asset_id

    job = slicing.create_job(
        project_id=project.id,
        plate_id=plate.id,
        provider_id="fake_slicer",
        profile_selection=ProfileSelection(
            printer_profile_id="printer_x1c",
            nozzle_profile_id="nozzle_04",
            process_profile_id="process_020_standard",
            filament_profile_ids=("filament_pla",),
        ),
    )
    completed = await slicing.run(job.id)

    assert completed.status.value == "succeeded"
    assert completed.progress == 100.0
    assert slicing.get(job.id).profile_selection.nozzle_profile_id == "nozzle_04"