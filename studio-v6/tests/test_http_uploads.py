from __future__ import annotations

import hashlib

import pytest
from aiohttp.test_utils import TestClient, TestServer

from api.http_server import create_http_application
from core.bootstrap import build_runtime
from core.paths import StudioPaths


@pytest.mark.asyncio
async def test_upload_routes_create_write_and_finalize_asset(tmp_path) -> None:
    runtime = build_runtime(StudioPaths(tmp_path / "3D-Studio"))
    client = TestClient(TestServer(create_http_application(runtime)))
    await client.start_server()
    content = b"solid http_cube\nendsolid http_cube\n"
    digest = hashlib.sha256(content).hexdigest()
    try:
        response = await client.post(
            "/api/printer_control_center/v1/assets/uploads",
            json={
                "original_name": "http-cube.stl",
                "expected_size": len(content),
                "source_ui": "gallery",
                "target": "studio",
                "chunk_size": len(content),
                "expected_digest": digest,
            },
        )
        assert response.status == 201
        upload_id = (await response.json())["data"]["id"]

        response = await client.post(
            f"/api/printer_control_center/v1/assets/uploads/{upload_id}/chunks?offset=0",
            data=content,
        )
        assert response.status == 200
        assert (await response.json())["data"]["received_size"] == len(content)

        response = await client.post(
            f"/api/printer_control_center/v1/assets/uploads/{upload_id}/complete"
        )
        assert response.status == 200
        payload = await response.json()
        assert payload["error"] is None
        assert payload["data"]["asset"]["digest"] == digest
        assert payload["data"]["duplicate"] is False
    finally:
        await client.close()
        runtime.close()