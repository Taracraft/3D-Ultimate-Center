"""Regression tests for safe multi-plate 3MF inspection."""

from __future__ import annotations

from io import BytesIO
import importlib.util
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
INSPECTOR_PATH = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
    / "three_mf_inspector.py"
)


def _load_inspector_module():
    spec = importlib.util.spec_from_file_location(
        "v6_three_mf_inspector",
        INSPECTOR_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _archive(files: dict[str, bytes | str]) -> bytes:
    memory = BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(
                name,
                content.encode("utf-8") if isinstance(content, str) else content,
            )
    return memory.getvalue()


def test_stl_is_reported_as_single_display_plate_one() -> None:
    inspector = _load_inspector_module()

    result = inspector.inspect_model(
        "model.stl",
        b"solid model\nendsolid model\n",
    )

    assert result["format"] == "stl"
    assert result["plate_count"] == 1
    assert result["plates"] == [
        {
            "plate_index": 0,
            "display_number": 1,
            "name": "Druckplatte 1",
            "object_count": None,
            "source": "3mf",
        }
    ]


def test_multi_plate_json_metadata_uses_one_based_display_numbers() -> None:
    inspector = _load_inspector_module()
    model = _archive({
        "[Content_Types].xml": "<Types/>",
        "3D/3dmodel.model": "<model/>",
        "Metadata/plate_1.json": json.dumps({
            "plate_index": 1,
            "plate_name": "Frontteile",
            "objects": [{"id": 1}, {"id": 2}],
        }),
        "Metadata/plate_2.json": json.dumps({
            "plate_index": 2,
            "plate_name": "Rückteile",
            "object_count": 3,
        }),
    })

    result = inspector.inspect_model("project.3mf", model)

    assert result["format"] == "3mf"
    assert result["plate_count"] == 2
    assert [plate["plate_index"] for plate in result["plates"]] == [0, 1]
    assert [plate["display_number"] for plate in result["plates"]] == [1, 2]
    assert [plate["name"] for plate in result["plates"]] == [
        "Frontteile",
        "Rückteile",
    ]
    assert [plate["object_count"] for plate in result["plates"]] == [2, 3]


def test_unsafe_archive_path_is_rejected() -> None:
    inspector = _load_inspector_module()
    model = _archive({"../plate_1.json": "{}"})

    try:
        inspector.inspect_model("unsafe.3mf", model)
    except ValueError as error:
        assert "unsicheren Pfad" in str(error)
    else:
        raise AssertionError("Unsafe 3MF path was accepted")
