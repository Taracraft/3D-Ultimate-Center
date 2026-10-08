"""Exercise real router status methods without HA, a worker process or a slice."""
from __future__ import annotations

import ast
from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import unittest

from aiohttp import ClientError, ClientTimeout


SOURCE = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio/slicer_backend_router.py"
FUNCTIONS = {
    "native_job_id", "_effective_numeric_process_settings", "_normalized_setting_values",
    "_settings_confirmed", "_normalized_material", "_normalized_color", "_materials_confirmed",
    "_profile_application", "_build_detailed_warning", "_engine_result_metrics", "_server_job",
    "_cached_metadata", "_cached_artifact", "_store_artifact",
}


def router_namespace():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))
    nodes = [node for node in tree.body if (
        isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS
        or isinstance(node, ast.ClassDef) and node.name == "StudioSlicerBackendRouter"
    )]
    scope = {
        "Any": Any, "re": re, "ClientError": ClientError, "ClientTimeout": ClientTimeout,
        "SERVER_PREFIX": "server__", "SERVER_ENDPOINT": "http://test.invalid",
        "BACKEND_SERVER": "server", "SlicerServerError": RuntimeError,
        "_COMPLETED_ARTIFACT_CACHE": OrderedDict(), "_MAX_COMPLETED_ARTIFACT_CACHE": 1,
        "_COMPLETED_METADATA_CACHE": OrderedDict(), "_MAX_COMPLETED_METADATA_CACHE": 100,
        "project_name_from_server_payload": lambda payload, fallback: payload.get("project_name") or fallback,
    }
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), scope)
    return scope


