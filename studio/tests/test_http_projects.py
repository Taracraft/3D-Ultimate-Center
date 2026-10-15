from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

from api.http_server import create_http_application
from core.bootstrap import build_runtime
from core.paths import StudioPaths


@pytest.mark.asyncio
async def test_project_routes_create_and_read_project(tmp_path) -> None:
    runtime = build_runtime(StudioPaths(tmp_path / "3D-Studio"))
    client = TestClient(TestServer(create_http_application(runtime)))
    await client.start_server()
    try:
        response = await client.post(
            "/api/ultimate_3d_studio/v1/projects",
            json={"name": "HTTP project"},
        )
        assert response.status == 201
        payload = await response.json()
        assert payload["error"] is None
        assert payload["request_id"] == response.headers["X-Request-ID"]
        project_id = payload["data"]["id"]

        response = await client.get(
            f"/api/ultimate_3d_studio/v1/projects/{project_id}"
        )
        assert response.status == 200
        payload = await response.json()
        assert payload["data"]["id"] == project_id
        assert payload["data"]["name"] == "HTTP project"
        assert payload["request_id"] == response.headers["X-Request-ID"]
    finally:
        await client.close()
        runtime.close()
