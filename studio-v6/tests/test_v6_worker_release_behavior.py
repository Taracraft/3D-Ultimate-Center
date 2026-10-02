"""Exercise the real worker handler with temporary files and no network or printer."""
from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

import tempfile
import unittest

SERVER = Path(__file__).resolve().parents[1] / "deploy/homeassistant/host/3d-printer-slicing-server/server.py"


def post_release(worker, job_id, authorized=True):
    handler = object.__new__(worker["Handler"])
    handler.path = f"/api/v1/jobs/{job_id}/release"
    replies = []
    handler.send_json = lambda status, body: replies.append((status, body))
    handler.require_authorization = lambda: authorized
    handler.do_POST()
    return replies


def post_create(worker, payload):
    handler = object.__new__(worker["Handler"])
    handler.path = "/api/v1/jobs"
    replies = []
    handler.send_json = lambda status, body: replies.append((status, body))
    handler.require_authorization = lambda: True
    handler.read_body = lambda _limit: json.dumps(payload).encode("utf-8")
    handler.do_POST()
    return replies


class WorkerReleaseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        config = root / "config.json"
        config.write_text(json.dumps({"base_dir": str(root / "worker"), "token": "test-only"}), encoding="utf-8")
        with patch.object(sys, "argv", [str(SERVER), str(config)]), patch("http.server.ThreadingHTTPServer") as server:
            self.worker = runpy.run_path(str(SERVER))
            server.return_value.serve_forever.assert_called_once()

    def test_release_returns_http_200_with_job_state_and_is_idempotent(self):
        worker = self.worker
        queued = worker["JOBS"] / "test-job.queued.json"
        queued.write_text(json.dumps({"job_id": "test-job", "input_file": "model.stl", "manual_release": True}), encoding="utf-8")
        status, body = post_release(worker, "test-job")[0]
        assert status == 200
        assert body["status"] == "queued"
        assert body["released"] is True
        first = queued.read_bytes()
        assert json.loads(first)["released_at"]
        status, body = post_release(worker, "test-job")[0]
        assert status == 200
        assert body["already_released"] is True
        assert queued.read_bytes() == first


    def test_job_creation_auto_releases_normal_jobs_and_holds_manual_jobs(self):
        worker = self.worker
        profile = worker["PROFILES"] / "test-printer.json"
        profile.write_text("{}", encoding="utf-8")
        (worker["UPLOADS"] / "model.stl").write_bytes(b"stl")

        base = {
            "job_id": "normal-job",
            "input_file": "model.stl",
            "printer_profile": "test-printer",
        }
        status, body = post_create(worker, base)[0]
        assert status == 202
        normal = json.loads((worker["JOBS"] / "normal-job.queued.json").read_text())
        assert normal["manual_release"] is False
        assert normal["released_at"] == normal["created_at"]

        held_payload = {**base, "job_id": "manual-job", "manual_release": True}
        status, body = post_create(worker, held_payload)[0]
        assert status == 202
        held = json.loads((worker["JOBS"] / "manual-job.queued.json").read_text())
        assert held["manual_release"] is True
        assert "released_at" not in held

        invalid = {**base, "job_id": "invalid-job", "manual_release": "false"}
        assert post_create(worker, invalid)[0][0] == 400
        assert not (worker["JOBS"] / "invalid-job.queued.json").exists()

    def test_release_rejects_missing_active_invalid_and_unauthorized_jobs(self):
        worker = self.worker
        assert post_release(worker, "missing")[0][0] == 404
        assert post_release(worker, "bad.id")[0][0] == 400
        active = worker["JOBS"] / "active.slicing.json"
        active.write_text('{"job_id":"active"}', encoding="utf-8")
        assert post_release(worker, "active")[0][0] == 409
        assert not (worker["JOBS"] / "active.queued.json").exists()
        normal = worker["JOBS"] / "normal.queued.json"
        normal.write_text('{"job_id":"normal","manual_release":false}', encoding="utf-8")
        assert post_release(worker, "normal")[0][0] == 409
        # Older manually queued jobs lack the new explicit hold field.
        legacy = worker["JOBS"] / "legacy.queued.json"
        legacy.write_text('{"job_id":"legacy"}', encoding="utf-8")
        assert post_release(worker, "legacy")[0][1]["released"] is True
        queued = worker["JOBS"] / "held.queued.json"
        queued.write_text('{"job_id":"held","manual_release":true}', encoding="utf-8")
        before = queued.read_bytes()
        assert post_release(worker, "held", authorized=False) == []
        assert queued.read_bytes() == before


    def test_release_preserves_corrupt_job_files(self):
        worker = self.worker
        for contents in ["{broken", "[]", "null"]:
            with self.subTest(contents=contents):
                queued = worker["JOBS"] / "broken.queued.json"
                queued.write_text(contents, encoding="utf-8")
                status, body = post_release(worker, "broken")[0]
                assert status == 500
                assert body["error"] == "invalid_job_json"
                assert queued.read_text(encoding="utf-8") == contents