def fixture():
    profile = {"id": "filament", "payload": {"nozzle_temperature": ["220"], "nozzle_temperature_initial_layer": ["220"]}}
    settings = {"layer_height": "0.2", "outer_wall_speed": "80"}
    job = {
        "process_overrides": {"selected_process_profile": {"profile_id": "process", "contract_sha256": "contract", "settings": settings}},
        "material_plan": {"filaments": [{"selected_profile": profile}]},
    }
    runtime = {
        "selected_process_profile": {"applied": True, "profile_id": "process", "contract_sha256": "contract"},
        "process_settings": deepcopy(settings),
        "filaments": [{"selected_profile_id": "filament", "material": "PLA", "color": "#101010",
            "selected_profile_sha256": hashlib.sha256(json.dumps(profile, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
            "parameter_settings": deepcopy(profile["payload"])}],
    }
    metadata = {
        "gcode_profile_settings": {**settings, **profile["payload"]},
        "analysis": {"layer_count": 10, "materials": [{"material": "PLA", "color": "#101010"}]},
        "heater_commands": [{"command": "M109", "channel": 1, "temperature_c": 220}],
    }
    payload = {"job_id": "fixture-job", "status": "completed", "job": job, "runtime": runtime}
    return payload, metadata


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self, **kwargs):
        return self.payload


class Session:
    def __init__(self, payload, status=200):
        self.payload, self.status, self.calls = payload, status, []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        return Response(self.payload, self.status)

    def delete(self, url, **kwargs):
        self.calls.append(("DELETE", url))
        return Response(self.payload, self.status)


class AnalysisStatusTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.scope = router_namespace()
        self.router = object.__new__(self.scope["StudioSlicerBackendRouter"])
        self.payload, self.metadata = fixture()

    def application(self, metadata):
        return self.scope["_profile_application"](self.payload["job"], self.payload["runtime"], metadata)

    def test_pending_becomes_confirmed_only_after_matching_analysis(self):
        before = deepcopy((self.payload, self.metadata))
        pending = self.application(None)
        assert pending["confirmation_source"] == "pending_gcode_analysis"
        assert pending["gcode_confirmed"] is False
        confirmed = self.application(self.metadata)
        assert confirmed["confirmation_source"] == "parsed_gcode_header_and_toolpath"
        assert confirmed["gcode_confirmed"] is True
        assert (self.payload, self.metadata) == before

    def test_analyzed_mismatch_does_not_masquerade_as_pending_analysis(self):
        self.metadata["gcode_profile_settings"]["outer_wall_speed"] = "200"
        result = self.application(self.metadata)
        assert result["confirmation_source"] == "gcode_analysis_unconfirmed"
        assert result["gcode_confirmed"] is False
        assert next(row for row in result["process"]["numeric_value_proof"] if row["key"] == "outer_wall_speed")["status"] == "mismatch"

    def test_incomplete_analysis_is_unconfirmed_and_never_promoted(self):
        for metadata in ({"analysis": {}}, {**self.metadata, "heater_commands": []}):
            with self.subTest(metadata=metadata):
                result = self.application(metadata)
                assert result["confirmation_source"] == "gcode_analysis_unconfirmed"
                assert result["gcode_confirmed"] is False

    def test_wrong_material_and_profile_hash_remain_fail_closed(self):
        for case in ("material", "color", "profile_hash", "process_contract"):
            with self.subTest(case=case):
                self.payload, self.metadata = fixture()
                if case == "material":
                    self.metadata["analysis"]["materials"][0]["material"] = "PETG"
                elif case == "color":
                    self.metadata["analysis"]["materials"][0]["color"] = "#FF0000"
                elif case == "profile_hash":
                    self.payload["runtime"]["filaments"][0]["selected_profile_sha256"] = "other"
                else:
                    self.payload["runtime"]["selected_process_profile"]["contract_sha256"] = "other"
                result = self.application(self.metadata)
                assert result["gcode_confirmed"] is False
                if case == "process_contract":
                    assert result["applied"] is False

    async def test_list_and_detail_share_completed_analysis_without_reanalyzing(self):
        self.scope["_store_artifact"]("fixture-job", (b"archive", "fixture.3mf", "digest", self.metadata))
        self.router.session = Session(self.payload)
        detail = await self.router.async_get_job("server__fixture-job")
        self.router.session = Session({"jobs": [self.payload]})
        listing = await self.router.async_list_jobs()
        assert listing[0]["profile_application"] == detail["profile_application"]
        assert listing[0]["slice_result"]["analysis"] == self.metadata["analysis"]
        assert listing[0]["profile_application"]["gcode_confirmed"] is True
        assert self.router.session.calls == [("GET", "http://test.invalid/api/v1/jobs")]

    async def test_list_reuses_only_the_matching_job_cache(self):
        self.scope["_store_artifact"]("another-job", (b"archive", "another.3mf", "digest", self.metadata))
        self.router.session = Session({"jobs": [self.payload, None]})
        listing = await self.router.async_list_jobs()
        assert len(listing) == 1
        assert listing[0]["profile_application"]["confirmation_source"] == "pending_gcode_analysis"
        assert listing[0]["profile_application"]["gcode_confirmed"] is False

    async def test_successful_delete_discards_analysis_for_reused_job_ids(self):
        self.scope["_store_artifact"]("fixture-job", (b"archive", "fixture.3mf", "digest", self.metadata))
        self.router.session = Session({"deleted": True})
        await self.router.async_delete_job("server__fixture-job")
        assert self.scope["_cached_metadata"]("fixture-job") is None
        assert self.scope["_cached_artifact"]("fixture-job") is None
        self.router.session = Session(self.payload)
        recreated = await self.router.async_get_job("server__fixture-job")
        assert recreated["profile_application"]["confirmation_source"] == "pending_gcode_analysis"
        assert recreated["profile_application"]["gcode_confirmed"] is False

    async def test_failed_delete_preserves_cached_proof(self):
        self.scope["_store_artifact"]("fixture-job", (b"archive", "fixture.3mf", "digest", self.metadata))
        self.router.session = Session({"error": "job_not_terminal"}, status=409)
        with self.assertRaises(RuntimeError):
            await self.router.async_delete_job("server__fixture-job")
        assert self.scope["_cached_metadata"]("fixture-job") is self.metadata


if __name__ == "__main__":
    unittest.main()
