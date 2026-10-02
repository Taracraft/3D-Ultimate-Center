from core.geometry_commands import CenterObjectOnPlate, DuplicateObjects, PlaceObjectOnBed
from core.studio import Bounds3D, PlateRecord, ProjectRecord, SceneObject, Transform3D, Vector3


def _project() -> ProjectRecord:
    scene_object = SceneObject(
        id="object_1",
        asset_id="asset_1",
        name="Cube",
        transform=Transform3D(position=(10.0, 20.0, 5.0), scale=(2.0, 2.0, 2.0)),
        bounds=Bounds3D(
            minimum=Vector3(-5.0, -5.0, -2.0),
            maximum=Vector3(5.0, 5.0, 8.0),
        ),
    )
    return ProjectRecord(
        id="project_1",
        name="Geometry",
        revision=1,
        plates=(
            PlateRecord(
                id="plate_1",
                name="Plate 1",
                order_index=0,
                objects=(scene_object,),
                size=(256.0, 256.0),
            ),
        ),
        created_at="2026-07-01T00:00:00Z",
        updated_at="2026-07-01T00:00:00Z",
    )


def test_center_and_place_on_bed() -> None:
    centered = CenterObjectOnPlate("plate_1", "object_1").apply(_project())
    centered_object = centered.plates[0].objects[0]
    assert centered_object.transform.position == (128.0, 128.0, 5.0)

    placed = PlaceObjectOnBed("plate_1", "object_1").apply(centered)
    assert placed.plates[0].objects[0].transform.position == (128.0, 128.0, 4.0)


def test_duplicate_preserves_source_and_offsets_copy() -> None:
    duplicated = DuplicateObjects(
        "plate_1",
        ("object_1",),
        (10.0, 15.0, 0.0),
    ).apply(_project())

    original, copy = duplicated.plates[0].objects
    assert original.id == "object_1"
    assert copy.id != original.id
    assert copy.asset_id == original.asset_id
    assert copy.transform.position == (20.0, 35.0, 5.0)
    assert copy.locked is False