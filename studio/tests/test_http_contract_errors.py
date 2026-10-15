from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

from api.http_server import create_http_application
from core.bootstrap import build_runtime
from core.paths import StudioPaths


@pytest.mark.asyncio
async def test_transport_errors_use_versioned_json_contract(tmp_path) -> None:
    runtime = build_runtime(StudioPaths(tmp_path / "3D-Studio"))
    client = TestClient(TestServer(create_http_application(runtime)))
    await client.start_server()
    try:
        response = await client.post(
            "/api/ultimate_3d_studio/v1/projects",
            data="{not-json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 400
        payload = await response.json()
        assert payload["data"] is None
        assert payload["error"]["code"] == "validation_failed"
        assert payload["request_id"] == response.headers["X-Request-ID"]
        assert payload["version"] == "v1"

        response = await client.post(
            "/api/ultimate_3d_studio/v1/projects",
            json={},
        )
        assert response.status == 400
        payload = await response.json()
        assert payload["error"]["code"] == "validation_failed"
        assert "name" in payload["error"]["message"]

        response = await client.get(
            "/api/ultimate_3d_studio/v1/does-not-exist"
        )
        assert response.status == 404
        assert (await response.json())["error"]["code"] == "not_found"

        response = await client.get(
            "/api/ultimate_3d_studio/v1/projects"
        )
        assert response.status == 405
        assert (await response.json())["error"]["code"] == "method_not_allowed"
    finally:
        await client.close()
        runtime.close()
