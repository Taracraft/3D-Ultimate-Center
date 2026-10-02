from core.makerworld import (
    MakerWorldCreator,
    MakerWorldDestination,
    MakerWorldModel,
    MakerWorldPrintProfile,
)
from core.makerworld_profiles import profile_snapshot, resolve_print_profile


def _model() -> MakerWorldModel:
    return MakerWorldModel(
        id="mw_model",
        title="Model",
        model_url="https://makerworld.example/model",
        description="Test",
        creator=MakerWorldCreator(id="creator", name="Creator"),
        license_name="CC BY",
        license_url=None,
        thumbnail_url=None,
        downloads=1,
        likes=1,
        tags=("test",),
        print_profiles=(
            MakerWorldPrintProfile(
                id="profile_04",
                name="0.20 Standard",
                printer_model="X1 Carbon",
                nozzle_diameter=0.4,
                plate_count=1,
                filament_count=1,
            ),
        ),
    )


def test_selected_profile_is_resolved_and_snapshotted() -> None:
    profile = resolve_print_profile(
        _model(),
        "profile_04",
        MakerWorldDestination.STUDIO,
    )
    assert profile is not None
    assert profile.name == "0.20 Standard"
    assert profile_snapshot(profile)["nozzle_diameter"] == 0.4


def test_slicer_requires_profile_when_profiles_exist() -> None:
    try:
        resolve_print_profile(_model(), None, MakerWorldDestination.SLICER)
    except ValueError as error:
        assert "must be selected" in str(error)
    else:
        raise AssertionError("Slicer import accepted no MakerWorld print profile")


def test_gallery_allows_model_files_only() -> None:
    assert resolve_print_profile(
        _model(),
        None,
        MakerWorldDestination.GALLERY,
    ) is None