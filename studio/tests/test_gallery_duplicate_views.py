"""Tests actual duplicate HTTP view with bounded Home Assistant doubles."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

from aiohttp import web
import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio"


@pytest.fixture
def view_module(monkeypatch, tmp_path):
    package = "duplicate_view_test_package"
    root = ModuleType(package)
    root.__path__ = [str(COMPONENT)]
    monkeypatch.setitem(sys.modules, package, root)
    const = ModuleType(package + ".const")
    const.API_BASE, const.DOMAIN = "/api/ultimate_3d_studio/v1", "ultimate_3d_studio"
    monkeypatch.setitem(sys.modules, const.__name__, const)
    module_name = package + ".gallery_duplicate_scan"
    spec = importlib.util.spec_from_file_location(module_name, COMPONENT / "gallery_duplicate_scan.py")
    scan = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, scan)
    spec.loader.exec_module(scan)
    http = ModuleType("homeassistant.components.http")
    http.HomeAssistantView = type("HomeAssistantView", (), {})
    for name in ["homeassistant", "homeassistant.components"]:
        if name not in sys.modules:
            m = ModuleType(name)
            m.__path__ = []
            monkeypatch.setitem(sys.modules, name, m)
    monkeypatch.setitem(sys.modules, "homeassistant.components.http", http)
    repository = ModuleType(package + ".gallery_management_views_v2")
    repository._DATA_REPOSITORY = "gallery_management_repository_v2"
    repository._error = lambda status, code, message: web.json_response({"data": None, "error": {"code": code, "message": message}}, status=status)
    repository._success = lambda data, **meta: web.json_response({"data": data, "error": None, "meta": meta})
    monkeypatch.setitem(sys.modules, repository.__name__, repository)
    spec = importlib.util.spec_from_file_location(package + ".gallery_duplicate_views", COMPONENT / "gallery_duplicate_views.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


class Hass:
    def __init__(self, root=None):
        self.data = {}
        self.config = SimpleNamespace(path=lambda *parts: str(root or Path("/not-present-in-test")))
        self.calls = []
        self.registered = []
        self.http = SimpleNamespace(register_view=self.registered.append)

    async def async_add_executor_job(self, job):
        self.calls.append(job)
        return job()


def request(hass, folder=""):
    return SimpleNamespace(app={"hass": hass}, query={"folder": folder})


def test_view_is_authenticated_read_only_and_registration_idempotent(view_module):
    hass = Hass()
    view_module.async_register_gallery_duplicate_views(hass)
    view_module.async_register_gallery_duplicate_views(hass)
    assert len(hass.registered) == 1
    view = hass.registered[0]
    assert view.requires_auth is True
    assert view.url.endswith("/gallery/duplicates")
    assert not hasattr(view, "post") and not hasattr(view, "delete")


def test_view_calls_real_scanner_with_the_canonical_repository_root(view_module, tmp_path):
    (tmp_path / "a.stl").write_bytes(b"model")
    (tmp_path / "b.stl").write_bytes(b"model")
    async def run():
        hass = Hass(tmp_path)
        response = await view_module.GalleryDuplicatesView().get(request(hass))
        assert response.status == 200
        payload = json.loads(response.text)
        assert payload["data"]["duplicate_groups"] == 1
        assert payload["data"]["read_only"] is True
        assert response.headers["Cache-Control"] == "no-store"
        assert len(hass.calls) == 1
        await asyncio.sleep(0)
        assert view_module._DATA_SCAN not in hass.data[view_module.DOMAIN]
    asyncio.run(run())


@pytest.mark.parametrize("code,status", [("invalid_folder",400), ("unsafe_folder",400),
    ("folder_not_found",404), ("library_changed",409), ("scan_byte_limit",422),
    ("scan_time_limit",422), ("scan_entry_limit",422), ("scan_io_error",422)])
def test_errors_never_masquerade_as_an_empty_success(view_module, monkeypatch, code, status):
    def scan(*args, **kwargs): raise view_module.DuplicateScanError(code)
    monkeypatch.setattr(view_module, "scan_gallery_duplicates", scan)
    async def run():
        response = await view_module.GalleryDuplicatesView().get(request(Hass()))
        assert response.status == status
        data = json.loads(response.text)
        assert data["data"] is None and data["error"]["code"] == code
        assert response.headers["Cache-Control"] == "no-store"
    asyncio.run(run())


def test_unexpected_errors_do_not_expose_private_paths(view_module, monkeypatch):
    def scan(*args, **kwargs): raise RuntimeError("SECRET private/root/file")
    monkeypatch.setattr(view_module, "scan_gallery_duplicates", scan)
    response = asyncio.run(view_module.GalleryDuplicatesView().get(request(Hass())))
    assert response.status == 500 and "SECRET" not in response.text


def test_busy_scan_is_not_started_twice(view_module):
    async def run():
        hass = Hass()
        blocker = asyncio.get_running_loop().create_future()
        hass.data[view_module.DOMAIN] = {view_module._DATA_SCAN: blocker}
        response = await view_module.GalleryDuplicatesView().get(request(hass))
        assert response.status == 409 and hass.calls == []
        assert json.loads(response.text)["error"]["code"] == "gallery_duplicate_scan_busy"
        blocker.cancel()
    asyncio.run(run())


def test_request_cancellation_keeps_guard_until_executor_finishes(view_module):
    async def run():
        hass = Hass()
        started, finish = asyncio.Event(), asyncio.Event()
        jobs = []
        async def executor(job):
            jobs.append(job)
            started.set()
            await finish.wait()
            return {"duplicate_groups":0}
        hass.async_add_executor_job = executor
        first = asyncio.create_task(view_module.GalleryDuplicatesView().get(request(hass)))
        await started.wait()
        first.cancel()
        with pytest.raises(asyncio.CancelledError): await first
        assert jobs[0].keywords["cancel"].is_set()
        second = await view_module.GalleryDuplicatesView().get(request(hass))
        assert second.status == 409 and len(jobs) == 1
        active = hass.data[view_module.DOMAIN][view_module._DATA_SCAN]
        assert not active.done()
        finish.set()
        await active
        await asyncio.sleep(0)
        assert view_module._DATA_SCAN not in hass.data[view_module.DOMAIN]
    asyncio.run(run())


def test_old_task_cleanup_does_not_remove_a_new_task(view_module):
    async def run():
        old = asyncio.get_running_loop().create_future()
        new = asyncio.get_running_loop().create_future()
        old.set_result(None)
        data = {view_module._DATA_SCAN:new}
        view_module._consume_task(data, old)
        assert data[view_module._DATA_SCAN] is new
        new.cancel()
    asyncio.run(run())


def test_missing_canonical_library_is_not_created_by_the_view(view_module, tmp_path):
    root = tmp_path / "absent"
    hass = Hass(root)
    response = asyncio.run(view_module.GalleryDuplicatesView().get(request(hass)))
    assert response.status == 404 and not root.exists()


def test_cached_repository_root_remains_authoritative(view_module, tmp_path):
    selected = tmp_path / "selected"
    selected.mkdir()
    (selected / "a.stl").write_bytes(b"same")
    (selected / "b.stl").write_bytes(b"same")
    hass = Hass(tmp_path / "do-not-create")
    hass.data[view_module.DOMAIN] = {view_module._DATA_REPOSITORY: SimpleNamespace(root=selected)}
    response = asyncio.run(view_module.GalleryDuplicatesView().get(request(hass)))
    assert json.loads(response.text)["data"]["duplicate_groups"] == 1
    assert not (tmp_path / "do-not-create").exists()
