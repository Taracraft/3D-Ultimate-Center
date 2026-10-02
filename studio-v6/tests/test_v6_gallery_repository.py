"""Regression tests for the independent V6 gallery repository and CAD handoff."""
from __future__ import annotations

from io import BytesIO
import importlib.util
from pathlib import Path
import struct
import sys
import types
import zipfile

import pytest


package = sys.modules.setdefault(
    "ultimate_3d_studio_v6",
    types.ModuleType("ultimate_3d_studio_v6"),
)
package.__path__ = []

BASE = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
)


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        f"ultimate_3d_studio_v6.{name}",
        BASE / filename,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


geometry = load("geometry_export", "geometry_export.py")
repository_module = load("gallery_repository", "gallery_repository.py")


def minimal_3mf(with_preview: bool = True) -> bytes:
    model = b'''<?xml version="1.0" encoding="UTF-8"?>
    <model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
      <resources>
        <object id="1" type="model"><mesh>
          <vertices>
            <vertex x="0" y="0" z="0"/>
            <vertex x="10" y="0" z="0"/>
            <vertex x="0" y="10" z="0"/>
          </vertices>
          <triangles><triangle v1="0" v2="1" v3="2"/></triangles>
        </mesh></object>
      </resources>
      <build><item objectid="1"/></build>
    </model>'''
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("3D/3dmodel.model", model)
        if with_preview:
            archive.writestr("Metadata/plate_1.png", b"\x89PNG\r\n\x1a\npreview")
    return output.getvalue()


def multi_document_bambu_3mf() -> bytes:
    main = b'''<?xml version="1.0" encoding="UTF-8"?>
    <model unit="millimeter"
      xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
      xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06">
      <resources>
        <object id="2" type="model"><components>
          <component p:path="/3D/Objects/object_1.model" objectid="1" transform="1 0 0 0 1 0 0 0 1 5 7 9"/>
        </components></object>
      </resources>
      <build><item objectid="2" transform="1 0 0 0 1 0 0 0 1 100 120 0"/></build>
    </model>'''
    object_model = b'''<?xml version="1.0" encoding="UTF-8"?>
    <model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
      <resources>
        <object id="1" type="model"><mesh>
          <vertices>
            <vertex x="0" y="0" z="0"/>
            <vertex x="10" y="0" z="0"/>
            <vertex x="0" y="10" z="0"/>
          </vertices>
          <triangles><triangle v1="0" v2="1" v3="2"/></triangles>
        </mesh></object>
      </resources>
    </model>'''
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("3D/3dmodel.model", main)
        archive.writestr("3D/Objects/object_1.model", object_model)
    return output.getvalue()


def test_geometry_export_returns_valid_binary_stl() -> None:
    payload = geometry.export_binary_stl(minimal_3mf(False), "Test")
    assert len(payload) == 84 + 50
    assert struct.unpack_from("<I", payload, 80)[0] == 1
    normal_and_vertices = struct.unpack_from("<12fH", payload, 84)
    assert normal_and_vertices[2] == pytest.approx(1.0)
    assert normal_and_vertices[3:6] == pytest.approx((0.0, 0.0, 0.0))
    assert normal_and_vertices[6:9] == pytest.approx((10.0, 0.0, 0.0))
    assert normal_and_vertices[9:12] == pytest.approx((0.0, 10.0, 0.0))


def test_geometry_export_resolves_external_component_documents_and_transforms() -> None:
    payload = geometry.export_binary_stl(multi_document_bambu_3mf(), "Bambu Multi Document")
    assert struct.unpack_from("<I", payload, 80)[0] == 1
    values = struct.unpack_from("<12fH", payload, 84)
    assert values[3:6] == pytest.approx((105.0, 127.0, 9.0))
    assert values[6:9] == pytest.approx((115.0, 127.0, 9.0))
    assert values[9:12] == pytest.approx((105.0, 137.0, 9.0))


