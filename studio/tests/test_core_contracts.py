from core.assets import AssetFormat, AssetKind, AssetRecord
from core.profiles import ProfileKind, ProfileSelection, ProfileSource
from core.queue import QueueItemRecord, QueueItemStatus
from core.slicing import SliceJobStatus
from core.studio import Transform3D


def test_asset_contract() -> None:
    asset = AssetRecord(
        id="asset_test",
        kind=AssetKind.MODEL,
        format=AssetFormat.STL,
        digest="a" * 64,
        size_bytes=123,
        original_name="cube.stl",
        storage_key="sha256/aa/test",
        created_at="2026-07-01T00:00:00Z",
    )
    assert asset.kind == AssetKind.MODEL
    assert asset.format.value == "stl"


def test_transform_defaults() -> None:
    transform = Transform3D()
    assert transform.position == (0.0, 0.0, 0.0)
    assert transform.scale == (1.0, 1.0, 1.0)


def test_profile_enums() -> None:
    assert ProfileKind.FILAMENT.value == "filament"
    assert ProfileSource.BAMBU_CLOUD.value == "bambu_cloud"
    assert ProfileSelection().filament_profile_ids == ()


def test_job_and_queue_states() -> None:
    assert SliceJobStatus.QUEUED.value == "queued"
    item = QueueItemRecord(
        id="queue_test",
        printer_serial="SERIAL",
        status=QueueItemStatus.PLANNED,
        quantity=1,
        priority=100,
        created_at="2026-07-01T00:00:00Z",
        updated_at="2026-07-01T00:00:00Z",
        source_ref="asset_test",
        source_kind="asset",
    )
    assert item.quantity == 1
