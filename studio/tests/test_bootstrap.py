from core.bootstrap import build_runtime
from core.paths import StudioPaths


def test_runtime_bootstrap_creates_layout_and_api(tmp_path) -> None:
    paths = StudioPaths(tmp_path / "3D-Studio")
    runtime = build_runtime(paths)

    try:
        assert paths.database.exists()
        assert paths.assets.is_dir()
        assert paths.uploads.is_dir()

        response = runtime.application.create_upload(
            {
                "original_name": "cube.stl",
                "expected_size": 3,
                "source_ui": "control_center",
                "target": "gallery",
                "chunk_size": 3,
            }
        )
        assert response.error is None
        assert response.data["source_ui"] == "control_center"
        assert response.data["target"] == "gallery"
    finally:
        runtime.close()
