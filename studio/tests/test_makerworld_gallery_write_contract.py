"""MakerWorld gallery writes: explicit overwrite and competing imports, isolated files."""
from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import sys
from threading import Barrier
from types import ModuleType, SimpleNamespace
import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio"

@pytest.fixture
def app(monkeypatch, tmp_path):
    package = "studio_makerworld_gallery_write_tests"
    root = ModuleType(package)
    root.__path__ = [str(COMPONENT)]
    monkeypatch.setitem(sys.modules, package, root)
    def stub(suffix, **values):
        name = suffix if suffix.startswith("homeassistant") else package + "." + suffix
        module = ModuleType(name)
        module.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, module)
        return module
    stub("homeassistant.components.http", HomeAssistantView=object)
    stub("homeassistant.core", HomeAssistant=object)
    stub("const", API_BASE="/api/ultimate_3d_studio/v1", DOMAIN="ultimate_3d_studio", VERSION="test")
    stub("geometry_export", export_binary_stl=lambda *args: b"")
    stub("makerworld_detail", async_load_detail=None)
    stub("makerworld_download", async_download_instance=None)
    stub("makerworld_runtime", MakerWorldError=type("MakerWorldError", (Exception,), {}), get_makerworld_runtime=None)
    stub("rich_text", readable_rich_text=lambda value, *args: value, safe_rich_html=lambda value: value)
    def load(suffix):
        name = package + "." + suffix
        spec = importlib.util.spec_from_file_location(name, COMPONENT / (suffix + ".py"))
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module
    gallery = load("gallery_repository")
    views = load("makerworld_views")
    repository = gallery.StudioGalleryRepository(tmp_path)
    downloads = []
    async def download(_request, instance, body):
        downloads.append((instance, body.copy()))
        return b"selected-profile-archive"
    monkeypatch.setattr(views, "_download_payload_from_body", download)
    monkeypatch.setattr(views, "_gallery", lambda _hass: repository)
    async def executor(function, *args):
        return function(*args)
    hass = SimpleNamespace(async_add_executor_job=executor)
    class Request(dict):
        def __init__(self, body, admin=True):
            super().__init__(hass_user=SimpleNamespace(is_admin=admin))
            self.app = {"hass": hass}
            self.body = body
        async def json(self):
            return self.body
    def post(body, admin=True):
        return asyncio.run(views.MakerWorldInstanceView().post(Request(body, admin), "profile-a", "save"))
    return SimpleNamespace(gallery=gallery, views=views, repository=repository, downloads=downloads, post=post, path=tmp_path)

@pytest.mark.parametrize("overwrite", ["false", "true", 0, 1, None, [], {}, ""])
def test_invalid_overwrite_is_rejected_before_download_or_write(app, overwrite):
    target = app.path / "existing.3mf"
    target.write_bytes(b"original-project")
    response = app.post({"confirmed": True, "filename": target.name, "overwrite": overwrite})
    assert response.status == 400
    assert json.loads(response.body)["error"]["code"] == "invalid_makerworld_transfer"
    assert app.downloads == []
    assert target.read_bytes() == b"original-project"

@pytest.mark.parametrize("explicit", [False, True])
def test_false_or_missing_overwrite_preserves_existing_file(app, explicit):
    target = app.path / "existing.3mf"
    target.write_bytes(b"original-project")
    body = {"confirmed": True, "filename": target.name}
    if explicit:
        body["overwrite"] = False
    response = app.post(body)
    assert response.status == 409
    assert target.read_bytes() == b"original-project"

def test_boolean_true_explicitly_replaces_existing_file(app):
    target = app.path / "existing.3mf"
    target.write_bytes(b"original-project")
    response = app.post({"confirmed": True, "filename": target.name, "overwrite": True})
    assert response.status == 200
    assert target.read_bytes() == b"selected-profile-archive"
    assert json.loads(response.body)["data"]["name"] == target.name

def test_new_import_retains_archive_bytes_and_asset_identity(app):
    response = app.post({"confirmed": True, "filename": "new.3mf"})
    assert response.status == 200
    assert (app.path / "new.3mf").read_bytes() == b"selected-profile-archive"
    data = json.loads(response.body)["data"]
    assert app.repository.path_from_asset_id(data["asset_id"]) == "new.3mf"

@pytest.mark.parametrize("body,admin,status", [
    ({"confirmed": True}, False, 403),
    ({"confirmed": False}, True, 409),
    ({"confirmed": "true"}, True, 409),
])
def test_permission_and_confirmation_remain_required(app, body, admin, status):
    assert app.post(body, admin).status == status
    assert app.downloads == []
    assert list(app.path.iterdir()) == []

def test_stale_absence_check_cannot_overwrite_another_import(app, monkeypatch):
    # A competitor may create the name after an absence check. The filesystem
    # must decide exclusive creation, even if an earlier stat reports absent.
    target = app.path / "competing.3mf"
    target.write_bytes(b"competitor-archive")
    original_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda path: False if path == target else original_exists(path))
    with pytest.raises(FileExistsError):
        app.repository.upload(target.name, b"new-import", overwrite=False)
    assert target.read_bytes() == b"competitor-archive"

def test_simultaneous_imports_produce_one_winner_without_byte_mixing(app):
    barrier = Barrier(16)
    payloads = [bytes([index + 1]) * 65536 for index in range(16)]
    def attempt(payload):
        barrier.wait(timeout=10)
        try:
            app.repository.upload("shared.3mf", payload, overwrite=False)
        except FileExistsError:
            return False
        return True
    with ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(pool.map(attempt, payloads))
    assert sum(outcomes) == 1
    assert (app.path / "shared.3mf").read_bytes() == payloads[outcomes.index(True)]
