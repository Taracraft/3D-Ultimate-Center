"""Exercise the real upload/job method against the native worker filename contract.

No HTTP, printer access, Home Assistant installation, or slicer execution is used.
Only unrelated profile collaborators are stubbed; both production filename paths
and the worker's safe_filename validator are read from checked-in source files.
"""
from __future__ import annotations

import ast
import copy
import os
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from urllib.parse import unquote, urlsplit
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
ROUTER = Path(os.environ.get(
    "SLICER_UPLOAD_ROUTER_SOURCE",
    str(ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6/slicer_backend_router.py"),
))
WORKER = Path(os.environ.get(
    "SLICER_UPLOAD_WORKER_SOURCE",
    str(ROOT / "deploy/homeassistant/host/3d-printer-slicing-server/server.py"),
))


def _load_worker_validator():
    tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
    names = {"SAFE_NAME", "ALLOWED_EXTENSIONS"}
    nodes = [node for node in tree.body if (
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id in names
                for target in node.targets)
    ) or (isinstance(node, ast.FunctionDef) and node.name == "safe_filename")]
    if len(nodes) != 3:
        raise AssertionError("Expected native-worker safe_filename and its constants")
    namespace = {"re": re, "Path": Path}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(WORKER), "exec"), namespace)
    return namespace["safe_filename"]


def _load_create_plate_job():
    tree = ast.parse(ROUTER.read_text(encoding="utf-8-sig"), filename=str(ROUTER))
    methods = [node for node in ast.walk(tree)
               if isinstance(node, ast.AsyncFunctionDef)
               and node.name == "async_create_plate_job"]
    if len(methods) != 1:
        raise AssertionError("Expected one production async_create_plate_job method")

    class ServerError(Exception):
        pass

    class ClientError(Exception):
        pass

    namespace = {
        "re": re,
        "uuid4": uuid4,
        "SERVER_ENDPOINT": "http://worker.invalid:8099",
        "SlicerServerError": ServerError,
        "SlicerServerConfigurationError": ServerError,
        "ClientError": ClientError,
        "ClientTimeout": lambda **kwargs: kwargs,
        "normalize_backend": lambda backend: backend,
        "_server_printer_profile": lambda target: "bambu_lab_a1_04",
        "resolve_nozzle_contract": lambda catalog, target: {},
        "validate_process_overrides": lambda overrides, nozzle: dict(overrides or {}),
        "contract_payload": lambda nozzle: {},
        "_effective_material_plan": lambda catalog, material: copy.deepcopy(material),
        "bind_execution_contract": lambda *args: {"contract": "test-fixture"},
        "safe_project_name": lambda name, fallback: str(name).strip() or fallback,
        "project_name_from_3mf": lambda model, filename: filename,
        "_server_job": lambda payload: payload,
        "_profile_application": lambda *args: {},
    }
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, methods[0]], type_ignores=[]))
    exec(compile(module, str(ROUTER), "exec"), namespace)
    return namespace["async_create_plate_job"]


class _Response:
    def __init__(self, status, payload=None):
        self.status = status
        self.payload = payload or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def text(self):
        return '{"error":"invalid_filename"}'

    async def json(self, **kwargs):
        return self.payload


class _WorkerSession:
    def __init__(self, validator):
        self.validator = validator
        self.uploads = []
        self.jobs = []

    def post(self, url, **kwargs):
        path = unquote(urlsplit(url).path)
        if path.startswith("/api/v1/files/"):
            name = path[len("/api/v1/files/"):]
            self.uploads.append((name, kwargs["data"], kwargs["headers"]))
            return _Response(201 if self.validator(name) else 400)
        if path == "/api/v1/jobs":
            request = copy.deepcopy(kwargs["json"])
            self.jobs.append(request)
            return _Response(201, {"job_id": request["job_id"], "status": "queued"})
        raise AssertionError(f"Unexpected network operation: {url}")


class SlicerUploadFilenameTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker_validator = staticmethod(_load_worker_validator())
        cls.create_plate_job = staticmethod(_load_create_plate_job())

    async def _check_upload(self, title, *, from_archive=False, plate_index=0):
        session = _WorkerSession(self.worker_validator)
        model = b"PK\x03\x04original-multimaterial-3mf-bytes\x00\xff"
        material_plan = {"filaments": [
            {"channel": 0, "ams_slot": 0, "color": "#000000"},
            {"channel": 1, "ams_slot": 1, "color": "#FFFF00"},
            {"channel": 2, "ams_slot": 2, "color": "#FFFFFF"},
            {"channel": 3, "ams_slot": 3, "color": "#FF0000"},
        ]}
        original_plan = copy.deepcopy(material_plan)

        async def executor_job(function, *args):
            return function(*args)

        router = SimpleNamespace(session=session, hass=SimpleNamespace(async_add_executor_job=executor_job))
        result = await self.create_plate_job(
            router, "server", title, model, {}, plate_index,
            target_printer={"model": "Bambu Lab A1"},
            material_plan=material_plan,
            selected_process_profile={"profile_id": "a1-020-standard"},
            source_project_name=None if from_archive else title,
        )
        self.assertEqual(result["status"], "queued")
        self.assertEqual(len(session.uploads), 1)
        self.assertEqual(len(session.jobs), 1)
        upload_name, uploaded_bytes, headers = session.uploads[0]
        request = session.jobs[0]
        self.assertEqual(self.worker_validator(upload_name), upload_name)
        self.assertLessEqual(len(upload_name), 200)
        self.assertTrue(upload_name.endswith(".3mf"))
        self.assertIn(f"-plate-{plate_index + 1}-", upload_name)
        self.assertEqual(request["input_file"], upload_name)
        self.assertEqual(request["project_name"], title)
        self.assertEqual(uploaded_bytes, model)
        self.assertEqual(headers["Content-Type"], "application/octet-stream")
        self.assertEqual(request["material_plan"], original_plan)
        self.assertEqual(material_plan, original_plan)
        self.assertTrue(request["native_multimaterial"])
        self.assertEqual(request["requested_plate_index"], plate_index)

    async def test_multicolor_plus_part_count_from_archive(self):
        await self._check_upload("Base 1 - color 1 +4 Teile", from_archive=True)

    async def test_umlauts_in_display_title_are_preserved(self):
        await self._check_upload("Tara Größe ÄÖÜ äöü ß")

    async def test_transport_name_is_bounded_including_prefix_and_suffix(self):
        await self._check_upload("Tara" + "x" * 300, plate_index=12)

    async def test_ordinary_title(self):
        await self._check_upload("AMS-lite_A1_A1mini_4-color_test")

    async def test_title_separators_cannot_change_upload_path(self):
        await self._check_upload("../Tara/..\\Test?color=4#mehr+Teile")


if __name__ == "__main__":
    unittest.main()