def test_repository_preserves_folder_structure_and_supports_cad_handoff(tmp_path: Path) -> None:
    repository = repository_module.V6GalleryRepository(tmp_path / "archive")
    folder = repository.create_folder("", "Projekte")
    item = repository.upload("demo.3mf", minimal_3mf(), "Projekte")

    assert folder["path"] == "Projekte"
    assert item["path"] == "Projekte/demo.3mf"
    listing = repository.list_folder("Projekte")
    assert listing["folder"] == "Projekte"
    assert listing["parent"] == ""
    assert [entry["name"] for entry in listing["items"]] == ["demo.3mf"]
    assert listing["stats"] == {
        "files": 1,
        "folders": 1,
        "bytes": len(minimal_3mf()),
    }

    preview = repository.preview(item["asset_id"])
    assert preview is not None
    assert preview[0].startswith(b"\x89PNG")
    assert preview[1] == "image/png"

    stl, filename = repository.model_stl(item["asset_id"])
    assert filename == "demo.stl"
    assert struct.unpack_from("<I", stl, 80)[0] == 1


def test_repository_cad_handoff_supports_realistic_multi_document_3mf(tmp_path: Path) -> None:
    repository = repository_module.V6GalleryRepository(tmp_path / "archive")
    item = repository.upload("bambu.3mf", multi_document_bambu_3mf())
    stl, filename = repository.model_stl(item["asset_id"])
    assert filename == "bambu.stl"
    assert struct.unpack_from("<I", stl, 80)[0] == 1


def test_repository_rename_move_delete_and_recursive_search(tmp_path: Path) -> None:
    repository = repository_module.V6GalleryRepository(tmp_path / "archive")
    repository.create_folder("", "A")
    repository.create_folder("", "B")
    repository.upload("first.3mf", minimal_3mf(False), "A")

    renamed = repository.rename("A/first.3mf", "renamed.3mf")
    assert renamed["path"] == "A/renamed.3mf"
    moved = repository.move("A/renamed.3mf", "B")
    assert moved["path"] == "B/renamed.3mf"

    search = repository.list_folder("", "renamed", True)
    assert [item["path"] for item in search["items"] if item["kind"] == "model"] == [
        "B/renamed.3mf"
    ]

    repository.delete("B/renamed.3mf")
    assert repository.stats()["files"] == 0
    repository.delete("A")
    assert {item["path"] for item in repository.tree()} == {"", "B"}


def test_zip_export_import_preserves_models_folders_and_sidecar_previews(tmp_path: Path) -> None:
    source = repository_module.V6GalleryRepository(tmp_path / "source")
    source.create_folder("", "Ordner")
    source.upload("part.3mf", minimal_3mf(False), "Ordner")
    (source.root / "Ordner" / "part.png").write_bytes(b"preview-sidecar")

    exported = source.export_zip()
    target = repository_module.V6GalleryRepository(tmp_path / "target")
    inspection = target.inspect_zip(exported)

    assert inspection["files"] == 2
    assert inspection["folders"] == 1
    assert inspection["conflicts"] == []

    result = target.import_zip(exported)
    assert result["verification"] == "ok"
    assert result["imported"] == 2
    assert (target.root / "Ordner" / "part.3mf").is_file()
    assert (target.root / "Ordner" / "part.png").read_bytes() == b"preview-sidecar"
    assert target.stats()["files"] == 1


def test_zip_import_reports_conflicts_and_requires_explicit_overwrite(tmp_path: Path) -> None:
    source = repository_module.V6GalleryRepository(tmp_path / "source")
    source_payload = minimal_3mf(False)
    source.upload("same.3mf", source_payload)
    exported = source.export_zip()

    target = repository_module.V6GalleryRepository(tmp_path / "target")
    target.upload("same.3mf", b"existing")
    inspection = target.inspect_zip(exported)
    assert inspection["conflicts"] == ["same.3mf"]

    with pytest.raises(FileExistsError):
        target.import_zip(exported, overwrite=False)

    result = target.import_zip(exported, overwrite=True)
    assert result["overwritten"] == 1
    assert target.download("same.3mf")[0] == source_payload


def test_unsafe_paths_and_unsupported_uploads_are_rejected(tmp_path: Path) -> None:
    repository = repository_module.V6GalleryRepository(tmp_path / "archive")
    with pytest.raises(ValueError):
        repository.create_folder("../outside", "bad")
    with pytest.raises(ValueError):
        repository.upload("notes.txt", b"text")
    with pytest.raises(ValueError):
        repository.path_from_asset_id("invalid")
