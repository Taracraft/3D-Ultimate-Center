"""MakerWorld saves use the Studio gallery regardless of first caller.

Only synthetic downloads and temporary files; no HA runtime or external I/O.
"""
from __future__ import annotations
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

COMPONENT = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio"
DOMAIN = "ultimate_3d_studio"

class MakerWorldGalleryStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.legacy = self.root / "printer_control_center" / "archive"
        self.legacy.mkdir(parents=True)
        self.sentinel = self.legacy / "existing.3mf"
        self.sentinel.write_bytes(b"legacy-original")
        self.before = (self.sentinel.read_bytes(), self.sentinel.stat().st_mtime_ns)
        self.package = "studio_makerworld_storage_test"
        package = ModuleType(self.package)
        package.__path__ = [str(COMPONENT)]
        modules = {self.package: package}
        def stub(name, **values):
            name = name if name.startswith("homeassistant") else self.package + "." + name
            mod = ModuleType(name)
            mod.__dict__.update(values)
            modules[name] = mod
        stub("homeassistant.components.http", HomeAssistantView=object)
        stub("homeassistant.core", HomeAssistant=object)
        stub("const", API_BASE="/api/ultimate_3d_studio/v1", DOMAIN=DOMAIN, VERSION="fixture")
        stub("geometry_export", export_binary_stl=lambda *args: b"")
        stub("makerworld_detail", async_load_detail=None)
        stub("makerworld_download", async_download_instance=None)
        stub("makerworld_runtime", MakerWorldError=type("MakerWorldError", (Exception,), {}), get_makerworld_runtime=None)
        stub("rich_text", readable_rich_text=lambda value, *args: value, safe_rich_html=lambda value: value)
        self.module_patch = patch.dict(sys.modules, modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        def load(suffix):
            name = self.package + "." + suffix
            spec = importlib.util.spec_from_file_location(name, COMPONENT / (suffix + ".py"))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module
        self.gallery = load("gallery_repository")
        self.views = load("makerworld_views")
        self.management = load("gallery_management_views")
        self.downloads = []
        async def download(request, instance, body):
            self.downloads.append((instance, body.copy()))
            return b"synthetic-selected-profile"
        self.views._download_payload_from_body = download
        async def executor(function, *args):
            return function(*args)
        self.hass = SimpleNamespace(data={}, config=SimpleNamespace(path=lambda *parts: str(self.root.joinpath(*parts))), async_add_executor_job=executor)

    def post(self, body, admin=True):
        hass = self.hass
        class Request(dict):
            def __init__(self):
                super().__init__(hass_user=SimpleNamespace(is_admin=admin))
                self.app = {"hass": hass}
                self.query = {}
            async def json(self):
                return body
        return asyncio.run(self.views.MakerWorldInstanceView().post(Request(), "instance-a", "save"))

    def assert_legacy_intact(self):
        self.assertEqual((self.sentinel.read_bytes(), self.sentinel.stat().st_mtime_ns), self.before)
        self.assertEqual(list(self.legacy.iterdir()), [self.sentinel])

    def test_makerworld_first_shares_only_studio_repository(self):
        first = self.views._gallery(self.hass)
        second = self.management._repository(self.hass)
        self.assertIs(first, second)
        self.assertEqual(first.root, self.root / DOMAIN / "gallery")
        self.assert_legacy_intact()

    def test_management_first_shares_only_studio_repository(self):
        first = self.management._repository(self.hass)
        second = self.views._gallery(self.hass)
        self.assertIs(first, second)
        self.assertEqual(second.root, self.root / DOMAIN / "gallery")
        self.assert_legacy_intact()

    def test_cold_makerworld_save_writes_only_studio_root(self):
        response = self.post({"confirmed": True, "filename": "new.3mf"})
        self.assertEqual(response.status, 200)
        self.assertEqual((self.root / DOMAIN / "gallery" / "new.3mf").read_bytes(), b"synthetic-selected-profile")
        self.assert_legacy_intact()

    def test_save_after_management_call_keeps_archive_and_identity(self):
        self.management._repository(self.hass)
        response = self.post({"confirmed": True, "filename": "new.3mf"})
        self.assertEqual(response.status, 200)
        data = json.loads(response.body)["data"]
        self.assertEqual(self.views._gallery(self.hass).path_from_asset_id(data["asset_id"]), "new.3mf")
        self.assert_legacy_intact()

    def test_explicit_overwrite_applies_only_to_studio_owned_file(self):
        response = self.post({"confirmed": True, "filename": "existing.3mf", "overwrite": True})
        self.assertEqual(response.status, 200)
        self.assert_legacy_intact()
        self.assertEqual((self.root / DOMAIN / "gallery" / "existing.3mf").read_bytes(), b"synthetic-selected-profile")

    def test_non_admin_cannot_download_or_initialize_storage(self):
        self.assertEqual(self.post({"confirmed": True}, admin=False).status, 403)
        self.assertEqual(self.downloads, [])
        self.assertFalse((self.root / DOMAIN).exists())
        self.assert_legacy_intact()

    def test_unconfirmed_save_cannot_download_or_initialize_storage(self):
        self.assertEqual(self.post({"confirmed": False}).status, 409)
        self.assertEqual(self.downloads, [])
        self.assertFalse((self.root / DOMAIN).exists())
        self.assert_legacy_intact()

    def test_linked_studio_directory_is_rejected_before_write(self):
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda p: True if p == self.root / DOMAIN else original(p)):
            response = self.post({"confirmed": True, "filename": "new.3mf"})
        self.assertEqual(response.status, 400)
        self.assertEqual(json.loads(response.body)["error"]["code"], "invalid_makerworld_transfer")
        self.assert_legacy_intact()

if __name__ == "__main__":
    unittest.main()
