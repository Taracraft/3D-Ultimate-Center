"""Warm gallery caches and resumable sessions stay bound to Studio storage.

Synthetic temporary files only; no HA runtime, user gallery or external network.
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

COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "deploy/homeassistant/custom_components/ultimate_3d_studio"
)
DOMAIN = "ultimate_3d_studio"


class _Content:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def iter_chunked(self, size: int):
        async def chunks():
            if self.payload:
                yield self.payload

        return chunks()


class GalleryCacheSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.legacy = self.root / "printer_control_center" / "archive"
        self.legacy.mkdir(parents=True)
        self.legacy_model = self.legacy / "existing.3mf"
        self.legacy_model.write_bytes(b"legacy-original")
        self.legacy_before = (
            self.legacy_model.read_bytes(),
            self.legacy_model.stat().st_mtime_ns,
        )

        self.package = "studio_gallery_cache_session_test"
        package = ModuleType(self.package)
        package.__path__ = [str(COMPONENT)]
        modules = {self.package: package}

        def stub(name: str, **values):
            full_name = (
                name
                if name.startswith("homeassistant")
                else self.package + "." + name
            )
            module = ModuleType(full_name)
            module.__dict__.update(values)
            modules[full_name] = module

        stub("homeassistant.components.http", HomeAssistantView=object)
        stub("homeassistant.core", HomeAssistant=object)
        stub(
            "const",
            API_BASE="/api/ultimate_3d_studio/v1",
            DOMAIN=DOMAIN,
            VERSION="fixture",
        )
        stub("geometry_export", export_binary_stl=lambda *args: b"")
        stub("makerworld_detail", async_load_detail=None)
        stub("makerworld_download", async_download_instance=None)
        stub(
            "makerworld_runtime",
            MakerWorldError=type("MakerWorldError", (Exception,), {}),
            get_makerworld_runtime=None,
        )
        stub(
            "rich_text",
            readable_rich_text=lambda value, *args: value,
            safe_rich_html=lambda value: value,
        )
        self.module_patch = patch.dict(sys.modules, modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)

        def load(suffix: str):
            name = self.package + "." + suffix
            spec = importlib.util.spec_from_file_location(
                name, COMPONENT / (suffix + ".py")
            )
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module

        self.storage = load("gallery_storage_paths")
        self.gallery = load("gallery_repository")
        self.gallery_v2 = load("gallery_repository_v2")
        self.request_body = load("request_body")
        self.maker = load("makerworld_views")
        self.management = load("gallery_management_views")
        self.management_v2 = load("gallery_management_views_v2")

        async def executor(function, *args):
            return function(*args)

        self.hass = SimpleNamespace(
            data={},
            config=SimpleNamespace(
                path=lambda *parts: str(self.root.joinpath(*parts))
            ),
            async_add_executor_job=executor,
        )

        async def download(request, instance, body):
            return b"synthetic-selected-profile"

        self.maker._download_payload_from_body = download

    def _domain_data(self):
        return self.hass.data.setdefault(DOMAIN, {})

    def _maker_post(self, filename: str, *, overwrite: bool = False):
        hass = self.hass

        class Request(dict):
            def __init__(self):
                super().__init__(hass_user=SimpleNamespace(is_admin=True))
                self.app = {"hass": hass}
                self.query = {}

            async def json(self):
                return {
                    "confirmed": True,
                    "filename": filename,
                    "overwrite": overwrite,
                }

        return asyncio.run(
            self.maker.MakerWorldInstanceView().post(
                Request(), "instance-a", "save"
            )
        )

    def _session_request(self, payload: bytes = b"", offset: int = 0):
        request = {
            "hass_user": SimpleNamespace(is_admin=True),
        }
        value = type("Request", (dict,), {})(request)
        value.app = {"hass": self.hass}
        value.query = {"offset": str(offset)}
        value.content_length = len(payload)
        value.content = _Content(payload)
        return value

    def _assert_legacy_model_intact(self):
        self.assertEqual(
            (
                self.legacy_model.read_bytes(),
                self.legacy_model.stat().st_mtime_ns,
            ),
            self.legacy_before,
        )

    def test_warm_legacy_v1_cache_makerworld_first_is_replaced_before_save(self):
        stale = self.gallery.StudioGalleryRepository(self.legacy)
        self._domain_data()["gallery_management_repository"] = stale

        current = self.maker._gallery(self.hass)
        self.assertIsNot(current, stale)
        self.assertIs(current, self.management._repository(self.hass))
        self.assertEqual(current.root, self.root / DOMAIN / "gallery")

        response = self._maker_post("new.3mf")
        self.assertEqual(response.status, 200)
        self.assertEqual(
            (self.root / DOMAIN / "gallery" / "new.3mf").read_bytes(),
            b"synthetic-selected-profile",
        )
        self._assert_legacy_model_intact()

    def test_warm_legacy_v1_cache_management_first_cannot_overwrite_legacy(self):
        stale = self.gallery.StudioGalleryRepository(self.legacy)
        self._domain_data()["gallery_management_repository"] = stale

        current = self.management._repository(self.hass)
        self.assertIsNot(current, stale)
        self.assertIs(current, self.maker._gallery(self.hass))

        response = self._maker_post("existing.3mf", overwrite=True)
        self.assertEqual(response.status, 200)
        self.assertEqual(
            (self.root / DOMAIN / "gallery" / "existing.3mf").read_bytes(),
            b"synthetic-selected-profile",
        )
        self._assert_legacy_model_intact()

    def test_warm_legacy_v2_cache_is_replaced(self):
        stale = self.gallery_v2.StudioGalleryRepositoryV2(self.legacy)
        self._domain_data()["gallery_management_repository_v2"] = stale

        current = self.management_v2._repository(self.hass)
        self.assertIsNot(current, stale)
        self.assertEqual(current.root, self.root / DOMAIN / "gallery")
        self._assert_legacy_model_intact()

    def test_valid_warm_caches_keep_identity(self):
        v1 = self.management._repository(self.hass)
        v2 = self.management_v2._repository(self.hass)
        self.assertIs(self.maker._gallery(self.hass), v1)
        self.assertIs(self.management._repository(self.hass), v1)
        self.assertIs(self.management_v2._repository(self.hass), v2)

    def test_linked_root_after_cache_creation_is_rejected_without_cache_clear(self):
        v1 = self.management._repository(self.hass)
        v2 = self.management_v2._repository(self.hass)
        original = Path.is_symlink

        def fake_link(path: Path) -> bool:
            if path == self.root / DOMAIN:
                return True
            return original(path)

        with patch.object(Path, "is_symlink", fake_link):
            with self.assertRaisesRegex(
                ValueError, "linked_studio_storage_not_allowed"
            ):
                self.maker._gallery(self.hass)
            with self.assertRaisesRegex(
                ValueError, "linked_studio_storage_not_allowed"
            ):
                self.management_v2._repository(self.hass)

        self.assertIs(
            self._domain_data()["gallery_management_repository"], v1
        )
        self.assertIs(
            self._domain_data()["gallery_management_repository_v2"], v2
        )

    def test_reload_preserves_domain_data_but_repairs_stale_cache(self):
        stale = self.gallery.StudioGalleryRepository(self.legacy)
        data = self._domain_data()
        data["gallery_management_repository"] = stale
        data["runtimes"] = {"old-entry": object()}
        data["runtimes"] = {}

        current = self.management._repository(self.hass)
        self.assertIsNot(current, stale)
        self.assertEqual(current.root, self.root / DOMAIN / "gallery")
        self.assertEqual(data["runtimes"], {})
        self._assert_legacy_model_intact()

    def test_legacy_session_chunk_fails_closed_without_data_loss(self):
        part = self.legacy / "old-upload.part"
        part.write_bytes(b"old")
        session = {
            "path": str(part),
            "filename": "old.3mf",
            "folder": "",
            "overwrite": False,
            "expected_size": 4,
            "received_size": 3,
            "chunk_size": 4,
            "created_at": 1.0,
        }
        self._domain_data()["gallery_upload_sessions_v2"] = {
            "legacy": session
        }
        before = json.dumps(session, sort_keys=True)

        response = asyncio.run(
            self.management_v2.GalleryUploadChunkView().post(
                self._session_request(b"x", 3), "legacy"
            )
        )

        self.assertEqual(response.status, 409)
        self.assertEqual(
            json.loads(response.body)["error"]["code"],
            "upload_session_path_invalid",
        )
        self.assertEqual(part.read_bytes(), b"old")
        self.assertEqual(json.dumps(session, sort_keys=True), before)

    def test_legacy_session_complete_fails_closed_without_data_loss(self):
        part = self.legacy / "complete-upload.part"
        part.write_bytes(b"old")
        session = {
            "path": str(part),
            "filename": "old.3mf",
            "folder": "",
            "overwrite": True,
            "expected_size": 3,
            "received_size": 3,
            "chunk_size": 4,
            "created_at": 1.0,
        }
        sessions = {"legacy": session}
        self._domain_data()["gallery_upload_sessions_v2"] = sessions
        before = json.dumps(session, sort_keys=True)

        response = asyncio.run(
            self.management_v2.GalleryUploadCompleteView().post(
                self._session_request(), "legacy"
            )
        )

        self.assertEqual(response.status, 409)
        self.assertEqual(
            json.loads(response.body)["error"]["code"],
            "upload_session_path_invalid",
        )
        self.assertEqual(part.read_bytes(), b"old")
        self.assertIn("legacy", sessions)
        self.assertEqual(json.dumps(session, sort_keys=True), before)
        self._assert_legacy_model_intact()

    def test_current_session_can_chunk_and_complete(self):
        upload_id = "current"
        part = self.root / DOMAIN / "upload_sessions" / f"{upload_id}.part"
        part.parent.mkdir(parents=True)
        part.write_bytes(b"a")
        sessions = {
            upload_id: {
                "path": str(part),
                "filename": "current.3mf",
                "folder": "",
                "overwrite": False,
                "expected_size": 2,
                "received_size": 1,
                "chunk_size": 4,
                "created_at": 1.0,
            }
        }
        self._domain_data()["gallery_upload_sessions_v2"] = sessions

        chunk = asyncio.run(
            self.management_v2.GalleryUploadChunkView().post(
                self._session_request(b"b", 1), upload_id
            )
        )
        self.assertEqual(chunk.status, 200)
        complete = asyncio.run(
            self.management_v2.GalleryUploadCompleteView().post(
                self._session_request(), upload_id
            )
        )

        self.assertEqual(complete.status, 200)
        self.assertNotIn(upload_id, sessions)
        self.assertFalse(part.exists())
        self.assertEqual(
            (self.root / DOMAIN / "gallery" / "current.3mf").read_bytes(),
            b"ab",
        )
        self._assert_legacy_model_intact()


if __name__ == "__main__":
    unittest.main()
