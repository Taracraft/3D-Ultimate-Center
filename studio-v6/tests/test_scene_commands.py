from core.history import History
from core.scene_commands import AddObject, AddPlate, RemovePlate, SetObjectColor, SetObjectTransform
from core.studio import PlateRecord, ProjectRecord, SceneObject, Transform3D


def _project() -> ProjectRecord:
    return ProjectRecord(
        id="project_test",
        name="Test",
        revision=1,
        plates=(PlateRecord(id="plate_1", name="Plate 1", order_index=0),),
        created_at="2026-07-01T00:00:00Z",
        updated_at="2026-07-01T00:00:00Z",
    )


def test_multiple_plates_and_minimum_one_plate() -> None:
    project = _project()
    second = PlateRecord(id="plate_2", name="Plate 2", order_index=1)
    project = AddPlate(second).apply(project)
    assert [plate.id for plate in project.plates] == ["plate_1", "plate_2"]

    project = RemovePlate("plate_2").apply(project)
    assert [plate.id for plate in project.plates] == ["plate_1"]

    try:
        RemovePlate("plate_1").apply(project)
    except ValueError as error:
        assert "at least one plate" in str(error)
    else:
        raise AssertionError("last plate was removed")


def test_object_transform_and_color_are_immutable() -> None:
    project = _project()
    scene_object = SceneObject(id="object_1", asset_id="asset_1", name="Cube")
    with_object = AddObject("plate_1", scene_object).apply(project)
    transformed = SetObjectTransform(
        "plate_1",
        "object_1",
        Transform3D(position=(10.0, 20.0, 0.0)),
    ).apply(with_object)
    colored = SetObjectColor("plate_1", "object_1", "#ff6600").apply(transformed)

    assert project.plates[0].objects == ()
    assert with_object.plates[0].objects[0].transform.position == (0.0, 0.0, 0.0)
    assert transformed.plates[0].objects[0].transform.position == (10.0, 20.0, 0.0)
    assert colored.plates[0].objects[0].color == "#ff6600"


def test_history_undo_and_redo_are_deterministic() -> None:
    original = _project()
    changed = AddPlate(
        PlateRecord(id="plate_2", name="Plate 2", order_index=1)
    ).apply(original)
    history = History.create(original)
    history.push(changed)

    assert history.undo() == original
    assert history.redo() == changed